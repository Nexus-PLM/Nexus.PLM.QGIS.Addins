; Inno Setup script for the Nexus PLM plugin for QGIS.
;
; There is no build step. The plugin is Python that runs under QGIS's own interpreter, so what
; ships is what is in `plugin\nexus_plm\`. Compile it with:
;
;   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer\Nexus.PLM.QGIS.Addin.iss
;
; PER-USER, NO ELEVATION. QGIS reads plugins from its installation (admin rights, wiped by the
; next QGIS update) and from the user's profile, which needs neither. This installs into the
; profile: %APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\nexus_plm.
;
; THE FOLDER NAME IS THE PYTHON PACKAGE. QGIS imports `nexus_plm` and calls its classFactory;
; installed under any other folder name the import fails and the plugin manager shows it broken.
; tests\test_installer.py holds the name here against the folder in plugin\.
;
; A COPIED PLUGIN IS A DISABLED PLUGIN. QGIS lists it in Plugins > Manage and Install with its box
; unticked, which reads as "the install failed". The [INI] section below writes
; [PythonPlugins] nexus_plm=true into the profile's QGIS4.ini, which is what turns the menu on at
; the next start - the same thing plugin\build.py does for a developer.
;
; QGIS4, NOT QGIS3. Measured on 4.2.2: the first start created QGIS\QGIS4\profiles\default with a
; QGIS\QGIS4.ini inside. The QGIS 3 documentation says QGIS3; that is QGIS 3.
;
; WHAT THIS DOES NOT INSTALL: the Nexus PLM tray application, which hosts the Addin Service the
; plugin talks to on localhost. It comes from Nexus.PLM.WPF.Addins.

#define AppName "Nexus PLM for QGIS"
#define AppPublisher "NexusPLM"

; Keep in step with plugin\nexus_plm\nexusplm\commands.py VERSION and metadata.txt.
; tests\test_installer.py fails when they drift.
#define AppVersion "0.1.0"

; Must match the folder in plugin\, which is the Python package QGIS imports.
#define PluginName "nexus_plm"

; The default profile of QGIS 4. Every user has one; a user on a named profile can copy the
; folder across from Settings > User Profiles > Open Active Profile Folder.
#define ProfileDir "{userappdata}\QGIS\QGIS4\profiles\default"
#define PluginsDir ProfileDir + "\python\plugins"

[Setup]
AppId={{3E9B7C21-6D4A-4F0B-9E2C-7A1D5B8F4C63}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
; Nothing is installed here - the plugin goes into QGIS's own profile - but Inno wants an
; application directory for its uninstall record, so it gets one it will not fill.
DefaultDirName={localappdata}\Programs\Nexus PLM QGIS Addin
DefaultGroupName=Nexus PLM
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=NexusPlmQgisAddinSetup
OutputDir=Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; The whole plugin package. __pycache__ is excluded because a stale compiled file is how an old
; module goes on being imported after its source has changed.
Source: "..\plugin\{#PluginName}\*"; DestDir: "{#PluginsDir}\{#PluginName}"; \
  Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs createallsubdirs ignoreversion

[INI]
; Enable the plugin. QGIS keeps the enabled set here; without this line the plugin is installed
; but off. Removed again on uninstall.
Filename: "{#ProfileDir}\QGIS\QGIS4.ini"; Section: "PythonPlugins"; Key: "{#PluginName}"; String: "true"; Flags: uninsdeleteentry

[UninstallDelete]
; Only the plugin's own folder. Its parent holds every other plugin the user has.
Type: filesandordirs; Name: "{#PluginsDir}\{#PluginName}"

[Code]

// The profile is created the first time QGIS runs. Absent, either QGIS is not installed or it has
// never been started - and a plugin dropped into a folder QGIS has not made yet is one QGIS will
// still find, because it scans the same path. Warn, and let the user decide.
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not DirExists(ExpandConstant('{#ProfileDir}')) then
    Result := MsgBox(
      'QGIS 4 was not found for this user.' + #13#10#13#10 +
      'Its profile folder does not exist yet, which means it is either not installed or has ' +
      'never been started. The plugin can still be installed now and will appear the first ' +
      'time QGIS runs.' + #13#10#13#10 +
      'Continue?',
      mbConfirmation, MB_YESNO) = IDYES;
end;

// QGIS reads its plugins when it starts. Installing underneath a running QGIS leaves the user
// looking at a menu bar with no Nexus PLM on it, and concluding the installer failed.
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) then
    // A line may not BEGIN with #13#10: the preprocessor reads a leading '#' as a directive
    // and refuses to compile. Keep the line breaks mid-line.
    MsgBox('Nexus PLM is installed.' + #13#10#13#10 +
           'If QGIS is open, close it and start it again - it reads its plugins at startup. ' +
           'The commands are in the Nexus PLM menu.',
           mbInformation, MB_OK);
end;
