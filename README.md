# Nexus PLM for QGIS

Product lifecycle management from inside QGIS. A PyQGIS plugin that puts the same command set the
Nexus PLM add-ins give Word, LibreOffice, OpenOffice, ONLYOFFICE, Inkscape and GIMP into a
**Nexus PLM** menu of its own on QGIS's menu bar, with a toolbar for the everyday commands.

Twenty-one commands: sign in and out, create from a template, open and search the vault, save,
save as a new or an existing item, check out and in, revise, change ownership, worklist and
workflow, properties, edit and refresh attribute values, settings, connection status, help and
about.

Tested against QGIS **4.2.2** (Qt 6.11, PyQt 6.11, bundled Python 3.12).

## What it tracks

The **project** - `.qgz` (the zipped project, QGIS's default) or `.qgs` (the plain XML) - is the
dataset that goes in and out of the vault. Layers that reference data outside the project file are
the user's business, as they are for QGIS itself; the plugin tracks the primary dataset.

## Where the PLM values live

- **The record** is the project's own custom properties, scope `NexusPLM` - inside the project
  file, so the values travel with it wherever it goes, and preserved by QGIS through every save.
- **The display** is a set of project variables, `nexus_partnumber`, `nexus_revision`,
  `nexus_description`... A print-layout label reading `[% @nexus_partnumber %]` renders the part
  number on the printed sheet. The template's **Title Block** layout does exactly that. Nothing
  depends on the display; the record is the deliverable.

## Install

Run `NexusPlmQgisAddinSetup.exe` (per user, no admin rights). It copies the plugin into the QGIS 4
default profile and enables it; restart QGIS and the **Nexus PLM** menu appears before Help. The
Nexus PLM tray application (`Nexus.PLM.WPF.Addins`) must be running - the plugin talks only to
the Addin Service it hosts on `http://localhost:5100`, never to the Engine or the vault directly.

Developers: `python plugin\build.py --install`, then restart QGIS (or reload with the Plugin
Reloader).

## Layout

```
plugin/
  build.py                 installs into a QGIS profile and enables the plugin
  nexus_plm/
    __init__.py            classFactory - QGIS's entry point
    metadata.txt           what QGIS reads to list the plugin
    plugin.py              the menu, the toolbar, one action per command (the only qgis import)
    nexusplm/
      client.py            HTTP to the Addin Service       ] shared with the Inkscape and GIMP
      state.py             path -> item map                ] add-ins; no QGIS in any of them
      identity.py          which item a file is            ]
      navigator.py         folder tree shaping             ]
      menu.py              the menu table - no qgis, so tests can read it
      project.py           the PLM record and the display variables, live and in a file
      host.py              the parts that know they are inside QGIS
      commands.py          what each menu entry does
tools/build_template.py    makes dist\QGIS Project.qgz, the type's template (needs QGIS's Python)
tests/                     pytest with a fake QGIS; no QGIS needed
installer/                 Inno Setup script
```

## Tests

```
python -m pytest tests/ -q
```

## Licence

MIT - see `LICENSE`.
