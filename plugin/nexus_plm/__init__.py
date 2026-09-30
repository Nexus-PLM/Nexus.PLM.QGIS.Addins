"""The Nexus PLM plugin for QGIS.

QGIS loads a plugin by importing its package and calling ``classFactory(iface)``. Everything else
is in :mod:`nexus_plm.plugin`, imported here and not at the top of this file, so that the package
can be imported by the tests without ``qgis`` present.
"""


def classFactory(iface):                                             # noqa: N802 - QGIS's name
    """QGIS's entry point: build the plugin for this window."""
    from .plugin import NexusPlmPlugin
    return NexusPlmPlugin(iface)
