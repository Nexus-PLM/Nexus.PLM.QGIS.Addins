"""The QGIS-shaped helpers, tested against the fake project and real files."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugin", "nexus_plm"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from fakeqgis import Project  # noqa: E402
from nexusplm import host  # noqa: E402


@pytest.fixture(autouse=True)
def never_the_real_log(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "logs" / "addin.log"))


class TestDocumentPath:
    def test_a_saved_project_answers_its_file_as_a_windows_path(self):
        """QGIS reports forward slashes; the rest of Nexus compares back-slashed paths."""
        assert host.document_path(Project(path="C:/projects/QGP-1.qgz")) == os.path.normpath("C:/projects/QGP-1.qgz")

    def test_never_saved_is_none_not_an_empty_string(self):
        assert host.document_path(Project(path="")) is None
        assert host.document_path(Project()) is None


class TestUploadCopy:
    """What PLM is given: the project as it stands, written to its OWN file - never a temp copy."""

    def test_it_writes_the_project_to_its_own_file_and_answers_that_path(self, tmp_path):
        own = str(tmp_path / "QGP-000001-QGZ.qgz")
        project = Project(path=own)
        sent = host.upload_copy(project, own)
        assert sent == own
        assert project.written_to == [own]
        assert os.path.isfile(own)

    def test_the_project_is_clean_afterwards_as_after_a_real_save(self, tmp_path):
        own = str(tmp_path / "p.qgz")
        project = Project(path=own); project.setDirty(True)
        host.upload_copy(project, own)
        assert not project.dirty

    def test_a_project_with_no_file_is_refused_not_guessed(self):
        with pytest.raises(ValueError):
            host.upload_copy(Project(), None)

    def test_a_write_qgis_refuses_is_an_error_not_a_silent_upload_of_stale_bytes(self, tmp_path):
        project = Project(path=str(tmp_path / "p.qgz"))
        project.write = lambda path=None: False
        with pytest.raises(RuntimeError):
            host.upload_copy(project, str(tmp_path / "p.qgz"))


class TestSameFile:
    def test_case_and_slashes_do_not_matter_on_windows(self):
        assert host.same_file(r"C:\Nexus\Staging\QGP-1.qgz", "c:/nexus/staging/qgp-1.qgz")

    def test_different_files_differ(self):
        assert not host.same_file(r"C:\a\QGP-1.qgz", r"C:\a\QGP-2.qgz")

    def test_nothing_is_never_the_same_file(self):
        assert not host.same_file(None, r"C:\x.qgz")
        assert not host.same_file(r"C:\x.qgz", "")


class TestWindowHandle:
    def test_the_main_windows_hwnd(self):
        class Iface:
            def mainWindow(self):                                     # noqa: N802
                class W:
                    def winId(self):                                  # noqa: N802
                        return 123456
                return W()
        assert host.window_handle(Iface()) == 123456

    def test_no_window_is_zero_not_an_error(self):
        assert host.window_handle(None) == 0


class TestLogging:
    def test_a_line_is_written(self):
        host.log("check-out: started")
        assert "check-out: started" in open(host.LOG_PATH, encoding="utf-8").read()

    def test_a_log_that_cannot_be_written_does_not_fail_the_command(self, monkeypatch):
        monkeypatch.setattr(host, "LOG_PATH", "\x00:/nowhere/addin.log")
        host.log("this must not raise")
