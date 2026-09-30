"""Build the QGIS project template the ``n5QgisProject`` type hands out.

Run under QGIS's own Python, which is the only one with ``qgis`` in it:

    "C:\\Program Files\\QGIS 4.2.2\\bin\\python-qgis.bat" tools\\build_template.py

Writes ``dist\\QGIS Project.qgz``: an empty project (no layers - a template must not depend on
data that is not on the user's machine) that carries

* the **PLM record**, every key the type maps as an empty slot under ``NexusPLM``, so a user can
  see in Project Properties > Variables where PLM's values will land;
* the **display variables**, ``nexus_*``, empty, so a layout label bound to them renders "" and
  not an expression error until PLM fills them;
* a **print layout, "Title Block"**, whose labels read the variables - the QGIS shape of the
  Inkscape template's title block. Export it and the sheet carries the part number, revision,
  description and date PLM wrote.

Developer-only: this is how the template was made, kept so it can be remade. It is not shipped.
"""

import os
import sys

from qgis.core import (QgsApplication, QgsExpressionContextUtils, QgsLayoutItemLabel,
                       QgsLayoutItemShape, QgsLayoutPoint, QgsLayoutSize, QgsPrintLayout,
                       QgsProject, QgsUnitTypes)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "dist", "QGIS Project.qgz")

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "plugin", "nexus_plm"))
from nexusplm import project as record                                # noqa: E402

#: Every key the type maps, in the order the sheet shows them.
KEYS = ["PartNumber", "Revision", "Description", "CreatedBy", "CreationDate",
        "ModifiedBy", "ModificationDate", "Department", "Author", "Priority", "Approved"]

#: The title block: (caption, key) per cell, four columns by two rows on an A4 landscape sheet.
CELLS = [("PART NUMBER", "PartNumber"), ("REV", "Revision"), ("DESCRIPTION", "Description"),
         ("DATE", "CreationDate"), ("AUTHOR", "Author"), ("DEPARTMENT", "Department"),
         ("PRIORITY", "Priority"), ("APPROVED", "Approved")]


def main():
    QgsApplication.setPrefixPath(os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "apps", "qgis"), True)
    app = QgsApplication([], False)
    app.initQgis()

    project = QgsProject.instance()
    project.setTitle("Nexus PLM project")
    md = project.metadata()
    md.setTitle("Nexus PLM project")
    md.setAbstract("Created from the Nexus PLM QGIS template. PLM writes its values into the "
                   "NexusPLM project properties and the nexus_* variables; the Title Block layout "
                   "shows them.")
    project.setMetadata(md)

    # Empty slots, so the record's shape is visible before PLM fills it.
    for key in KEYS:
        project.writeEntry(record.SCOPE, key, "")
        QgsExpressionContextUtils.setProjectVariable(project, record.variable_name(key), "")

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName("Title Block")
    page = layout.pageCollection().page(0)
    page.setPageSize("A4", page.Landscape)

    # A frame along the bottom of the sheet, then a caption and a value label per cell.
    left, top, width, height = 10.0, 160.0, 277.0, 40.0
    frame = QgsLayoutItemShape(layout)
    frame.setShapeType(QgsLayoutItemShape.Rectangle)
    frame.attemptMove(QgsLayoutPoint(left, top, QgsUnitTypes.LayoutMillimeters))
    frame.attemptResize(QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(frame)

    columns, rows = 4, 2
    cell_w, cell_h = width / columns, height / rows
    for index, (caption, key) in enumerate(CELLS):
        column, row = index % columns, index // columns
        x, y = left + column * cell_w, top + row * cell_h
        head = QgsLayoutItemLabel(layout)
        head.setText(caption)
        head.attemptMove(QgsLayoutPoint(x + 2, y + 1.5, QgsUnitTypes.LayoutMillimeters))
        head.attemptResize(QgsLayoutSize(cell_w - 4, 6, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(head)
        value = QgsLayoutItemLabel(layout)
        value.setText("[% @" + record.variable_name(key) + " %]")
        value.setId("nexus:" + key)
        value.attemptMove(QgsLayoutPoint(x + 2, y + 8, QgsUnitTypes.LayoutMillimeters))
        value.attemptResize(QgsLayoutSize(cell_w - 4, cell_h - 10, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(value)

    project.layoutManager().addLayout(layout)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if not project.write(OUT):
        raise SystemExit("could not write " + OUT)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
    print("record slots:", record.read_from_file(OUT))
    app.exitQgis()


if __name__ == "__main__":
    main()
