"""Just enough of QGIS for the tests: a project with custom properties, variables and a file.

The add-in reaches QGIS through the ``project`` object it is handed and nothing else, so a fake
project is all the tests need. It mirrors the real API's shapes exactly - ``readEntry`` answers a
``(value, found)`` pair, ``entryList`` takes a scope and a key - because a fake that is easier
than the real thing proves nothing.
"""

import os


class Project:
    """Stands in for ``QgsProject``: custom properties by scope, variables, a file name."""

    def __init__(self, path=None, entries=None):
        self._entries = {}                     # scope -> {key: value}
        for scope, values in (entries or {}).items():
            self._entries[scope] = dict(values)
        self.variables = {}                    # what setProjectVariable recorded
        self._path = path or ""
        self.dirty = False
        self.written_to = []                   # every path write() was asked for

    # ── custom properties ────────────────────────────────────────────────────

    def writeEntry(self, scope, key, value):                          # noqa: N802
        self._entries.setdefault(scope, {})[key] = value
        return True

    def readEntry(self, scope, key, default=""):                      # noqa: N802
        values = self._entries.get(scope, {})
        if key in values:
            return values[key], True
        return default, False

    def entryList(self, scope, key=""):                               # noqa: N802
        return sorted(self._entries.get(scope, {}))

    def removeEntry(self, scope, key):                                # noqa: N802
        self._entries.get(scope, {}).pop(key, None)
        return True

    # ── variables (QgsExpressionContextUtils.setProjectVariable, bound to this project) ──

    def setProjectVariable(self, name, value):                        # noqa: N802
        self.variables[name] = value

    # ── file ─────────────────────────────────────────────────────────────────

    def fileName(self):                                               # noqa: N802
        return self._path

    def write(self, path=None):
        target = path or self._path
        if not target:
            return False
        self.written_to.append(target)
        with open(target, "wb") as handle:
            handle.write(b"<!DOCTYPE qgis><qgis version='fake'><properties/></qgis>")
        self._path = target
        self.dirty = False
        return True

    def setDirty(self, dirty=True):                                   # noqa: N802
        self.dirty = dirty

    def setTitle(self, title):                                        # noqa: N802
        self.title = title


class Variables:
    """Stands in for ``QgsExpressionContextUtils``: the static ``setProjectVariable``."""

    @staticmethod
    def setProjectVariable(project, name, value):                     # noqa: N802
        project.setProjectVariable(name, value)


def minimal_qgs(extra=""):
    """A project file body as QGIS 4 writes it, trimmed to what the record code touches."""
    return ("<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
            "<qgis version=\"4.2.2-Belém do Pará\" projectname=\"\">\n"
            "  <title></title>\n"
            "  <properties>\n"
            "    <properties name=\"Gui\">\n"
            "      <properties name=\"CanvasColorBluePart\" type=\"int\">255</properties>\n"
            "    </properties>\n" + extra +
            "  </properties>\n"
            "</qgis>\n").encode("utf-8")


def write_qgz(path, qgs_bytes):
    """A .qgz as QGIS writes it: the .qgs beside a styles database."""
    import zipfile
    stem = os.path.splitext(os.path.basename(path))[0]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(stem + ".qgs", qgs_bytes)
        archive.writestr("styles.db", b"SQLite format 3\x00" + b"\x00" * 32)
    return path
