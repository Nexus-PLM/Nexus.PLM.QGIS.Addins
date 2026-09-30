"""The QGIS half of the plugin: a Nexus PLM menu and toolbar, and one action per command.

This is the only module that imports ``qgis`` and ``PyQt`` at the top, and it does nothing but
build widgets, hand each click to :func:`nexusplm.commands.run`, and keep every action's enabled
state in step with what the service says. Every decision - what a command does, what the record
looks like, which commands apply right now - is elsewhere, where it can be tested without QGIS.

**A plugin lands in the Plugins menu by default**, and this one does not: Nexus PLM is document
management, not a plugin feature, so it gets a menu of its own on the menu bar - as LibreOffice,
OpenOffice and GIMP give it - inserted before Help so it reads as part of the application.

**The toolbar is the LibreOffice toolbar**: a few plain buttons and several that drop a menu down
(:data:`nexusplm.menu.TOOLBAR`), with the same icons, so every host presents the same face. One
``QAction`` per command is shared by the menu and the toolbar, so enabling or disabling it does
both at once.
"""

import os
import sys

# The package sits beside this file. QGIS puts the plugin's own directory on sys.path, but a
# plugin that works only because of that convenience breaks the first time it is imported from
# somewhere else (the tests, a console session).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qgis.core import QgsProject                                       # noqa: E402
from qgis.PyQt.QtCore import QSize, QTimer                             # noqa: E402
from qgis.PyQt.QtGui import QAction, QIcon                             # noqa: E402
from qgis.PyQt.QtWidgets import QMenu, QToolButton                     # noqa: E402

from nexusplm import availability, commands, host, identity            # noqa: E402
from nexusplm.client import Client, DEFAULT_BASE_URL, ServiceUnavailable  # noqa: E402
from nexusplm.menu import Group, MENU, MENU_TITLE, TOOLBAR, TOOLBAR_TITLE  # noqa: E402

TRAY_IS_DOWN = (
    "Cannot reach Nexus PLM on %s. Nothing can be saved to or read from PLM until the Nexus PLM "
    "tray application is running. Start it from the Start menu and run the command again."
    % DEFAULT_BASE_URL
)

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

#: The sizes the standard Nexus icon set is drawn at - the same PNGs the LibreOffice and
#: OpenOffice add-ins ship, so every host shows the same pictures. Marc: "can't we use the
#: standard set of icons we used in the other addins".
ICON_SIZES = (16, 26, 50)


class NexusPlmPlugin:
    """Every Nexus PLM command QGIS can run, as actions in a menu and a toolbar."""

    def __init__(self, iface):
        self.iface = iface
        self.menu = None
        self.toolbar = None
        self.actions = {}
        self.group_buttons = []

    # ── QGIS calls these ─────────────────────────────────────────────────────

    def initGui(self):                                                # noqa: N802 - QGIS's name
        window = self.iface.mainWindow()

        # One action per command, built from the menu table - the one list of what exists.
        for entry in MENU:
            if entry is None:
                continue
            command, label = entry
            action = QAction(_icon(command), label, window)
            action.setObjectName("nexusPlm_" + command.replace("-", "_"))
            action.setStatusTip("Nexus PLM: " + label.rstrip("."))
            # A default argument, not a closure over the loop variable: every action would
            # otherwise run the last command in the table.
            action.triggered.connect(lambda checked=False, name=command: self.run(name))
            self.actions[command] = action

        # The menu, in the table's order and with its separators.
        self.menu = QMenu(MENU_TITLE, window.menuBar())
        for entry in MENU:
            if entry is None:
                self.menu.addSeparator()
            else:
                self.menu.addAction(self.actions[entry[0]])
        self.menu.aboutToShow.connect(self.refresh_availability)
        # Before Help, so the menu reads as part of QGIS rather than an afterthought at the end.
        help_action = _help_menu_action(window.menuBar())
        if help_action is not None:
            window.menuBar().insertMenu(help_action, self.menu)
        else:
            window.menuBar().addMenu(self.menu)

        # The toolbar: plain buttons, dropdown groups, separators.
        self.toolbar = self.iface.addToolBar(TOOLBAR_TITLE)
        self.toolbar.setObjectName("NexusPlmToolbar")
        for item in TOOLBAR:
            if item is None:
                self.toolbar.addSeparator()
            elif isinstance(item, Group):
                self.toolbar.addWidget(self._group_button(item))
            else:
                self.toolbar.addAction(self.actions[item])

        # What applies right now, and again whenever it could have changed: another project, a
        # save under a new name, the project cleared, or one of our own commands having run.
        project = QgsProject.instance()
        for signal in (project.readProject, project.cleared, project.fileNameChanged):
            try:
                signal.connect(self._on_project_changed)
            except Exception:                                          # noqa: BLE001
                pass
        QTimer.singleShot(0, self.refresh_availability)

    def unload(self):
        if self.menu is not None:
            self.menu.menuAction().setVisible(False)
            self.iface.mainWindow().menuBar().removeAction(self.menu.menuAction())
            self.menu.deleteLater()
            self.menu = None
        if self.toolbar is not None:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None
        self.actions = {}
        self.group_buttons = []

    # ── the toolbar's dropdown buttons ───────────────────────────────────────

    def _group_button(self, group):
        button = QToolButton(self.toolbar)
        button.setObjectName("nexusPlmGroup_" + group.key)
        button.setIcon(_icon("group-" + group.key))
        button.setText(group.label)          # not drawn (icon-only toolbar) but read by accessibility
        button.setToolTip("Nexus PLM: " + group.label)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(group.label, button)
        for command in group.commands:
            if command is None:
                menu.addSeparator()
            else:
                menu.addAction(self.actions[command])
        menu.aboutToShow.connect(self.refresh_availability)
        button.setMenu(menu)
        self.group_buttons.append(button)
        return button

    # ── running a command ─────────────────────────────────────────────────────

    def run(self, command):
        try:
            commands.run(command, QgsProject.instance(), hwnd=host.window_handle(self.iface))
        except ServiceUnavailable:
            host.log("%s: the tray application is not running" % command)
            # QGIS's own message bar, because the thing that draws the tray's toasts is the thing
            # that is down.
            self.iface.messageBar().pushWarning("Nexus PLM", TRAY_IS_DOWN)
        finally:
            self.refresh_availability()

    # ── what applies right now ────────────────────────────────────────────────

    def _on_project_changed(self, *_args):
        self.refresh_availability()

    def refresh_availability(self):
        """Enable exactly the commands that apply, per :func:`nexusplm.availability.enabled_commands`.

        Asks the service who is signed in and what this project is. When the service cannot be
        reached everything stays enabled: the user then gets the "tray is not running" message
        from whatever they click, which is the one thing worth telling them, and a toolbar greyed
        out for a reason it cannot show would only look broken.
        """
        if not self.actions:
            return
        client = Client()
        path = host.document_path(QgsProject.instance())
        try:
            who = client.me()
            user = who.get("username") if who.get("success") else None
            state = identity.state_of(client, path) if (user and path) else None
        except ServiceUnavailable:
            allowed = set(self.actions)
        except Exception as error:                                     # noqa: BLE001
            host.log("availability: %r" % (error,))
            allowed = set(self.actions)
        else:
            allowed = availability.enabled_commands(state, user=user, path=path)
        for command, action in self.actions.items():
            action.setEnabled(command in allowed)


def _icon(name):
    """The icon at every size it is drawn at, or an empty icon when none is shipped."""
    icon = QIcon()
    for size in ICON_SIZES:
        path = os.path.join(ICONS, "%s_%d.png" % (name, size))
        if os.path.isfile(path):
            icon.addFile(path, QSize(size, size))
    return icon


def _help_menu_action(menu_bar):
    """The Help menu's action on the menu bar, or ``None`` if QGIS renamed it."""
    for action in menu_bar.actions():
        if action.menu() is not None and action.text().replace("&", "") == "Help":
            return action
    return None
