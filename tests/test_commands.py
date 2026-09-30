"""The command bodies, driven with a fake service and a fake QGIS."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugin", "nexus_plm"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from fakeqgis import Project, minimal_qgs, write_qgz  # noqa: E402
from nexusplm import commands, host, menu, state  # noqa: E402
from nexusplm import project as record  # noqa: E402
from nexusplm.client import ServiceUnavailable  # noqa: E402


class FakeClient:
    """Records what was asked of it and answers whatever the test set up."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []
        self.said = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append(name)
            return self.answers.get(name, {"success": True})
        return call

    def notify(self, message, severity="info"):
        self.said.append((severity, message))
        self.calls.append("notify")
        return {"success": True}


@pytest.fixture(autouse=True)
def no_real_side_effects(monkeypatch, tmp_path):
    """Never write the real log or document map, never launch QGIS, never open a browser."""
    monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "addin.log"))
    monkeypatch.setattr(state, "_PATH", str(tmp_path / "documents.json"))
    monkeypatch.setattr(host, "open_document", lambda path: None)
    monkeypatch.setattr(host, "open_url", lambda url: None)
    monkeypatch.setattr(host, "upload_copy", lambda project, path: path)


def context(client=None, project=None, path="C:/projects/QGP-000001-QGZ.qgz"):
    return commands.Context(client or FakeClient(), project or Project(path=path), path)


class TestTheMenuAndTheCommandsAgree:
    """A menu entry with no command is a dead entry; a command with no entry is unreachable."""

    def test_every_menu_entry_has_a_command(self):
        assert [c for c, _ in menu.ENTRIES if c not in commands.COMMANDS] == []

    def test_every_command_is_on_the_menu(self):
        assert sorted(set(commands.COMMANDS) - {c for c, _ in menu.ENTRIES}) == []

    def test_every_toolbar_button_is_a_menu_entry(self):
        assert [c for c in menu.TOOLBAR if c not in menu.LABELS] == []

    def test_twenty_one_commands_like_every_other_nexus_add_in(self):
        assert len(menu.ENTRIES) == 21


class TestAnUnregisteredProject:
    def test_it_is_told_so_rather_than_failing(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: None)
        client = FakeClient()
        commands.check_out(context(client))
        assert any("not registered in PLM" in m for _s, m in client.said)
        assert "check_out" not in client.calls


class TestAnUnsavedProject:
    def test_save_as_new_says_to_save_first(self):
        client = FakeClient()
        commands.save_as_new(context(client, project=Project(), path=None))
        assert any("never been saved" in m for _s, m in client.said)
        assert "save_as_new" not in client.calls


class TestWhatGetsUploaded:
    """PLM is given the project's own path, holding the project as it stands - not a temp copy."""

    def test_save_to_plm_sends_the_projects_own_path(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient()
        sent = {}
        monkeypatch.setattr(client, "save",
                            lambda item_id, path: sent.update(path=path) or {"success": True})
        ctx = context(client)
        commands.save_to_plm(ctx)
        assert sent["path"] == ctx.path

    def test_check_in_sends_one_too(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient()
        commands.check_in(context(client))
        assert "check_in" in client.calls


class TestValuesReachTheProject:
    def test_refresh_writes_the_record(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(refresh_values={
            "success": True, "attribute_mappings": {"PartNumber": "QGP-000001-QGZ", "Revision": "B"}})
        ctx = context(client)
        commands.refresh_values(ctx)
        assert record.read_values(ctx.project) == {"PartNumber": "QGP-000001-QGZ", "Revision": "B"}
        assert ctx.project.variables["nexus_revision"] == "B"

    def test_edit_values_writes_only_when_the_dialog_was_saved(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(edit_values={"success": True, "saved": False,
                                         "attribute_mappings": {"Revision": "Z"}})
        ctx = context(client)
        commands.edit_values(ctx)
        assert record.read_values(ctx.project) == {}

    def test_an_item_with_no_mapped_attributes_says_so(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(refresh_values={"success": True, "attribute_mappings": {}})
        commands.refresh_values(context(client))
        assert any("Nothing to update" in m for _s, m in client.said)


class TestTheStagedFile:
    """New from Template: the record goes into the FILE before it is opened."""

    def test_new_from_template_writes_the_record_remembers_and_opens(self, monkeypatch, tmp_path):
        staged = write_qgz(str(tmp_path / "QGP-000002-QGZ.qgz"), minimal_qgs())
        opened = []
        monkeypatch.setattr(host, "open_document", lambda p: opened.append(p))
        client = FakeClient(new={"success": True, "plm_object_id": "obj-2", "part_number": "QGP-000002-QGZ",
                                 "file_path": staged, "attribute_mappings": {"PartNumber": "QGP-000002-QGZ"}})
        commands.new_from_template(context(client))
        assert opened == [staged]
        assert record.read_from_file(staged) == {"PartNumber": "QGP-000002-QGZ"}
        assert state.item_of(staged) == "obj-2"

    def test_a_file_that_cannot_take_the_record_still_opens(self, monkeypatch, tmp_path):
        broken = str(tmp_path / "broken.qgz")
        open(broken, "wb").write(b"not a zip, not xml")
        opened = []
        monkeypatch.setattr(host, "open_document", lambda p: opened.append(p))
        client = FakeClient(new={"success": True, "plm_object_id": "obj-3", "file_path": broken,
                                 "attribute_mappings": {"PartNumber": "QGP-000003-QGZ"}})
        commands.new_from_template(context(client))
        assert opened == [broken]

    def test_no_staged_file_is_said(self):
        client = FakeClient(new={"success": True, "plm_object_id": "obj-4"})
        commands.new_from_template(context(client))
        assert any("did not stage a file" in m for _s, m in client.said)


class TestReviseInPlace:
    """Revise stages the next revision under the SAME file name. The open project must become it."""

    def test_the_open_project_takes_the_new_revisions_record_and_nothing_opens(self, monkeypatch, tmp_path):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        staged = write_qgz(str(tmp_path / "QGP-000001-QGZ.qgz"), minimal_qgs())
        opened = []
        monkeypatch.setattr(host, "open_document", lambda p: opened.append(p))
        client = FakeClient(revise={"success": True, "item_id": "item-1", "revision": "B",
                                    "file_path": staged.upper(),          # same file, other case
                                    "attribute_mappings": {"Revision": "B"}})
        ctx = context(client, project=Project(path=staged), path=staged)
        commands.revise(ctx)
        assert opened == []
        assert record.read_values(ctx.project)["Revision"] == "B"
        assert record.read_from_file(staged) == {"Revision": "B"}

    def test_a_different_file_opens_in_a_new_qgis_and_leaves_this_project_alone(self, monkeypatch, tmp_path):
        other = write_qgz(str(tmp_path / "QGP-000002-QGZ.qgz"), minimal_qgs())
        opened = []
        monkeypatch.setattr(host, "open_document", lambda p: opened.append(p))
        client = FakeClient(open_document={"success": True, "item_id": "item-2", "file_path": other,
                                           "attribute_mappings": {"Revision": "A"}})
        ctx = context(client, path=str(tmp_path / "QGP-000001-QGZ.qgz"))
        commands.open_from_plm(ctx)
        assert opened == [other]
        assert record.read_values(ctx.project) == {}


class TestSignOut:
    def test_it_does_not_toast_on_success(self):
        client = FakeClient()
        commands.sign_out(context(client))
        assert client.said == []

    def test_a_refusal_is_still_shown(self):
        client = FakeClient(sign_out={"success": False, "error": "Not signed in."})
        commands.sign_out(context(client))
        assert any("Not signed in." in m for _s, m in client.said)


class TestSaveAsNewOffers:
    def test_empty_slots_and_server_keys_stay_home(self, monkeypatch):
        project = Project(path="C:/projects/plain.qgz", entries={"NexusPLM": {
            "PartNumber": "", "Revision": "", "CreatedBy": "", "CreationDate": "",
            "Description": "A plain project", "Author": ""}})
        client = FakeClient()
        sent = {}
        monkeypatch.setattr(client, "save_as_new",
                            lambda path, hwnd, attributes=None, file_extensions=None:
                            sent.update(attributes=attributes) or {"success": True})
        commands.save_as_new(context(client, project=project, path="C:/projects/plain.qgz"))
        assert sent["attributes"] == {"Description": "A plain project"}


class TestSaveAsExistingFillsTheRecord:
    def test_the_items_values_are_fetched_and_written(self):
        client = FakeClient(
            save_as_existing={"success": True, "item_id": "item-3", "part_number": "QGP-000003-QGZ"},
            refresh_values={"success": True,
                            "attribute_mappings": {"PartNumber": "QGP-000003-QGZ", "Revision": "A"}})
        ctx = context(client)
        commands.save_as_existing(ctx)
        assert client.calls.index("save_as_existing") < client.calls.index("refresh_values")
        assert record.read_values(ctx.project) == {"PartNumber": "QGP-000003-QGZ", "Revision": "A"}

    def test_a_refusal_asks_for_nothing_more(self):
        client = FakeClient(save_as_existing={"success": False, "error": "Locked by jdoe."})
        commands.save_as_existing(context(client))
        assert "refresh_values" not in client.calls


class TestRefusalsAreShown:
    def test_the_services_own_reason_is_what_the_user_reads(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(check_out={"success": False, "error": "Already checked out to jdoe."})
        commands.check_out(context(client))
        assert any("Already checked out to jdoe." in m for _s, m in client.said)

    def test_a_cancelled_dialog_says_nothing(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(properties={"success": False, "cancelled": True})
        commands.properties(context(client))
        assert client.said == []


class TestConnectionStatus:
    def test_signed_in(self):
        client = FakeClient(me={"success": True, "username": "admin"})
        commands.connection_status(context(client))
        assert any("Signed in as admin" in m for _s, m in client.said)

    def test_signed_out(self):
        client = FakeClient(me={"success": False})
        commands.connection_status(context(client))
        assert any("Nobody is signed in" in m for _s, m in client.said)


class TestRun:
    def test_an_unexpected_failure_becomes_a_sentence_not_a_traceback(self, monkeypatch):
        boom = lambda ctx: (_ for _ in ()).throw(ValueError("kaboom"))          # noqa: E731
        monkeypatch.setitem(commands.COMMANDS, "explode", boom)
        said = []
        monkeypatch.setattr(host, "say", lambda client, msg, severity="info": said.append(msg))
        commands.run("explode", Project(path="C:/p.qgz"))
        assert any("kaboom" in m for m in said)

    def test_an_unreachable_service_is_raised_for_the_entry_point_to_show(self, monkeypatch):
        def unreachable(ctx):
            raise ServiceUnavailable("no tray")
        monkeypatch.setitem(commands.COMMANDS, "unreachable", unreachable)
        with pytest.raises(ServiceUnavailable):
            commands.run("unreachable", Project(path="C:/p.qgz"))

    def test_an_unknown_command_does_nothing_quietly(self):
        commands.run("no-such-command", Project())

    def test_the_window_handle_reaches_the_context(self, monkeypatch):
        seen = {}
        monkeypatch.setitem(commands.COMMANDS, "peek", lambda ctx: seen.update(hwnd=ctx.hwnd, path=ctx.path))
        commands.run("peek", Project(path="C:/projects/x.qgz"), hwnd=4242)
        assert seen["hwnd"] == 4242
        assert seen["path"] == os.path.normpath("C:/projects/x.qgz")
