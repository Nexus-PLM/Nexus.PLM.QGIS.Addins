"""Which commands are offered when - the rule the toolbar and the menu both follow."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugin", "nexus_plm"))

from nexusplm import availability, menu  # noqa: E402

ALL = {c for c, _ in menu.ENTRIES}
PATH = r"C:\Nexus\Staging\QGP-000001-QGZ.qgz"


def on(state=None, user="admin", path=PATH):
    return availability.enabled_commands(state, user=user, path=path)


class TestSignedOut:
    def test_only_sign_in_and_the_session_free_commands(self):
        assert on(user=None) == {"sign-in", "connection-status", "settings", "help", "about"}

    def test_sign_out_is_not_offered_when_nobody_is_signed_in(self):
        assert "sign-out" not in on(user=None)


class TestNoFile:
    def test_fetching_and_making_are_offered_nothing_on_this_file(self):
        allowed = on(path=None)
        assert {"new-from-template", "open-from-plm", "search", "worklist", "sign-out"} <= allowed
        for command in ("save-as-new", "save-to-plm", "check-out", "properties", "revise"):
            assert command not in allowed, command


class TestAFilePlmDoesNotKnow:
    def test_the_save_as_commands_are_how_it_gets_to_know_it(self):
        allowed = on(state={"success": True, "status": "unknown"})
        assert {"save-as-new", "save-as-existing"} <= allowed
        for command in ("save-to-plm", "check-out", "check-in", "revise", "properties", "edit-values"):
            assert command not in allowed, command

    def test_no_state_at_all_reads_the_same(self):
        assert on(state=None) == on(state={"status": "unknown"})


class TestAnItem:
    def checked_in(self):
        return {"success": True, "status": "checked_in", "checked_out_by": None}

    def mine(self):
        return {"success": True, "status": "checked_out", "checked_out_by": "admin"}

    def theirs(self):
        return {"success": True, "status": "checked_out", "checked_out_by": "jdoe"}

    def released(self):
        return {"success": True, "status": "released", "checked_out_by": None}

    def test_checked_in_offers_check_out_and_revise_not_check_in(self):
        allowed = on(self.checked_in())
        assert {"check-out", "revise", "properties", "edit-values", "refresh-values",
                "new-workflow", "change-owner"} <= allowed
        assert "check-in" not in allowed and "save-to-plm" not in allowed

    def test_checked_out_to_me_offers_check_in_and_save_not_check_out(self):
        allowed = on(self.mine())
        assert {"check-in", "save-to-plm", "revise"} <= allowed
        assert "check-out" not in allowed

    def test_checked_out_to_somebody_else_offers_neither_lock_command_nor_revise(self):
        allowed = on(self.theirs())
        for command in ("check-out", "check-in", "save-to-plm", "revise"):
            assert command not in allowed, command
        assert {"properties", "refresh-values"} <= allowed          # looking is always fine

    def test_released_offers_revise_but_not_check_out(self):
        """A released revision is closed; the next step is a new revision, not a lock on this one."""
        allowed = on(self.released())
        assert "revise" in allowed and "check-out" not in allowed

    def test_every_command_the_rule_names_exists(self):
        named = (availability.ALWAYS | availability.SIGNED_IN | availability.WITH_FILE
                 | availability.IN_PLM | {"sign-in", "sign-out", "check-out", "check-in",
                                           "save-to-plm", "revise"})
        assert named == ALL
