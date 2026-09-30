# Nexus PLM for QGIS — developer guide

How the plugin is built, how to change it safely, and what QGIS does differently. Every "measured"
fact below was measured on QGIS 4.2.2 and cost something to learn.

## Architecture in one paragraph

QGIS loads a plugin by importing the package in `python/plugins/<name>/` and calling its
`classFactory(iface)`. Ours returns `NexusPlmPlugin`, whose `initGui` builds one `QAction` per row
of the table in `nexusplm/menu.py`, puts them in a **Nexus PLM** menu (inserted before Help) and on
a toolbar of dropdown buttons laid out exactly like the LibreOffice add-in's, and keeps each
action's enabled state in step with what the service says. A click calls
`commands.run(name, QgsProject.instance(), hwnd)`. The plugin runs **inside QGIS's process** and
holds the live project. Everything that talks HTTP is in `nexusplm/client.py`; everything that
touches the project's record is in `nexusplm/project.py`; everything that knows it is inside QGIS
is in `nexusplm/host.py` (importing `qgis` inside functions) and `plugin.py` (the only module
importing it at the top). Everything else runs under plain Python, which is why 105 tests need no
QGIS.

```
plugin/
  build.py                copies into %APPDATA%\QGIS\QGIS4\profiles\<profile>\python\plugins AND enables in QGIS4.ini
  nexus_plm/
    __init__.py           classFactory(iface) - imports plugin.py lazily
    metadata.txt          name, version, qgisMinimumVersion, supportsQt6
    plugin.py             QMenu + QToolBar(QToolButton dropdowns) + refresh_availability
    icons/                <command>_16|26|50.png, group-<key>_16|26|50.png - the standard Nexus set
    nexusplm/
      menu.py             MENU (entries + separators), TOOLBAR (plain buttons, Group dropdowns, separators)
      availability.py     enabled_commands(state, user, path) → set of command names
      commands.py         one function per command; Context; COMMANDS; run()
      project.py          read_values / write_values / offerable_values / write_into_file / read_from_file
      host.py             document_path / upload_copy / same_file / open_document / window_handle / say / log
      client.py           Client: one method per service endpoint (shared with Inkscape and GIMP)
      state.py            the path → item map, %APPDATA%\NexusPLM\qgis-documents.json (shared)
      identity.py         which item a file is: the map first, then /plm/state (shared)
      navigator.py        folder tree shaping (shared)
tools/build_template.py   makes dist/QGIS Project.qgz (needs QGIS's Python)
tests/                    fakeqgis.py, test_commands, test_project, test_host, test_plugin, test_availability, test_installer
installer/                Inno Setup script
```

## The one rule everything follows

**The plugin talks only to the Addin Service** (`http://localhost:5100`), never to the Engine or
the vault. The service owns the session, every dialog and every toast, and it enumerates no hosts:
this add-in declares `HOST_NAME = "QGIS"` and `FILE_EXTENSIONS = ".qgz;.qgs"` with each request.
If a change here seems to need a service change, stop — it usually means the add-in should be
declaring something instead.

## The record

`project.py` keeps PLM's values in the project's **custom properties** under the scope `NexusPLM`
(`project.writeEntry("NexusPLM", key, value)`), which QGIS stores in the `.qgs` as

```xml
<properties>
  <properties name="NexusPLM">
    <properties name="PartNumber" type="QString">QGP-00000001-QGZ</properties>
    …
```

and preserves through every save. Alongside, each value is exposed as a **project variable**
`nexus_<key lower>` (`QgsExpressionContextUtils.setProjectVariable`) so a layout label can show it,
and the project's **title and metadata title** are set to the part number so the window says which
item it is. `write_values` returns `(recorded, shown)`.

`write_into_file(path, values)` does the same to a **file nothing has open**: it rewrites the
`.qgs` member of the `.qgz` with `zipfile` + `xml.etree` (variables as the two parallel
`QStringList`s QGIS uses, `variableNames`/`variableValues`), copying every other member — the
styles database — through untouched. `read_from_file` reads it back. Neither needs QGIS.

`offerable_values(project)` is what Save As New offers as the new item's defaults: filled-in
values only, never the server's own keys (part number, revision, the four stamps). The service
merges the offer onto the new revision as-is.

## The command shape

Every command is `def name(context)` and returns `None`:

```python
def check_in(context):
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.check_in(item_id, _to_upload(context))
    if not answer.get("success"):
        _refused(context, answer, "Check In")
```

- `_to_upload` → `host.upload_copy`: `project.write(path)` to the project's **own file**, returning
  that path. Never a temp copy — the service records the path as the item's home.
- `_hand_over(context, answer)`: remember the item, write values into the staged file, then either
  write the record into the **live project** (when the staged file is this project — Revise) or
  start a **new QGIS** on the file. Never `iface.addProject`, which would replace the user's project.
- `_apply(context, answer)`: write returned `attribute_mappings` into the live project.
- `run(name, project, hwnd)`: logs, turns any exception into a toast, lets only
  `ServiceUnavailable` escape for `plugin.py` to put in the message bar.

`plugin.py` calls `refresh_availability()` after every command, on `readProject`, `cleared` and
`fileNameChanged`, and on each menu's `aboutToShow`. It asks `client.me()` and
`identity.state_of()` and applies `availability.enabled_commands`; when the service is unreachable
everything stays enabled so the user meets the "tray is not running" message.

### Adding a command

1. Add `("my-command", "My Command...")` to `MENU` in `menu.py`, and place it in `TOOLBAR` (a
   plain button or inside a `Group`).
2. Add `def my_command(context)` in `commands.py`; register it in `COMMANDS`.
3. Put it in the right set in `availability.py` (`ALWAYS`, `SIGNED_IN`, `WITH_FILE`, `IN_PLM`, or a
   status rule) — `test_every_command_the_rule_names_exists` fails until you do.
4. Add `icons/my-command_16.png`, `_26`, `_50` from the standard set.
5. Add the client method if the endpoint is new — shapes from the service's `PlmModels.cs`.
6. `python plugin/build.py --install` and **restart QGIS** (plugin code is read at startup).

## Things QGIS does differently (all measured)

| | Consequence |
|---|---|
| Profile is `%APPDATA%\QGIS\QGIS4\profiles\default`, ini `QGIS\QGIS4.ini`. | Not `QGIS3`, whatever the QGIS 3 docs say. |
| A copied plugin is disabled until `[PythonPlugins] nexus_plm=true`. | `build.py` and the installer's `[INI]` section write it. |
| The title bar shows the project **metadata** title. | `write_values` / `write_into_file` set `<title>`, `projectname` and `<projectMetadata><title>`. Live `setMetadata` repaints at once. |
| Plugin code is read at start. | Reinstall → restart. Two windows can run two versions. |
| `qgis.bat <file>` starts a separate process. | `open_document` gives a second window; `iface.addProject` would replace the user's project. |
| `QgsProject.fileName()` = forward slashes, `""` when never saved. | `host.document_path` normalises to a Windows path or `None`. |
| The plugin call holds the UI thread. | QGIS reads "Not Responding" while a Nexus dialog is open; a UI Automation enumeration of the desktop hangs on it. Follow-up: run the call off-thread. |
| Headless PyQGIS works from `bin\python-qgis.bat` with `QgsApplication.setPrefixPath("…/apps/qgis", True)`. | That is how `tools/build_template.py` runs. Its `qgisSettingsDirPath()` is a *python* profile, not QGIS's. |
| `qgis-python-crash-info-<pid>` in `%LOCALAPPDATA%\Temp` is an empty placeholder written at every start. | Not an error. |

## Running the tests

```bash
python -m pytest tests/ -q
```

`tests/fakeqgis.py` stands up `Project` (custom properties, variables, file, title, metadata),
`Variables` and a minimal `.qgs`/`.qgz` writer. `plugin.py` cannot be imported without QGIS, so
`test_plugin.py` holds its **text** to the rules that matter (the table is the list, one action per
command, the refresh triggers, the icon lookup). The autouse fixture patches `host.LOG_PATH`,
`state._PATH`, `host.open_document`, `host.open_url` and `host.upload_copy`.

## The server side

On the Engine: MIME row `qgz` → `application/x-qgis-project` (`.qgz,.qgs`); numbering
`QgisProject` → `QGP-########-QGZ`; type `n5QgisProject` (cloned from a document type, twelve
connector mappings); template `QGIS Project.qgz` uploaded to the vault and attached. All through
the API; `POST /api/types` hot-registers. The New dialog grew a "Has QGIS template" filter by
itself — the service enumerates no hosts.

## Building the installer

```
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer\Nexus.PLM.QGIS.Addin.iss
```

Per user, no elevation, into the QGIS 4 default profile's `python\plugins\nexus_plm`, plus the
`[INI]` line that enables it (removed on uninstall). `tests/test_installer.py` holds the script
against the source: `AppVersion` == `commands.VERSION` == `metadata.txt`'s `version`, the paths ==
`build.py`'s, payload and uninstall scope. Bump all three versions together.

## Debugging

- Add-in log: `%APPDATA%\NexusPLM\Logs\plmqgisaddin.log`; QGIS's own Python errors: the "Python
  error" bar and `%APPDATA%\QGIS\QGIS4\profiles\default\python\...`.
- Document map: `%APPDATA%\NexusPLM\qgis-documents.json`.
- `curl http://localhost:5100/api/auth/me` — who the tray is signed in as.
- `curl "http://localhost:5100/plm/state?file_path=C:\Nexus\Staging\QGP-00000001-QGZ.qgz"` — what PLM thinks a file is.
- Plugin Reloader (a QGIS plugin) reloads ours without a restart during development.
