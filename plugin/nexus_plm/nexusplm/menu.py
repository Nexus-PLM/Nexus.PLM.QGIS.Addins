"""What appears in the Nexus PLM menu, and what each entry runs.

In its own module, away from the plugin entry point, for one reason: the entry point imports
``qgis`` and so can only be loaded inside QGIS. The menu is a plain table with no QGIS in it, and
keeping it here is what lets a test check that every entry has a command and every command has an
entry - the two lists that drift.
"""

#: The menu's title on QGIS's menu bar, beside Project, Edit, View... A menu of its own, as
#: LibreOffice, OpenOffice and GIMP give it: Nexus PLM is document management, not a plugin
#: feature, so it does not go under the Plugins menu where PyQGIS plugins land by default.
MENU_TITLE = "Nexus PLM"

#: The toolbar's title, for View > Toolbars.
TOOLBAR_TITLE = "Nexus PLM"

#: Every menu entry: the command :mod:`nexusplm.commands` dispatches on, and its label. ``None``
#: is a separator. Unlike GIMP and Inkscape, QGIS shows a menu in the order it was built, so this
#: order is the one the user sees - grouped the way every other Nexus add-in groups its toolbar.
MENU = [
    # Account
    ("sign-in",           "Sign In..."),
    ("sign-out",          "Sign Out"),
    None,
    # Data management
    ("new-from-template", "New from Template..."),
    ("open-from-plm",     "Open from PLM..."),
    ("search",            "Search..."),
    ("save-to-plm",       "Save to PLM"),
    ("save-as-new",       "Save As New Item..."),
    ("save-as-existing",  "Save As Existing Item..."),
    None,
    # Lifecycle
    ("check-out",         "Check Out"),
    ("check-in",          "Check In"),
    ("revise",            "Revise"),
    ("change-owner",      "Change Ownership..."),
    None,
    # Workflow
    ("worklist",          "My Worklist..."),
    ("new-workflow",      "New Workflow..."),
    None,
    # Attributes
    ("properties",        "Properties..."),
    ("edit-values",       "Edit Values..."),
    ("refresh-values",    "Refresh Values"),
    None,
    # Information
    ("settings",          "Current Settings..."),
    ("connection-status", "Connection Status"),
    ("help",              "Help"),
    ("about",             "About"),
]

#: The entries alone, separators dropped: ``(command, label)`` pairs.
ENTRIES = [entry for entry in MENU if entry is not None]

#: The label for each command.
LABELS = dict(ENTRIES)

#: Every command is on the toolbar, grouped by the same separators as the menu - the shape of
#: the LibreOffice and OpenOffice toolbars. It started as the eight everyday commands; Marc asked
#: for sign in and out "etc." to be there too, and the whole set is what the other hosts show.
TOOLBAR = [command for command, _label in ENTRIES]
