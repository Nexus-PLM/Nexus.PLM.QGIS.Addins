"""Where a PLM value lives in a QGIS project.

Two homes, one record:

* **The record** is the project's own custom properties, under the scope ``NexusPLM``. QGIS
  stores custom properties inside the project file - ``<properties><properties name="NexusPLM">``
  in the ``.qgs`` XML, zipped into the ``.qgz`` - and preserves every scope it does not recognise,
  so the record travels with the project wherever the file goes. Measured on 4.2.2 before this was
  written: written, saved, re-read, present.
* **The display** is a set of project variables, ``nexus_<key>`` (``nexus_partnumber``,
  ``nexus_revision``...). A variable is what a print-layout label, a map decoration or a layer
  expression can show - ``[% @nexus_partnumber %]`` in a layout label renders the part number on
  the printed sheet - which is the QGIS shape of the Inkscape template's title block. Nothing here
  depends on anything showing it; the record is the deliverable, the display is a convenience.

The project object is passed in, never imported: :mod:`qgis` exists only inside QGIS, and every
function here is tested against ``tests/fakeqgis.py``. A staged file nothing has open yet is
edited as a file (:func:`write_into_file`), with ``zipfile`` and ``xml.etree`` and no QGIS at all.
"""

import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile

#: The custom-property scope the record lives in.
SCOPE = "NexusPLM"

#: The prefix of the project variables that show a value. Lower-cased key follows: a variable
#: name is used in expressions, and ``@nexus_partnumber`` reads better than ``@nexus_PartNumber``.
VARIABLE_PREFIX = "nexus_"

#: Keys PLM stamps itself. A project's copies of them are never offered back as the values of a
#: new item. Save As New merges whatever a caller offers straight onto the new revision (only
#: ``plm_`` keys are refused), so a project copied from another item would hand the new item its
#: old part number, and a template's empty record wiped ``createdBy`` and ``creationDate`` to ""
#: - measured on the Inkscape add-in, IND-00000007-SVG, 29 Sep 2026.
SYSTEM_KEYS = frozenset(k.lower() for k in (
    "PartNumber", "Revision", "CreatedBy", "CreationDate", "ModifiedBy", "ModificationDate"))


def variable_name(key):
    """The project variable that shows ``key``: ``PartNumber`` -> ``nexus_partnumber``."""
    return VARIABLE_PREFIX + re.sub(r"[^a-z0-9_]", "_", key.lower())


def for_display(value):
    """A value as it reads on a sheet: an ISO timestamp becomes its date, everything else is itself.

    ``2026-09-30T01:20:23.1099261Z`` is what the server stamps; ``2026-09-30`` is what a title
    block wants. The record keeps the full value - only the display is shortened.
    """
    text = "" if value is None else str(value)
    match = re.match(r"^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}", text)
    return match.group(1) if match else text


# ── the live project ─────────────────────────────────────────────────────────

def read_values(project):
    """Every PLM value recorded in the project, as ``{key: text}``.

    A project that has never been in PLM has no ``NexusPLM`` scope, which is not an error and
    answers an empty dict.
    """
    values = {}
    for key in project.entryList(SCOPE, ""):
        text, found = project.readEntry(SCOPE, key, "")
        if found:
            values[key] = text
    return values


def offerable_values(project):
    """The project's values a new item may take as defaults: filled in, and not PLM's own.

    An empty entry is a slot the template left for PLM to fill, not a value of ""; offering it as
    "" is how the blanks above were written. And the identity and stamp keys belong to the server
    whatever the project says.
    """
    return {key: value for key, value in read_values(project).items()
            if value and key.lower() not in SYSTEM_KEYS}


def write_values(project, values, variables=None):
    """Record ``values`` in the project and show them through its variables.

    Returns ``(recorded, shown)``: how many values went into the record and how many project
    variables were set. The two are reported separately so a user hunting for a value on a layout
    is told the record has it even when nothing displays it.

    ``variables`` is ``QgsExpressionContextUtils``, passed in so this can be tested without QGIS.
    ``None`` inside QGIS means "import it"; ``None`` in a test means the fake project's own
    ``setProjectVariable`` is used.
    """
    if not values:
        return 0, 0

    recorded = 0
    for key, value in values.items():
        project.writeEntry(SCOPE, key, "" if value is None else str(value))
        recorded += 1

    shown = 0
    setter = _variable_setter(project, variables)
    if setter is not None:
        for key, value in values.items():
            setter(project, variable_name(key), for_display(value))
            shown += 1

    _title_by_part_number(project, values)
    project.setDirty(True)
    return recorded, shown


def _title_by_part_number(project, values):
    """Name the project after its part number, so the window says which item it is.

    QGIS titles a window by the project's title when it has one and by the file name otherwise.
    A template carries a title ("Nexus PLM project"), so every project made from it opened as
    "Nexus PLM project - QGIS" - Marc could not tell the windows apart. The part number is the
    one name every other Nexus host shows in its title bar.
    """
    part_number = values.get("PartNumber")
    if part_number and hasattr(project, "setTitle"):
        project.setTitle(str(part_number))


def _variable_setter(project, variables):
    """``QgsExpressionContextUtils.setProjectVariable`` or a stand-in, or ``None`` when neither."""
    if variables is not None:
        return variables.setProjectVariable
    try:
        from qgis.core import QgsExpressionContextUtils
        return QgsExpressionContextUtils.setProjectVariable
    except ImportError:
        setter = getattr(project, "setProjectVariable", None)
        if setter is None:
            return None
        return lambda _project, name, value: setter(name, value)


# ── a project file nothing has open ───────────────────────────────────────────

#: The XML element the record lives in, and the one the variables live in.
_PROPERTIES = "properties"
_VARIABLES = "Variables"


def write_into_file(path, values):
    """Put ``values`` into a project **file**, for a project QGIS has not opened yet.

    New from Template and Open from PLM stage a file and then open it; the record has to be in the
    file before that, or the project arrives carrying nothing for an item PLM has just numbered.
    Works on ``.qgz`` (the ``.qgs`` member is rewritten and every other member - the styles
    database - copied through untouched) and on a plain ``.qgs``.

    Returns ``(recorded, shown)`` as :func:`write_values` does.
    """
    if not path or not values:
        return 0, 0

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [(info, archive.read(info.filename)) for info in archive.infolist()]
        name = next((info.filename for info, _ in members if info.filename.lower().endswith(".qgs")), None)
        if name is None:
            raise ValueError("%s holds no .qgs project" % path)
        rewritten = []
        counts = (0, 0)
        for info, payload in members:
            if info.filename == name:
                payload, counts = _write_into_xml(payload, values)
            rewritten.append((info, payload))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
            for info, payload in rewritten:
                out.writestr(info.filename, payload)
        with open(path, "wb") as handle:
            handle.write(buffer.getvalue())
        return counts

    with open(path, "rb") as handle:
        payload = handle.read()
    payload, counts = _write_into_xml(payload, values)
    with open(path, "wb") as handle:
        handle.write(payload)
    return counts


def read_from_file(path):
    """The record in a project file, as :func:`read_values` reads it from a live project."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            name = next((n for n in archive.namelist() if n.lower().endswith(".qgs")), None)
            payload = archive.read(name) if name else b""
    else:
        with open(path, "rb") as handle:
            payload = handle.read()
    if not payload:
        return {}
    root = ET.fromstring(payload)
    block = _scope_block(root, SCOPE, create=False)
    if block is None:
        return {}
    return {child.get("name"): (child.text or "") for child in block if child.get("name")}


def _write_into_xml(payload, values):
    root = ET.fromstring(payload)
    record = _scope_block(root, SCOPE, create=True)
    shown_in = _scope_block(root, _VARIABLES, create=True)

    recorded = 0
    for key, value in values.items():
        _set_property(record, key, "" if value is None else str(value))
        recorded += 1

    # QGIS keeps project variables as two parallel lists under <Variables>: variableNames and
    # variableValues, each a <value> per variable. Written the same way so QGIS reads them back.
    names = _list_property(shown_in, "variableNames")
    texts = _list_property(shown_in, "variableValues")
    existing = [v.text or "" for v in names]
    shown = 0
    for key, value in values.items():
        name = variable_name(key)
        text = for_display(value)
        if name in existing:
            texts[existing.index(name)].text = text
        else:
            ET.SubElement(names, "value").text = name
            ET.SubElement(texts, "value").text = text
            existing.append(name)
        shown += 1

    # The window title, as _title_by_part_number does for a live project. QGIS keeps the title in
    # <title> and mirrors it in the root's projectname attribute.
    part_number = values.get("PartNumber")
    if part_number:
        title = root.find("title")
        if title is None:
            title = ET.SubElement(root, "title")
        title.text = str(part_number)
        root.set("projectname", str(part_number))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), (recorded, shown)


def _scope_block(root, scope, create):
    properties = root.find(_PROPERTIES)
    if properties is None:
        if not create:
            return None
        properties = ET.SubElement(root, _PROPERTIES)
    for child in properties.findall(_PROPERTIES):
        if child.get("name") == scope:
            return child
    if not create:
        return None
    block = ET.SubElement(properties, _PROPERTIES)
    block.set("name", scope)
    return block


def _set_property(block, key, text):
    for child in block.findall(_PROPERTIES):
        if child.get("name") == key:
            child.text = text
            child.set("type", "QString")
            return
    element = ET.SubElement(block, _PROPERTIES)
    element.set("name", key)
    element.set("type", "QString")
    element.text = text


def _list_property(block, key):
    for child in block.findall(_PROPERTIES):
        if child.get("name") == key:
            return child
    element = ET.SubElement(block, _PROPERTIES)
    element.set("name", key)
    element.set("type", "QStringList")
    return element


def is_project_file(path):
    """Whether a path names a QGIS project by extension."""
    return bool(path) and os.path.splitext(path)[1].lower() in (".qgz", ".qgs")
