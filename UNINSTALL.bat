@echo off
REM ProcreateViewer - Uninstaller
REM Right-click → "Run as administrator"
powershell -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs -FilePath powershell.exe -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0scripts\uninstall.ps1\"' -Wait"
pause
