"""Which commands may be used right now, decided from what the service says and nothing else.

Marc: "I'm not sure if we can control activity when a function should not be available". In Qt
every action's enabled state is ours to set; the question is only what the rule is. The rule is
the LibreOffice sidebar's (``nexusplm.panel.enabled_buttons``), widened to the whole command set,
so a user who sees a command in two hosts and finds it enabled in one has found a bug:

* **Signed out**: only Sign In and the commands that need no session.
* **No file**: the commands that make or fetch a project. Nothing that works on *this* file.
* **A file PLM does not know**: the two Save As commands, which are how it gets to know it.
* **A PLM item**: its card and its values; Check Out when it is checked in; Check In and Save to
  PLM when it is checked out **to you**; Revise unless somebody else holds it.

No QGIS here. ``state`` is the ``/plm/state`` answer, ``user`` the signed-in name, ``path`` the
project's file or ``None``.
"""

#: Usable with no session and no file.
ALWAYS = frozenset({"connection-status", "settings", "help", "about"})

#: Usable once signed in, whatever is open - they fetch or make a project rather than act on one.
SIGNED_IN = frozenset({"new-from-template", "open-from-plm", "search", "worklist"})

#: Usable on a saved file, registered or not - they are how a file becomes an item.
WITH_FILE = frozenset({"save-as-new", "save-as-existing"})

#: Usable on a registered item whoever holds it.
IN_PLM = frozenset({"properties", "edit-values", "refresh-values", "new-workflow", "change-owner"})


def is_in_plm(state):
    """Whether the service resolved the file to an item.

    ``status`` is ``unknown`` both for a file PLM has never seen and for one it could not resolve,
    so this is about what can be offered, not about why.
    """
    return bool(state) and bool(state.get("status")) and state["status"] != "unknown"


def enabled_commands(state, user=None, path=None):
    """The set of command names that may be used, for the toolbar and the menu alike."""
    allowed = set(ALWAYS)
    if not user:
        allowed.add("sign-in")
        return allowed

    allowed.add("sign-out")
    allowed |= SIGNED_IN
    if not path:
        return allowed

    allowed |= WITH_FILE
    if not is_in_plm(state):
        return allowed

    allowed |= IN_PLM
    status = state.get("status")
    holder = state.get("checked_out_by")
    mine = status == "checked_out" and holder == user
    held_by_other = status == "checked_out" and not mine

    if status == "checked_in":
        allowed.add("check-out")
    if mine:
        allowed |= {"check-in", "save-to-plm"}
    if not held_by_other:
        allowed.add("revise")
    return allowed
