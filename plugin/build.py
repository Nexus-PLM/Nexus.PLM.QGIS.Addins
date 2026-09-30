#!/usr/bin/env python3
"""Install the Nexus PLM plugin into QGIS.

    python build.py --install                      # into the default profile
    python build.py --install --profile Marc       # into a named profile

There is nothing to generate - QGIS takes the menu from the plugin's own ``initGui`` - so this
script copies the plugin folder into the profile's ``python/plugins`` and **enables it**: a plugin
that is only copied sits in Plugins > Manage and Install as an unticked box, which reads to a
user as "the install failed". QGIS records the enabled set in the profile's ``QGIS4.ini`` under
``[PythonPlugins]``; ``nexus_plm=true`` there is what turns the menu on at the next start.
"""

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: The plugin folder, which is also the Python package QGIS imports.
PLUGIN = "nexus_plm"

#: Where QGIS keeps profiles. ``QGIS4`` in QGIS 4 - measured on 4.2.2, whose first start created
#: ``%APPDATA%\QGIS\QGIS4\profiles\default`` with ``QGIS\QGIS4.ini`` inside. The QGIS 3 docs say
#: ``QGIS3``; that is QGIS 3.
PROFILES_SUBDIR = os.path.join("QGIS", "QGIS4", "profiles")
SETTINGS_INI = "QGIS4.ini"


def profiles_root():
    """The folder holding every profile of the current user."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, PROFILES_SUBDIR)
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/QGIS/QGIS4/profiles")
    return os.path.expanduser("~/.local/share/QGIS/QGIS4/profiles")


def plugins_dir(profile="default"):
    """The profile's plugins folder, where a plugin package must sit."""
    return os.path.join(profiles_root(), profile, "python", "plugins")


def settings_file(profile="default"):
    """The profile's QGIS4.ini, which records which plugins are enabled."""
    return os.path.join(profiles_root(), profile, "QGIS", SETTINGS_INI)


def install(target):
    """Copy the plugin folder into ``target``, replacing any previous copy."""
    os.makedirs(target, exist_ok=True)
    destination = os.path.join(target, PLUGIN)
    # Replace rather than merge: a module deleted from the source must not survive in the
    # installed copy, which is how a stale file goes on being imported for weeks.
    shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, PLUGIN), destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return destination


def enable(ini_path):
    """Set ``[PythonPlugins] nexus_plm=true`` in a QGIS4.ini, keeping everything else as it is.

    Written by hand rather than through ``configparser``: QGIS's ini holds keys ``configparser``
    rejects (``%`` escapes, duplicate-looking keys under ``[Recent]``), and a rewrite that
    normalises them is a rewrite that loses the user's settings.
    """
    lines = []
    if os.path.isfile(ini_path):
        with open(ini_path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()

    section = "[PythonPlugins]"
    key = PLUGIN + "="
    out, in_section, written, seen_section = [], False, False, False
    for line in lines:
        if line.strip().startswith("[") and line.strip().endswith("]"):
            if in_section and not written:
                out.append(key + "true"); written = True
            in_section = line.strip() == section
            seen_section = seen_section or in_section
            out.append(line)
            continue
        if in_section and line.startswith(key):
            if not written:
                out.append(key + "true"); written = True
            continue
        out.append(line)
    if in_section and not written:
        out.append(key + "true"); written = True
    if not seen_section:
        if out and out[-1].strip():
            out.append("")
        out.extend([section, key + "true"])

    os.makedirs(os.path.dirname(ini_path), exist_ok=True)
    with open(ini_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")
    return ini_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="copy the plugin into a QGIS profile")
    parser.add_argument("--profile", default="default", help="the QGIS profile (default: default)")
    parser.add_argument("--target", help="install somewhere other than the profile's plugins folder")
    arguments = parser.parse_args()

    if not arguments.install:
        print("nothing to build - the menu lives in %s/plugin.py. Pass --install to deploy." % PLUGIN)
        return

    if not arguments.target and not os.path.isdir(os.path.join(profiles_root(), arguments.profile)):
        raise SystemExit("No QGIS profile '%s' under %s. Start QGIS once first."
                         % (arguments.profile, profiles_root()))

    target = arguments.target or plugins_dir(arguments.profile)
    print("installed to %s" % install(target))
    if not arguments.target:
        print("enabled in %s" % enable(settings_file(arguments.profile)))


if __name__ == "__main__":
    main()
