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

class Group(object):
    """A toolbar button that drops a menu down: the LibreOffice toolbar's "stacked" buttons.

    ``key`` names the icon (``icons/group-<key>_<size>.png``), ``label`` is the tooltip, and
    ``commands`` are the menu's entries in order, ``None`` a separator.
    """

    def __init__(self, key, label, commands):
        self.key = key
        self.label = label
        self.commands = commands


#: The toolbar, in order. A string is a plain button for that command, a :class:`Group` a button
#: with a dropdown, ``None`` a separator. It is the LibreOffice and OpenOffice toolbar exactly
#: (``nexusplm_controllers.STACKS`` there), so every host presents the same face; Marc asked for
#: the sign in/out group and the dropdowns after seeing the flat first version.
TOOLBAR = [
    Group("account", "Account", ["sign-in", "sign-out"]),
    None,
    "new-from-template",
    "open-from-plm",
    "search",
    Group("save", "Save", ["save-to-plm", "save-as-new", "save-as-existing"]),
    None,
    Group("tasks", "Tasks", ["check-out", "check-in", None, "revise", None, "change-owner"]),
    Group("workflow", "Workflow", ["worklist", "new-workflow"]),
    None,
    "properties",
    Group("values", "Values", ["edit-values", "refresh-values"]),
    None,
    Group("about", "Nexus PLM", ["settings", "connection-status", None, "help", "about"]),
]


def toolbar_commands():
    """Every command the toolbar reaches, in order - plain buttons and dropdown entries alike."""
    commands = []
    for item in TOOLBAR:
        if isinstance(item, Group):
            commands.extend(c for c in item.commands if c is not None)
        elif item is not None:
            commands.append(item)
    return commands


#: The group keys, for the icon files that must exist.
GROUP_KEYS = [item.key for item in TOOLBAR if isinstance(item, Group)]
