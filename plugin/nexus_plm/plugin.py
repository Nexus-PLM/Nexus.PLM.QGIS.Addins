"""The QGIS half of the plugin: a Nexus PLM menu and toolbar, and one action per command.

This is the only module that imports ``qgis`` and ``PyQt`` at the top, and it does nothing but
build widgets and hand each click to :func:`nexusplm.commands.run`. Every decision - what a
command does, what the record looks like, what to say - is elsewhere, where it can be tested
without QGIS.

**A plugin lands in the Plugins menu by default**, and this one does not: Nexus PLM is document
management, not a plugin feature, so it gets a menu of its own on the menu bar - as LibreOffice,
OpenOffice and GIMP give it - inserted before Help so it reads as part of the application.
"""

import os
import sys

# The package sits beside this file. QGIS puts the plugin's own directory on sys.path, but a
# plugin that works only because of that convenience breaks the first time it is imported from
# somewhere else (the tests, a console session).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qgis.core import QgsProject                                       # noqa: E402
from qgis.PyQt.QtCore import QSize                                     # noqa: E402
from qgis.PyQt.QtGui import QAction, QIcon                             # noqa: E402
from qgis.PyQt.QtWidgets import QMenu, QToolBar                        # noqa: E402

from nexusplm import commands, host                                    # noqa: E402
from nexusplm.client import DEFAULT_BASE_URL, ServiceUnavailable      # noqa: E402
from nexusplm.menu import ENTRIES, MENU, MENU_TITLE, TOOLBAR, TOOLBAR_TITLE  # noqa: E402

TRAY_IS_DOWN = (
    "Cannot reach Nexus PLM on %s. Nothing can be saved to or read from PLM until the Nexus PLM "
    "tray application is running. Start it from the Start menu and run the command again."
    % DEFAULT_BASE_URL
)

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


class NexusPlmPlugin:
    """Every Nexus PLM command QGIS can run, as actions in a menu and a toolbar."""

    def __init__(self, iface):
        self.iface = iface
        self.menu = None
        self.toolbar = None
        self.actions = {}

    # ── QGIS calls these ─────────────────────────────────────────────────────

    def initGui(self):                                                # noqa: N802 - QGIS's name
        window = self.iface.mainWindow()
        self.menu = QMenu(MENU_TITLE, window.menuBar())
        self.toolbar = self.iface.addToolBar(TOOLBAR_TITLE)
        self.toolbar.setObjectName("NexusPlmToolbar")

        for entry in MENU:
            if entry is None:
                self.menu.addSeparator()
                continue
            command, label = entry
            action = QAction(_icon(command), label, window)
            action.setObjectName("nexusPlm_" + command.replace("-", "_"))
            action.setStatusTip("Nexus PLM: " + label.rstrip("."))
            # A default argument, not a closure over the loop variable: every action would
            # otherwise run the last command in the table.
            action.triggered.connect(lambda checked=False, name=command: self.run(name))
            self.menu.addAction(action)
            if command in TOOLBAR:
                self.toolbar.addAction(action)
            self.actions[command] = action

        # Before Help, so the menu reads as part of QGIS rather than an afterthought at the end.
        help_action = _help_menu_action(window.menuBar())
        if help_action is not None:
            window.menuBar().insertMenu(help_action, self.menu)
        else:
            window.menuBar().addMenu(self.menu)

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

    # ── running a command ─────────────────────────────────────────────────────

    def run(self, command):
        try:
            commands.run(command, QgsProject.instance(), hwnd=host.window_handle(self.iface))
        except ServiceUnavailable:
            host.log("%s: the tray application is not running" % command)
            # QGIS's own message bar, because the thing that draws the tray's toasts is the thing
            # that is down.
            self.iface.messageBar().pushWarning("Nexus PLM", TRAY_IS_DOWN)


#: The sizes the standard Nexus icon set is drawn at - the same PNGs the LibreOffice and
#: OpenOffice add-ins ship, so every host shows the same pictures. Marc: "can't we use the
#: standard set of icons we used in the other addins".
ICON_SIZES = (16, 26, 50)


def _icon(command):
    """The command's icon at every size it is drawn at, or an empty icon when none is shipped."""
    icon = QIcon()
    for size in ICON_SIZES:
        path = os.path.join(ICONS, "%s_%d.png" % (command, size))
        if os.path.isfile(path):
            icon.addFile(path, QSize(size, size))
    return icon


def _help_menu_action(menu_bar):
    """The Help menu's action on the menu bar, or ``None`` if QGIS renamed it."""
    for action in menu_bar.actions():
        if action.menu() is not None and action.text().replace("&", "") == "Help":
            return action
    return None
