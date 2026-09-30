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
