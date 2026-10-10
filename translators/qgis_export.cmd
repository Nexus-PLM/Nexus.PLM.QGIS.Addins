@echo off
rem qgis_export.cmd - the launcher the Translation server runs. It lives beside the manifest at
rem a space-free path, so the server can start it directly; the real interpreter path, which on
rem a default install contains spaces ("C:\Program Files\QGIS 4.2.2\bin\python-qgis.bat"), is
rem only ever expanded INSIDE batch, where "call" quotes it safely. Going through cmd /c with
rem two quoted paths instead loses the first and last quote (cmd's documented /C rule) and
rem breaks on "Program Files".
rem
rem QGIS_PYTHON_CMD must point at python-qgis.bat on the Translation server. Paths travel via
rem QGIS_INPUT / QGIS_OUTPUT, set by the manifest.
if not defined QGIS_PYTHON_CMD (
  echo ERROR: QGIS_PYTHON_CMD is not set; point it at QGIS's bin\python-qgis.bat 1>&2
  exit /b 2
)
if not exist "%QGIS_PYTHON_CMD%" (
  echo ERROR: QGIS_PYTHON_CMD does not exist: %QGIS_PYTHON_CMD% 1>&2
  exit /b 2
)
call "%QGIS_PYTHON_CMD%" "%~dp0qgis_export.py"
exit /b %ERRORLEVEL%
