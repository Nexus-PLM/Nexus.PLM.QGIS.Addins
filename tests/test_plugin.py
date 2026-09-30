"""The plugin package as QGIS sees it, checked without importing qgis.

QGIS decides whether a folder is a plugin from ``metadata.txt`` and ``classFactory``; both are
text nobody runs until QGIS does, and both drift from the code. These tests read them as text.
"""

import configparser
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin", "nexus_plm")
sys.path.insert(0, PLUGIN)
sys.path.insert(0, os.path.join(ROOT, "plugin"))

import build  # noqa: E402
from nexusplm import commands, menu  # noqa: E402


def metadata():
    parser = configparser.ConfigParser()
    parser.read(os.path.join(PLUGIN, "metadata.txt"), encoding="utf-8")
    return parser["general"]


class TestMetadata:
    def test_the_version_is_the_one_the_add_in_reports(self):
        assert metadata()["version"] == commands.VERSION

    def test_it_declares_qt6_and_a_qgis_range_that_includes_4(self):
        md = metadata()
        assert md["supportsQt6"].lower() == "true"
        assert float(md["qgisMinimumVersion"]) <= 4.0 <= float(md["qgisMaximumVersion"])

    def test_the_name_is_the_menu_title(self):
        assert metadata()["name"] == menu.MENU_TITLE


class TestTheEntryPoint:
    def test_class_factory_exists_and_defers_the_qgis_import(self):
        body = open(os.path.join(PLUGIN, "__init__.py"), encoding="utf-8").read()
        assert "def classFactory(iface)" in body
        assert not re.search(r"^\s*(from|import) qgis", body, re.MULTILINE)

    def test_the_package_imports_without_qgis(self):
        import importlib
        module = importlib.import_module("nexus_plm") if "nexus_plm" in sys.modules else None
        # Import through the plugin folder's parent so the package name is what QGIS uses.
        sys.path.insert(0, os.path.join(ROOT, "plugin"))
        import nexus_plm  # noqa: F401
        assert callable(nexus_plm.classFactory)

    def test_the_folder_is_the_package_build_py_installs(self):
        assert os.path.basename(PLUGIN) == build.PLUGIN


class TestPluginPy:
    """plugin.py can only run inside QGIS; hold its text against the menu table instead."""

    def test_it_builds_every_entry_from_the_menu_table_not_a_second_list(self):
        body = open(os.path.join(PLUGIN, "plugin.py"), encoding="utf-8").read()
        assert "for entry in MENU" in body
        for command, _label in menu.ENTRIES:
            assert '"%s"' % command not in body, "plugin.py names %s directly - the table is the list" % command

    def test_each_action_binds_its_own_command(self):
        """A lambda closing over the loop variable would run the last command for every entry."""
        body = open(os.path.join(PLUGIN, "plugin.py"), encoding="utf-8").read()
        assert "name=command" in body


class TestIcons:
    """Every command has an icon at every size; without one the toolbar shows a bare word.

    The pictures are the standard Nexus set the LibreOffice and OpenOffice add-ins ship, copied,
    so every host shows the same icons - Marc's ask. Sizes 16/26/50 as that set is drawn.
    """

    ICONS = os.path.join(PLUGIN, "icons")
    SIZES = (16, 26, 50)

    def test_every_command_has_a_png_at_every_size(self):
        missing = ["%s_%d.png" % (c, s) for c, _ in menu.ENTRIES for s in self.SIZES
                   if not os.path.isfile(os.path.join(self.ICONS, "%s_%d.png" % (c, s)))]
        assert missing == []

    def test_every_dropdown_group_has_its_icon_at_every_size(self):
        missing = ["group-%s_%d.png" % (k, s) for k in menu.GROUP_KEYS for s in self.SIZES
                   if not os.path.isfile(os.path.join(self.ICONS, "group-%s_%d.png" % (k, s)))]
        assert missing == []

    def test_each_file_is_a_png_of_the_size_its_name_says(self):
        for name in os.listdir(self.ICONS):
            size = int(name.rsplit("_", 1)[1].split(".")[0])
            with open(os.path.join(self.ICONS, name), "rb") as handle:
                head = handle.read(24)
            assert head[:8] == b"\x89PNG\r\n\x1a\n", name
            width = int.from_bytes(head[16:20], "big")
            assert width == size, "%s is %d wide" % (name, width)

    def test_plugin_py_loads_the_same_sizes_the_files_come_in(self):
        body = open(os.path.join(PLUGIN, "plugin.py"), encoding="utf-8").read()
        assert "ICON_SIZES = (16, 26, 50)" in body
        assert '"%s_%d.png" % (name, size)' in body


class TestAvailabilityIsWired:
    """plugin.py can only run inside QGIS; hold its text to the rule and its triggers."""

    def body(self):
        return open(os.path.join(PLUGIN, "plugin.py"), encoding="utf-8").read()

    def test_the_rule_module_decides_not_plugin_py(self):
        assert "availability.enabled_commands(state, user=user, path=path)" in self.body()

    def test_it_refreshes_when_the_project_changes_after_a_command_and_when_a_menu_opens(self):
        body = self.body()
        for trigger in ("project.readProject", "project.cleared", "project.fileNameChanged",
                        "aboutToShow.connect(self.refresh_availability)",
                        "finally:\n            self.refresh_availability()"):
            assert trigger in body, trigger

    def test_one_action_serves_menu_and_toolbar(self):
        """Disabling an action must grey it out in both places at once."""
        body = self.body()
        assert "self.menu.addAction(self.actions[entry[0]])" in body
        assert "menu.addAction(self.actions[command])" in body
        assert "self.toolbar.addAction(self.actions[item])" in body

    def test_an_unreachable_service_leaves_everything_enabled(self):
        """So the user meets the 'tray is not running' message, not a greyed-out toolbar."""
        body = self.body()
        assert "except ServiceUnavailable:\n            allowed = set(self.actions)" in body


class TestEnablingThePlugin:
    """A copied plugin is an unticked box in the manager; build.py must also enable it."""

    def test_a_fresh_ini_gets_the_section_and_key(self, tmp_path):
        ini = str(tmp_path / "QGIS" / "QGIS3.ini")
        build.enable(ini)
        assert open(ini, encoding="utf-8").read().strip().splitlines()[-2:] == ["[PythonPlugins]", "nexus_plm=true"]

    def test_an_existing_ini_keeps_everything_else(self, tmp_path):
        ini = tmp_path / "QGIS3.ini"
        ini.write_text("[Recent]\nfile=C%3A/odd.qgz\n\n[PythonPlugins]\nprocessing=true\nnexus_plm=false\n\n[UI]\nx=1\n", encoding="utf-8")
        build.enable(str(ini))
        text = ini.read_text(encoding="utf-8")
        assert "file=C%3A/odd.qgz" in text and "processing=true" in text and "x=1" in text
        assert text.count("nexus_plm=") == 1 and "nexus_plm=true" in text

    def test_an_ini_without_the_section_gains_it(self, tmp_path):
        ini = tmp_path / "QGIS3.ini"
        ini.write_text("[UI]\nx=1\n", encoding="utf-8")
        build.enable(str(ini))
        text = ini.read_text(encoding="utf-8")
        assert "[PythonPlugins]" in text and "nexus_plm=true" in text and "x=1" in text
