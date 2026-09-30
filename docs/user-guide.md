# Nexus PLM for QGIS — user guide

Everything is in the **Nexus PLM** menu and on the **Nexus PLM** toolbar. Every dialog you see
belongs to the Nexus PLM tray application; the same dialogs appear in every other Nexus PLM
add-in, so what you learn here holds in Inkscape, GIMP and the office suites too.

## Before you start

1. The **Nexus PLM tray application** must be running (the tray icon near the clock). If it is
   not, every command says so in QGIS's message bar and stops.
2. **Sign In…** (the Account ▾ button) once. The session is shared by every Nexus add-in on the
   machine and is kept between QGIS sessions; **Connection Status** tells you who is signed in.

## The toolbar

![The toolbar](toolbar.png)

Left to right: **Account ▾** (Sign In, Sign Out) · New from Template · Open from PLM · Search ·
**Save ▾** (Save to PLM, Save As New Item, Save As Existing Item) · **Tasks ▾** (Check Out, Check
In, Revise, Change Ownership) · **Workflow ▾** (My Worklist, New Workflow) · Properties ·
**Values ▾** (Edit Values, Refresh Values) · **Nexus PLM ▾** (Settings, Connection Status, Help,
About). The menu has the same commands in the same groups.

**A greyed-out command is one that does not apply right now** — not a fault. Check In is grey
until you have checked the project out; Check Out is grey while it is checked out; Sign In is grey
while you are signed in; nothing acts on a project that has never been saved. The state refreshes
when a project is opened, after every command, and each time you open a menu.

## The project is the item

A project becomes a PLM item in one of three ways:

- **New from Template…** — pick a type, PLM numbers the item, and the type's template opens **in a
  new QGIS window** with the part number, revision, description and dates already in it. Your
  current project is left alone.
- **Open from PLM…** / **Search…** — browse or search the vault; the project you pick opens in a
  new QGIS window.
- **Save As New Item…** — register the project you have open as a new item. **Save As Existing
  Item…** gives its content to an item that already exists instead.

From then on the add-in knows which item the file is, whichever way you open it, and the window
title is the part number.

## Working on an item

| Command | What it does |
|---|---|
| **Check Out** | Takes the lock. Nobody else can change the item while you hold it. |
| **Save to PLM** | Saves the project and uploads it as a new version of the revision. You keep the lock. |
| **Check In** | Saves, uploads and releases the lock. You can leave a comment. |
| **Revise** | Starts the next revision — major (A → B) or minor (A → A.001), as the type allows. **The project you are in becomes the new revision**; the values update in place, nothing new opens. |
| **Change Ownership…** | Hands the item to another user. |
| **Properties…** | The item's full card: revisions, workflows, history, approvers, attachments. |
| **Edit Values…** | Edit the item's attributes. Values PLM owns are shown locked; the ones the project owns are editable. What you save is written into the project. |
| **Refresh Values** | Re-read the item's attributes from PLM into the project. |
| **My Worklist…** / **New Workflow…** | What PLM is waiting on you for; start a workflow on this item (this is how a revision gets Released). |

## Where the values go

Every attribute the type maps is written **into the project file itself**, as project properties
(Project ▸ Properties… ▸ Variables shows the `nexus_*` ones). The file carries its part number and
revision wherever it goes, and PLM reads them back from it.

To **show** a value on a printed map, put a label in a print layout with an expression such as
`[% @nexus_partnumber %]`, `[% @nexus_revision %]`, `[% @nexus_description %]` or
`[% @nexus_creationdate %]`. The template's **Title Block** layout (Project ▸ Layouts) is built
exactly this way — export it and the sheet carries what PLM wrote.

QGIS marks the project modified after a Nexus command wrote values into it; save it (Ctrl+S) when
you are done, as you normally would.

## Session and information

**Sign In…** / **Sign Out** · **Current Settings…** (staging folder, service port, where the
service connects) · **Connection Status** (is the service up, who is signed in) · **Help** (this
project's page) · **About** (add-in and service versions).

## If something does not work

- *"Cannot reach Nexus PLM on http://localhost:5100"* in the message bar — start the Nexus PLM
  tray application. Every command stays enabled until it is up, so you get this message rather
  than a greyed-out toolbar.
- *"This project is not registered in PLM"* — the file is not an item yet. Use **Save As New
  Item…** or open the item from PLM.
- *"Save this project to a file first"* — a never-saved project has no file for PLM to take.
- **No Nexus PLM menu** — Plugins ▸ Manage and Install Plugins ▸ Installed: tick **Nexus PLM**.
  The installer does this; a hand copy does not.
- **QGIS says "Not Responding" while a Nexus dialog is open** — it is waiting for the dialog. Finish
  or cancel the dialog and it returns.
- The add-in's log is `%APPDATA%\NexusPLM\Logs\plmqgisaddin.log`.
