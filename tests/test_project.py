"""The PLM record in a project: live, and in a file nothing has open."""

import os
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugin", "nexus_plm"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from fakeqgis import Project, Variables, minimal_qgs, write_qgz  # noqa: E402
from nexusplm import project as record  # noqa: E402


class TestTheRecord:
    def test_a_project_never_in_plm_reads_empty(self):
        assert record.read_values(Project()) == {}

    def test_values_go_into_the_nexusplm_scope_and_come_back(self):
        p = Project()
        recorded, shown = record.write_values(p, {"PartNumber": "QGP-000001-QGZ", "Revision": "A"},
                                              variables=Variables)
        assert (recorded, shown) == (2, 2)
        assert record.read_values(p) == {"PartNumber": "QGP-000001-QGZ", "Revision": "A"}
        assert p.readEntry("NexusPLM", "PartNumber", "")[0] == "QGP-000001-QGZ"

    def test_writing_marks_the_project_dirty_so_save_is_offered(self):
        p = Project()
        record.write_values(p, {"Revision": "B"}, variables=Variables)
        assert p.dirty

    def test_none_is_recorded_as_empty_text(self):
        p = Project()
        record.write_values(p, {"Author": None}, variables=Variables)
        assert record.read_values(p) == {"Author": ""}

    def test_nothing_to_write_touches_nothing(self):
        p = Project()
        assert record.write_values(p, {}, variables=Variables) == (0, 0)
        assert not p.dirty


class TestTheDisplay:
    """Values are shown through project variables a layout label can read."""

    def test_each_value_becomes_a_nexus_variable(self):
        p = Project()
        record.write_values(p, {"PartNumber": "QGP-000001-QGZ"}, variables=Variables)
        assert p.variables == {"nexus_partnumber": "QGP-000001-QGZ"}

    def test_a_timestamp_shows_as_its_date_but_is_recorded_in_full(self):
        p = Project()
        record.write_values(p, {"CreationDate": "2026-09-30T01:20:23.1099261Z"}, variables=Variables)
        assert p.variables["nexus_creationdate"] == "2026-09-30"
        assert record.read_values(p)["CreationDate"] == "2026-09-30T01:20:23.1099261Z"

    def test_variable_names_are_expression_safe(self):
        assert record.variable_name("Review Due") == "nexus_review_due"
        assert record.variable_name("PartNumber") == "nexus_partnumber"

    def test_without_qgis_the_fake_projects_own_setter_is_found(self):
        """Inside QGIS the real QgsExpressionContextUtils is imported; outside, the project's."""
        p = Project()
        recorded, shown = record.write_values(p, {"Revision": "C"})
        assert (recorded, shown) == (1, 1)
        assert p.variables == {"nexus_revision": "C"}


class TestWhatANewItemMayTakeFromTheProject:
    """Save As New offers the project's values as defaults. Not all of them."""

    RECORD = {"NexusPLM": {
        "PartNumber": "QGP-000004-QGZ", "Revision": "B", "CreatedBy": "admin",
        "CreationDate": "2026-09-28T19:41:00Z", "ModifiedBy": "admin",
        "ModificationDate": "2026-09-29T01:00:00Z",
        "Description": "Site survey", "Author": "Claude", "Department": "", "Priority": "",
    }}

    def test_blank_slots_are_not_offered(self):
        offered = record.offerable_values(Project(entries=self.RECORD))
        assert "Department" not in offered and "Priority" not in offered

    def test_the_servers_own_keys_are_not_offered_whatever_the_project_says(self):
        offered = record.offerable_values(Project(entries=self.RECORD))
        for key in ("PartNumber", "Revision", "CreatedBy", "CreationDate",
                    "ModifiedBy", "ModificationDate"):
            assert key not in offered, key

    def test_the_users_own_filled_in_values_are(self):
        assert record.offerable_values(Project(entries=self.RECORD)) == {
            "Description": "Site survey", "Author": "Claude"}


class TestWritingIntoAStagedFile:
    """New from Template stages a file and opens it in a new QGIS: the record must be in the FILE."""

    def test_a_qgz_gets_the_record_and_keeps_its_other_members(self, tmp_path):
        path = write_qgz(str(tmp_path / "QGP-000001-QGZ.qgz"), minimal_qgs())
        recorded, shown = record.write_into_file(path, {"PartNumber": "QGP-000001-QGZ", "Revision": "A"})
        assert (recorded, shown) == (2, 2)
        assert record.read_from_file(path) == {"PartNumber": "QGP-000001-QGZ", "Revision": "A"}
        with zipfile.ZipFile(path) as archive:
            assert sorted(archive.namelist()) == ["QGP-000001-QGZ.qgs", "styles.db"]
            assert archive.read("styles.db").startswith(b"SQLite format 3")

    def test_the_variables_are_written_the_way_qgis_stores_them(self, tmp_path):
        """Two parallel QStringLists under <Variables>: variableNames and variableValues."""
        path = write_qgz(str(tmp_path / "p.qgz"), minimal_qgs())
        record.write_into_file(path, {"PartNumber": "QGP-000001-QGZ", "CreationDate": "2026-09-30T01:00:00Z"})
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("p.qgs"))
        block = [b for b in root.find("properties").findall("properties") if b.get("name") == "Variables"][0]
        names = [v.text for b in block if b.get("name") == "variableNames" for v in b]
        values = [v.text for b in block if b.get("name") == "variableValues" for v in b]
        assert dict(zip(names, values)) == {"nexus_partnumber": "QGP-000001-QGZ",
                                            "nexus_creationdate": "2026-09-30"}

    def test_existing_values_are_replaced_not_duplicated(self, tmp_path):
        path = write_qgz(str(tmp_path / "p.qgz"), minimal_qgs())
        record.write_into_file(path, {"Revision": "A"})
        record.write_into_file(path, {"Revision": "B"})
        assert record.read_from_file(path) == {"Revision": "B"}
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("p.qgs"))
        block = [b for b in root.find("properties").findall("properties") if b.get("name") == "Variables"][0]
        names = [v.text for b in block if b.get("name") == "variableNames" for v in b]
        assert names.count("nexus_revision") == 1

    def test_the_other_scopes_are_left_alone(self, tmp_path):
        path = write_qgz(str(tmp_path / "p.qgz"), minimal_qgs())
        record.write_into_file(path, {"Revision": "A"})
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("p.qgs"))
        gui = [b for b in root.find("properties").findall("properties") if b.get("name") == "Gui"][0]
        assert gui[0].get("name") == "CanvasColorBluePart" and gui[0].text == "255"

    def test_a_plain_qgs_works_too(self, tmp_path):
        path = tmp_path / "p.qgs"
        path.write_bytes(minimal_qgs())
        record.write_into_file(str(path), {"Revision": "A"})
        assert record.read_from_file(str(path)) == {"Revision": "A"}

    def test_a_file_without_a_record_reads_empty(self, tmp_path):
        path = write_qgz(str(tmp_path / "p.qgz"), minimal_qgs())
        assert record.read_from_file(path) == {}

    def test_nothing_to_write_leaves_the_file_untouched(self, tmp_path):
        path = write_qgz(str(tmp_path / "p.qgz"), minimal_qgs())
        before = open(path, "rb").read()
        assert record.write_into_file(path, {}) == (0, 0)
        assert open(path, "rb").read() == before

    def test_a_zip_with_no_project_inside_is_refused(self, tmp_path):
        path = str(tmp_path / "odd.qgz")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("readme.txt", b"nothing here")
        with pytest.raises(ValueError):
            record.write_into_file(path, {"Revision": "A"})


class TestHowAValueReads:
    def test_iso_timestamp_becomes_a_date(self):
        assert record.for_display("2026-09-30T01:20:23.1099261Z") == "2026-09-30"

    def test_everything_else_is_itself(self):
        assert record.for_display("Site survey") == "Site survey"
        assert record.for_display(None) == ""
        assert record.for_display(42) == "42"


class TestProjectFiles:
    def test_the_two_project_extensions(self):
        assert record.is_project_file(r"C:\x\a.qgz") and record.is_project_file(r"C:\x\a.QGS")
        assert not record.is_project_file(r"C:\x\a.gpkg") and not record.is_project_file(None)
