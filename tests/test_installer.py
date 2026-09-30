"""The installer script, held against the source it ships.

An Inno script is text nobody runs until release day, and every value in it that also lives
somewhere else - the version, the package name, the profile path - is a value that drifts. These
tests read the .iss as text and check each against where it really comes from.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugin", "nexus_plm"))
sys.path.insert(0, os.path.join(ROOT, "plugin"))

import build  # noqa: E402
from nexusplm import commands  # noqa: E402

ISS = os.path.join(ROOT, "installer", "Nexus.PLM.QGIS.Addin.iss")


def script():
    with open(ISS, encoding="utf-8") as handle:
        return handle.read()


def define(name):
    match = re.search(r'^#define %s\s+"([^"]*)"' % re.escape(name), script(), re.MULTILINE)
    assert match, "no #define %s in the installer" % name
    return match.group(1)


class TestTheVersion:
    def test_the_installer_ships_the_version_the_add_in_reports(self):
        assert define("AppVersion") == commands.VERSION


class TestThePackageName:
    def test_it_is_the_folder_build_py_installs(self):
        assert define("PluginName") == build.PLUGIN

    def test_the_folder_exists_and_is_a_package_with_a_class_factory(self):
        folder = os.path.join(ROOT, "plugin", define("PluginName"))
        assert os.path.isfile(os.path.join(folder, "__init__.py"))
        assert os.path.isfile(os.path.join(folder, "metadata.txt"))


class TestTheDestination:
    def test_it_is_the_qgis4_default_profile_build_py_uses(self):
        assert define("ProfileDir") == r"{userappdata}\QGIS\QGIS4\profiles\default"
        assert build.plugins_dir().lower().endswith(r"\qgis\qgis4\profiles\default\python\plugins")

    def test_the_plugin_is_enabled_in_the_same_ini_build_py_writes(self):
        body = script()
        assert re.search(r'Filename:\s*"\{#ProfileDir\}\\QGIS\\QGIS4\.ini";\s*Section:\s*"PythonPlugins";\s*Key:\s*"\{#PluginName\}";\s*String:\s*"true"', body)
        assert build.settings_file().lower().endswith(r"\qgis\qgis4.ini")

    def test_enabling_is_undone_on_uninstall(self):
        assert "uninsdeleteentry" in script()


class TestUninstall:
    def test_it_removes_only_its_own_folder(self):
        body = script()
        assert r'{#PluginsDir}\{#PluginName}' in body
        assert not re.search(r'Type:\s*filesandordirs;\s*Name:\s*"\{#PluginsDir\}"\s*$', body, re.MULTILINE)


class TestPayload:
    def test_compiled_python_is_excluded(self):
        assert "__pycache__" in script()

    def test_the_developer_tools_are_not_shipped(self):
        sources = re.findall(r'^Source:\s*"([^"]+)"', script(), re.MULTILINE)
        assert sources == [r"..\plugin\{#PluginName}\*"]
