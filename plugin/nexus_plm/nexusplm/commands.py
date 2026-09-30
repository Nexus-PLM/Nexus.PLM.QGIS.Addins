"""What each Nexus PLM menu entry does, in one place and with no QGIS API in sight.

Every command takes a :class:`Context` and returns ``None``. The context carries the four things a
command can need - the service client, the open project, its file, and the window to parent a
dialog to - so no command has to go and find them, and so all of this can be tested without QGIS.

Every command that gives PLM a file gives it :func:`_to_upload`, which writes the project **as it
stands** to its own file. See :func:`nexusplm.host.upload_copy` for why it is the project's own
file and not a copy.
"""

from nexusplm import host
from nexusplm import identity
from nexusplm import project as record
from nexusplm.client import Client, ServiceUnavailable, FILE_EXTENSIONS


class Context(object):
    """What a command is given. Built once by the entry point."""

    def __init__(self, client, project, path, hwnd=0):
        self.client = client
        self.project = project
        self.path = path
        self.hwnd = hwnd


# ── shared helpers ───────────────────────────────────────────────────────────

def _refused(context, answer, command):
    """Show the service's own reason for refusing. A cancelled dialog is not a refusal."""
    if answer.get("cancelled"):
        return
    host.say(context.client,
             answer.get("error") or "Nexus PLM did not answer the %s request." % command,
             "warning")


def _require_path(context):
    """The project must have been saved before PLM can do anything with the file itself."""
    if context.path:
        return True
    host.say(context.client,
             "Save this project to a file first. Nexus PLM works on the saved file, and this one "
             "has never been saved.", "warning")
    return False


def _require_item(context):
    """The item this project is, or ``None`` with the user already told why not."""
    if not _require_path(context):
        return None
    item_id = identity.item_of(context.client, context.path)
    if item_id is None:
        host.say(context.client, "This project is not registered in PLM.", "warning")
    return item_id


def _to_upload(context):
    """The file PLM should take: the project as it stands, written to its own file."""
    return host.upload_copy(context.project, context.path)


def _remember(context, answer):
    """Write down that this file is that item - the next command reads it back.

    Through ``identity.remember`` rather than ``state.remember`` directly, because the service
    does not use one name for the item across every endpoint: ``/plm/new`` answers
    ``plm_object_id`` where others answer ``item_id``. identity knows both.
    """
    identity.remember(context.path, answer)


def _hand_over(context, answer):
    """Take the file PLM just staged: remember it, write its record, and show it.

    The order matters. The record goes in while the project is still only a file - a staged file
    that is not the open project opens in a NEW QGIS, so there is no live project to write it into
    afterwards. Without this step New from Template hands over a project carrying nothing, for an
    item PLM has just numbered.
    """
    staged = answer.get("file_path")
    if not staged:
        return False

    identity.remember(staged, answer)

    mappings = answer.get("attribute_mappings") or {}
    if mappings:
        try:
            recorded, shown = record.write_into_file(staged, mappings)
            host.log("staged %s: wrote %d value(s), %d shown" % (staged, recorded, shown))
        except Exception as error:                              # noqa: BLE001
            # A project that opens without its values is worth having; a command that fails
            # because it could not fill them in is not.
            host.log("could not write values into %s: %r" % (staged, error))

    if host.same_file(staged, context.path):
        # PLM staged the file this project IS - which is what Revise does, since the next revision
        # keeps the part number and so the file name. Writing the new revision's record into the
        # open project makes this window the new revision, edits and all. Opening the file in a
        # second QGIS beside the closed revision was the bug Marc saw on Inkscape: "opening a new
        # file, not up-revving the existing one".
        if mappings:
            recorded, shown = record.write_values(context.project, mappings)
            host.log("the open project is now %s: wrote %d value(s), %d shown" % (staged, recorded, shown))
    else:
        host.open_document(staged)
    return True


def _apply(context, answer, quiet=False):
    """Write the attribute values the service returned into the project."""
    mappings = answer.get("attribute_mappings") or {}
    recorded, shown = record.write_values(context.project, mappings)
    if recorded:
        host.log("wrote %d value(s), %d shown as project variables" % (recorded, shown))
    elif not quiet:
        host.say(context.client,
                 "Nothing to update: this item has no attributes mapped into the project.")
    return recorded


# ── account ──────────────────────────────────────────────────────────────────

def sign_in(context):
    """Sign in, through the service's own window."""
    answer = context.client.sign_in(context.hwnd)
    if not answer.get("success"):
        _refused(context, answer, "Sign In")


def sign_out(context):
    """Sign out of PLM.

    No toast of our own on success. ``/api/auth/logout`` carries the service's ``[CommandToast]``,
    so the tray has already said "Logout - Signed out admin" by the time the answer arrives; a
    second "Signed out." underneath it is what driving the Inkscape add-in showed.
    """
    answer = context.client.sign_out()
    if not answer.get("success"):
        _refused(context, answer, "Sign Out")


# ── data management ──────────────────────────────────────────────────────────

def new_from_template(context):
    """Create a new item from a type's template and open the project it makes."""
    answer = context.client.new(context.hwnd, file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "New")

    if not _hand_over(context, answer):
        host.say(context.client,
                 "PLM created the item but did not stage a file to open.", "warning")


def open_from_plm(context):
    """Browse the vault and open the chosen project."""
    answer = context.client.open_document(context.hwnd, file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "Open")

    if not _hand_over(context, answer):
        _refused(context, answer, "Open")


def search(context):
    """Search PLM, and open whatever the user picks."""
    answer = context.client.search(context.hwnd)
    if not answer.get("success"):
        return _refused(context, answer, "Search")
    _hand_over(context, answer)


def save_to_plm(context):
    """Upload this project to its item, keeping the lock."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.save(item_id, _to_upload(context))
    if not answer.get("success"):
        _refused(context, answer, "Save")


def save_as_new(context):
    """Register this project as a new PLM item."""
    if not _require_path(context):
        return

    answer = context.client.save_as_new(
        _to_upload(context), context.hwnd,
        attributes=record.offerable_values(context.project),
        file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "Save As New Item")

    # Registering and then not writing it down is how a document PLM had just created came back
    # as "not registered in PLM" on the very next command.
    _remember(context, answer)
    _apply(context, answer, quiet=True)


def save_as_existing(context):
    """Give this project's content to an item that already exists."""
    if not _require_path(context):
        return

    answer = context.client.save_as_existing(
        _to_upload(context), context.hwnd, file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "Save As Existing Item")
    _remember(context, answer)

    # The answer names the item the project now belongs to but carries none of its values - the
    # service's Save As Existing answers no mappings, for any host. Ask for them, so the record
    # and the layout variables show whose project it has become.
    item_id = answer.get("item_id")
    if item_id:
        values = context.client.refresh_values(item_id)
        if values.get("success"):
            _apply(context, values, quiet=True)


# ── lifecycle ────────────────────────────────────────────────────────────────

def check_out(context):
    """Take the lock, so nobody else can change the item while you work."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.check_out(item_id)
    if not answer.get("success"):
        _refused(context, answer, "Check Out")


def check_in(context):
    """Upload and release the lock."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.check_in(item_id, _to_upload(context))
    if not answer.get("success"):
        _refused(context, answer, "Check In")


def revise(context):
    """Start a new revision of this item."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.revise(item_id, context.hwnd)
    if not answer.get("success"):
        return _refused(context, answer, "Revise")

    _hand_over(context, answer)


def change_owner(context):
    """Hand the item to someone else."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.change_owner(item_id, context.hwnd, context.path)
    if not answer.get("success"):
        _refused(context, answer, "Change Ownership")


# ── workflow ─────────────────────────────────────────────────────────────────

def worklist(context):
    """Show what PLM is waiting on you for."""
    answer = context.client.worklist(context.hwnd)
    if not answer.get("success"):
        _refused(context, answer, "My Worklist")


def new_workflow(context):
    """Start a workflow on this item."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.new_workflow(item_id)
    if not answer.get("success"):
        _refused(context, answer, "New Workflow")


# ── attributes ───────────────────────────────────────────────────────────────

def properties(context):
    """Show the item's full card."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.properties(item_id, context.hwnd)
    if not answer.get("success"):
        _refused(context, answer, "Properties")


def edit_values(context):
    """Edit the item's attributes, then write what was saved back into the project."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.edit_values(item_id, context.hwnd, record.read_values(context.project))
    if not answer.get("success"):
        return _refused(context, answer, "Edit Values")
    if answer.get("saved"):
        _apply(context, answer)


def refresh_values(context):
    """Re-read the item's attributes from PLM into the project."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.refresh_values(item_id)
    if not answer.get("success"):
        return _refused(context, answer, "Refresh Values")
    _apply(context, answer)


# ── information ──────────────────────────────────────────────────────────────

def settings(context):
    """The service's own settings window."""
    answer = context.client.settings()
    if not answer.get("success"):
        _refused(context, answer, "Settings")


def about(context):
    """What this add-in and the service are."""
    answer = context.client.about(context.hwnd, addin_version=VERSION)
    if not answer.get("success"):
        _refused(context, answer, "About")


def help_site(context):
    """Open the add-in's documentation."""
    host.open_url(HELP_URL)


def connection_status(context):
    """Say whether the service is reachable, and who is signed in.

    ``health()`` first, and deliberately: it raises when the service is not running, which is the
    one answer this command exists to give.
    """
    context.client.health()
    who = context.client.me()
    if who.get("success"):
        host.say(context.client,
                 "Connected to Nexus PLM. Signed in as %s." % (who.get("username") or "you"))
    else:
        host.say(context.client, "Connected to Nexus PLM. Nobody is signed in.")


#: Add-in version, reported by About and in the service's log. Kept in step with metadata.txt
#: and the installer; tests hold all three together.
VERSION = "0.1.0"
HELP_URL = host.HELP_URL

#: Every command the menu can run, by name.
COMMANDS = {
    "sign-in": sign_in,
    "sign-out": sign_out,
    "new-from-template": new_from_template,
    "open-from-plm": open_from_plm,
    "search": search,
    "save-to-plm": save_to_plm,
    "save-as-new": save_as_new,
    "save-as-existing": save_as_existing,
    "check-out": check_out,
    "check-in": check_in,
    "revise": revise,
    "change-owner": change_owner,
    "worklist": worklist,
    "new-workflow": new_workflow,
    "properties": properties,
    "edit-values": edit_values,
    "refresh-values": refresh_values,
    "settings": settings,
    "about": about,
    "help": help_site,
    "connection-status": connection_status,
}


def run(name, project, hwnd=0):
    """Run one command by name, turning every failure into something the user can read.

    A command must never leave a Python traceback in front of the user: QGIS shows one in a
    "Python error" bar with a stack trace, which turns a service that is merely not running into
    something that looks like a broken plugin. Only :class:`ServiceUnavailable` escapes, for the
    entry point to turn into the "tray is not running" message.
    """
    client = Client()
    path = host.document_path(project)
    context = Context(client, project, path, hwnd=hwnd)

    command = COMMANDS.get(name)
    if command is None:
        host.log("unknown command: %s" % name)
        return

    host.log("%s: started" % name)
    try:
        command(context)
        host.log("%s: done" % name)
    except ServiceUnavailable:
        host.log("%s: the Nexus PLM tray application is not running" % name)
        raise
    except Exception as error:                                   # noqa: BLE001 - see docstring
        host.log("%s: failed: %r" % (name, error))
        host.say(client, "Nexus PLM could not complete %s: %s" % (name, error), "warning")
