@echo off
REM ===================================================================
REM  ProcreateViewer - One-Click Install
REM  Right-click this file - "Run as administrator"
REM ===================================================================

echo.
echo  +------------------------------------------------+
echo  :    ProcreateViewer - One-Click Installer        :
echo  +------------------------------------------------+
echo.

REM Launch the PowerShell installer elevated
powershell -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs -FilePath powershell.exe -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0scripts\install.ps1\"' -Wait"

echo.
echo  Done! You can close this window.
echo.
pause
