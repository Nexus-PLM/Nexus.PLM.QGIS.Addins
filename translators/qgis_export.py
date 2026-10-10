"""
qgis_export.py - Headless QGIS: open the project named by QGIS_INPUT and export it to the
format implied by QGIS_OUTPUT's extension:

  .pdf   the project's first print layout (or, when it has none, the map itself on one page)
  .png   the map canvas rendered over the layers' full extent
  .gpkg  every vector layer packaged into one GeoPackage, one table per layer

Run under QGIS's bundled interpreter (python-qgis.bat), which sets the OSGeo4W environment.
Paths travel through environment variables, the same contract as the FreeCAD and GIMP scripts.
ASCII only: console output goes through the system code page.
"""
import os
import sys


def fail(message):
    sys.stderr.write("ERROR: " + message + "\n")
    sys.exit(1)


def main():
    input_path = os.environ.get("QGIS_INPUT")
    output_path = os.environ.get("QGIS_OUTPUT")
    if not input_path or not output_path:
        fail("QGIS_INPUT and QGIS_OUTPUT must be set")

    # Offscreen: a Windows service has no desktop, and rendering needs a QGuiApplication.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import (
        QgsApplication, QgsProject, QgsLayoutExporter, QgsMapSettings,
        QgsMapRendererCustomPainterJob, QgsVectorLayer, QgsVectorFileWriter,
        QgsLayout, QgsLayoutItemMap, QgsLayoutSize, QgsCoordinateTransformContext,
    )
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QImage, QPainter, QColor

    prefix = os.environ.get("QGIS_PREFIX_PATH")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        project = QgsProject.instance()
        if not project.read(input_path):
            fail("could not read project: " + input_path)

        ext = os.path.splitext(output_path)[1].lower()
        if ext == ".pdf":
            export_pdf(project, output_path, QgsLayoutExporter, QgsLayout, QgsLayoutItemMap,
                       QgsLayoutSize)
        elif ext == ".png":
            export_png(project, output_path, QgsMapSettings, QgsMapRendererCustomPainterJob,
                       QSize, QImage, QPainter, QColor)
        elif ext == ".gpkg":
            export_gpkg(project, output_path, QgsVectorLayer, QgsVectorFileWriter,
                        QgsCoordinateTransformContext)
        else:
            fail("unsupported output extension " + ext)

        if not os.path.exists(output_path):
            fail("export produced no file")
        print("Exported " + ext + " -> " + output_path)
    finally:
        app.exitQgis()


def layers_extent(project):
    """Union of every valid layer's extent, in the project CRS. None when no layer has one."""
    from qgis.core import QgsCoordinateTransform, QgsRectangle
    extent = None
    for layer in map_layers(project):
        e = layer.extent()
        if e.isEmpty():
            continue
        if layer.crs() != project.crs():
            e = QgsCoordinateTransform(layer.crs(), project.crs(), project).transformBoundingBox(e)
        if extent is None:
            extent = QgsRectangle(e)
        else:
            extent.combineExtentWith(e)
    return extent


def map_layers(project):
    return [l for l in project.mapLayers().values() if l.isValid()]


def export_pdf(project, output_path, QgsLayoutExporter, QgsLayout, QgsLayoutItemMap,
               QgsLayoutSize):
    layouts = project.layoutManager().printLayouts()
    if layouts:
        layout = layouts[0]
    else:
        # No print layout saved: build a one-page A4 landscape layout holding the map.
        from qgis.core import Qgis, QgsLayoutPoint
        mm = Qgis.LayoutUnit.Millimeters
        layout = QgsLayout(project)
        layout.initializeDefaults()
        layout.pageCollection().page(0).setPageSize(QgsLayoutSize(297, 210, mm))
        item = QgsLayoutItemMap(layout)
        item.attemptMove(QgsLayoutPoint(10, 10, mm))
        item.attemptResize(QgsLayoutSize(277, 190, mm))
        item.setLayers(map_layers(project))
        extent = layers_extent(project)
        if extent is not None:
            item.setExtent(extent)
        layout.addLayoutItem(item)
    exporter = QgsLayoutExporter(layout)
    result = exporter.exportToPdf(output_path, QgsLayoutExporter.PdfExportSettings())
    if result != QgsLayoutExporter.ExportResult.Success:
        fail("layout export failed with code " + str(result))


def export_png(project, output_path, QgsMapSettings, QgsMapRendererCustomPainterJob,
               QSize, QImage, QPainter, QColor):
    layers = map_layers(project)
    if not layers:
        fail("the project has no valid layers to render")
    extent = layers_extent(project)
    settings = QgsMapSettings()
    settings.setLayers(layers)
    settings.setDestinationCrs(project.crs())
    settings.setExtent(extent)
    settings.setOutputSize(QSize(1600, 1200))
    settings.setBackgroundColor(QColor(255, 255, 255))
    image = QImage(settings.outputSize(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    job = QgsMapRendererCustomPainterJob(settings, painter)
    job.start()
    job.waitForFinished()
    painter.end()
    if not image.save(output_path, "PNG"):
        fail("could not write PNG")


def export_gpkg(project, output_path, QgsVectorLayer, QgsVectorFileWriter,
                QgsCoordinateTransformContext):
    vectors = [l for l in map_layers(project) if isinstance(l, QgsVectorLayer)]
    if not vectors:
        fail("the project has no vector layers to package")
    if os.path.exists(output_path):
        os.remove(output_path)
    for i, layer in enumerate(vectors):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer.name()
        existing = QgsVectorFileWriter.ActionOnExistingFile
        options.actionOnExistingFile = (
            existing.CreateOrOverwriteFile if i == 0 else existing.CreateOrOverwriteLayer)
        err, msg = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, output_path, QgsCoordinateTransformContext(), options)[:2]
        if err != QgsVectorFileWriter.WriterError.NoError:
            fail("packaging layer '" + layer.name() + "' failed: " + str(msg))


main()
