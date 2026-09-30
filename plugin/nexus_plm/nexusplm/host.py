"""The parts that know they are inside QGIS.

Everything QGIS-shaped lives here so the command bodies do not have to care: where the log goes,
what the open project's file is, how to put a project in front of the user, and how to say
something to them.

**QGIS holds ONE project per window**, and a plugin holds the live ``QgsProject.instance()`` and
can write it. So this add-in behaves like the office ones: Save to PLM writes the project to its
own file and uploads that, with no guessing about whether the disk is up to date. Opening a second
project means a second QGIS, because loading one into this window would replace what the user has
open - which "Open from PLM" must never do.

``qgis`` is imported inside functions, never at module level: the tests run under plain Python.
"""

import os
import subprocess
import sys

#: Beside every other Nexus add-in's log, under its own name so two hosts never share a file.
LOG_PATH = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"),
    "NexusPLM", "Logs", "plmqgisaddin.log")

HELP_URL = "https://github.com/Nexus-PLM/Nexus.PLM.QGIS.Addins"


def log(message):
    """A line in the shared log. Best effort - a command must not fail over a log write."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        pass


def document_path(project):
    """The file the open project was saved to, or ``None`` when it has never been saved.

    ``None`` is a normal state, not a failure: a fresh QGIS window holds an unsaved project, and
    Save As New Item is exactly the command for it. QGIS answers "" for never-saved; that becomes
    ``None`` so a caller has one case to handle. Back-slashed, because QGIS reports forward slashes
    and the rest of Nexus (the document map, the service's ``plm_file_path``) compares Windows paths.
    """
    try:
        path = project.fileName()
    except Exception:
        return None
    if not path:
        return None
    return os.path.normpath(path)


def upload_copy(project, path):
    """Write the project as it stands to its own file, and answer that path for PLM.

    The project's **own file, not a copy under %TEMP%**: ``SaveRequest`` has one ``FilePath``, which
    the service both reads and **records as the item's ``plm_file_path``** - so a temp copy became
    the item's home, and Revise staged the next revision under %TEMP% and opened it in a second
    window (measured on the Inkscape add-in, which shares this design). Marc: "it must get written
    to the staging directory." For an item PLM handed over, the project's own file IS the staged
    file. Writing it is what QGIS's own Save does, and the project is clean afterwards.

    ``path`` is required: a project that has never been saved has no file for PLM to take, and the
    commands refuse that case before reaching here.
    """
    if not path:
        raise ValueError("a project with no file cannot be uploaded")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not project.write(path):
        raise RuntimeError("QGIS could not write the project to %s" % path)
    return path


def same_file(a, b):
    """Whether two paths name the same file, as Windows sees it: case-insensitive, normalised."""
    if not a or not b:
        return False
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def open_document(path):
    """Show a project to the user, in a new QGIS.

    Not ``iface.addProject``: that loads the file into THIS window, closing whatever the user had
    open (with a save prompt if it was dirty). Opening an item from the vault must not disturb the
    user's work, so a second QGIS is started on the file - the same executable this one runs as,
    with this process's environment, which is the OSGeo4W environment ``qgis.bat`` set up.

    All three streams go to DEVNULL and the child is detached, so closing the first QGIS cannot
    take the second down with it.
    """
    executable = qgis_executable()
    if not executable:
        raise RuntimeError("Could not find the QGIS executable to open %s with." % path)

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) \
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    subprocess.Popen(
        [executable, path],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, creationflags=creation_flags,
    )


def qgis_executable():
    """Where QGIS itself is: the program this plugin is running inside.

    ``QCoreApplication.applicationFilePath()`` is the running executable - ``qgis-bin.exe`` on
    Windows - which is exactly the one to start again. Found rather than configured, because a
    hardcoded path breaks on the first machine that installed elsewhere.
    """
    try:
        from qgis.PyQt.QtCore import QCoreApplication
        path = QCoreApplication.applicationFilePath()
        if path and os.path.isfile(path):
            return os.path.normpath(path)
    except Exception:
        pass
    # Outside QGIS (or an odd build): the interpreter's own folder is the bin folder.
    here = os.path.dirname(os.path.abspath(sys.executable))
    for name in ("qgis-bin.exe", "qgis-bin", "qgis"):
        candidate = os.path.join(here, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def window_handle(iface):
    """The main window's HWND, for the service to parent its dialogs to. 0 when unknown."""
    try:
        return int(iface.mainWindow().winId())
    except Exception:
        return 0


def open_url(url):
    """Open a page in the user's browser."""
    import webbrowser
    webbrowser.open(url)


def say(client, message, severity="info"):
    """Tell the user something, through the one toast the tray host owns.

    Not QGIS's own message bar: every Nexus add-in says things in the same place, and the tray is
    the one thing that is running whichever host the user is in.
    """
    try:
        client.notify(message, severity)
    except Exception:
        log("could not post a notification: " + message)
