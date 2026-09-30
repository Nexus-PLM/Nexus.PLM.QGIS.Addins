# CLAUDE.md — Nexus.PLM.QGIS.Addins

The Nexus PLM add-in for QGIS: a PyQGIS plugin with its own **Nexus PLM** menu and toolbar.

---

## Layout

```
plugin/
  build.py              installs into a QGIS 4 profile AND enables the plugin in QGIS4.ini
  nexus_plm/            the plugin package - the folder name is what QGIS imports
    __init__.py         classFactory(iface); imports plugin.py lazily so tests can import the package
    metadata.txt        name / version / qgisMinimumVersion / supportsQt6
    plugin.py           QMenu + QToolBar from menu.MENU; the ONLY module importing qgis at the top
    nexusplm/
      client.py         HTTP to the Addin Service     ] shared with Inkscape and GIMP; no QGIS API
      state.py          path -> item map              ] in any of them
      identity.py       which item a file is          ]
      navigator.py      folder tree shaping           ]
      menu.py           the menu table - no qgis, so tests can read it
      project.py        the record (custom properties, scope NexusPLM) + display (nexus_* variables)
      host.py           document_path / upload_copy / same_file / open_document / window_handle
      commands.py       what each menu entry does; Context(client, project, path, hwnd)
tools/build_template.py  developer-only; run under "C:\Program Files\QGIS 4.2.2\bin\python-qgis.bat"
tests/                   pytest with tests/fakeqgis.py; runs under plain Python
installer/               Inno Setup, per-user
```

## Build

```bash
python plugin/build.py --install      # then restart QGIS (menu is built at load)
python -m pytest tests/ -q
```

## Rules that are not negotiable

- **The record is the deliverable.** PLM values go into the project's custom properties (scope
  `NexusPLM`) so the `.qgz` carries them wherever it goes. The `nexus_*` project variables that a
  layout label can show are a convenience - never let a command depend on them.
- **Uploads write the project to its OWN file** (`host.upload_copy` = `project.write(path)`) and
  send that path. Not a temp copy: `SaveRequest.FilePath` is one path the service both reads and
  records as `plm_file_path`, so a temp path became the next revision's home on the Inkscape
  add-in. Marc: "it must get written to the staging directory."
- **Revise ups the revision in place.** When the staged file *is* the open project
  (`host.same_file`), `_hand_over` writes the new revision's record into the live project instead
  of launching a second QGIS. A different file - Open from PLM, Search - opens in a **new QGIS
  process**, never via `iface.addProject`, which would replace what the user has open.
- **Save As New offers only `project.offerable_values`**: filled-in values that are not PLM's own
  (part number, revision, the four stamps). The service merges the offer onto the new revision.
- **No toast of our own where the service already toasts** (Sign Out). Save As Existing follows
  up with refresh-values because the service's answer carries no mappings.
- **`qgis` is imported only in `plugin.py` (top) and inside functions in `host.py`.** Everything
  else is tested without QGIS; `project.py` takes the project object as an argument and edits a
  staged file with `zipfile` + `xml.etree`, never through QGIS.
- **Standard library only** in `nexusplm/`, plus what QGIS bundles. `requests` is not there.
- **The service is the only thing this talks to.** Never the Engine, never the vault.
- **A command never leaves a traceback in front of the user.** QGIS shows one in a "Python error"
  bar; `commands.run` turns anything unexpected into a toast, only `ServiceUnavailable` escapes and
  `plugin.py` turns that into a message-bar warning.
- Host-specific facts are **declared by the add-in** (`HOST_NAME = "QGIS"`,
  `FILE_EXTENSIONS = ".qgz;.qgs"`) and travel with the request; the service keeps no list of hosts.

## Measured facts worth not re-learning (QGIS 4.2.2, 29 Sep 2026)

- The profile is **`%APPDATA%\QGIS\QGIS4\profiles\default`**, settings in `QGIS\QGIS4.ini`,
  plugins in `python\plugins\<package>`. The QGIS 3 docs say `QGIS3`; QGIS 4 does not.
- A copied plugin is a **disabled** plugin until `[PythonPlugins] <name>=true` is in the ini.
  `build.py` and the installer both write it.
- Custom properties round-trip: `writeEntry("NexusPLM", key, value)` lands as
  `<properties><properties name="NexusPLM"><properties name="Key" type="QString">` in the `.qgs`
  inside the `.qgz` (beside a `*_styles.db`), and `readEntry` gets it back after `read()`.
- Project variables are stored as two parallel `QStringList`s under `<properties name="Variables">`:
  `variableNames` and `variableValues`. `project.write_into_file` writes them that way.
- `QgsProject.fileName()` answers forward slashes and `""` for never-saved; `host.document_path`
  normalises to a Windows path / `None`.
- Headless PyQGIS works from `bin\python-qgis.bat` after `QgsApplication.setPrefixPath(
  ".../apps/qgis", True)`; `QgsApplication.qgisSettingsDirPath()` there points at a *python*
  profile, not QGIS's - do not read the profile path from it.
- Qt 6.11 / PyQt 6.11 / Python 3.12 bundled.

## Server side

Type `n5QgisProject` (cloned from `n5GimpImage`, 12 connector mappings), numbering `QgisProject`
= `QGP-########-QGZ`, MIME row `qgz` = `application/x-qgis-project` (`.qgz,.qgs`), template
`QGIS Project.qgz` in the vault - all via the API on 29 Sep 2026.

## Still to do

- E2E sweep of the 21 commands on the installed plugin.
- Toolbar icons: `plugin/nexus_plm/icons/<command>.svg` are looked up and fall back to no icon.
