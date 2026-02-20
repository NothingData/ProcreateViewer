@echo off
REM ===================================================================
REM  ProcreateViewer - Complete Uninstaller
REM  Removes all registrations, settings, DLLs, and application files.
REM  Must run as Administrator for registry cleanup.
REM ===================================================================
setlocal enabledelayedexpansion

echo.
echo  +-------------------------------------------------------+
echo  :       ProcreateViewer - Uninstaller                   :
echo  +-------------------------------------------------------+
echo.
echo  This will:
echo    1. Remove .procreate file associations
echo    2. Unregister the thumbnail handler
echo    3. Delete application files from this folder
echo    4. Clean up thumbnail cache
echo.

set /p confirm="Are you sure you want to uninstall? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo  Cancelled.
    pause
    exit /b 0
)

REM -- Check for admin privileges --
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  Requesting administrator privileges...
    echo.
    powershell -Command "Start-Process -Verb RunAs -FilePath '%~f0' -ArgumentList 'elevated'"
    exit /b
)

echo.
echo  [1/4] Removing file associations...

REM Remove HKCR entries
reg delete "HKCR\.procreate" /f >nul 2>&1
reg delete "HKCR\ProcreateViewer.procreate" /f >nul 2>&1

REM Remove HKCU entries
reg delete "HKCU\Software\Classes\.procreate" /f >nul 2>&1
reg delete "HKCU\Software\Classes\ProcreateViewer.procreate" /f >nul 2>&1

REM Remove HKLM entries
reg delete "HKLM\Software\Classes\.procreate" /f >nul 2>&1
reg delete "HKLM\Software\Classes\ProcreateViewer.procreate" /f >nul 2>&1

echo  [OK] File associations removed.

echo.
echo  [2/4] Unregistering thumbnail handler...

set CLSID={C3A1B2D4-E5F6-4890-ABCD-123456789ABC}

REM Unregister DLL with RegAsm
set REGASM64=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe
set REGASM32=C:\Windows\Microsoft.NET\Framework\v4.0.30319\RegAsm.exe

if exist "%~dp0ProcreateThumbHandler.dll" (
    if exist "%REGASM64%" (
        "%REGASM64%" /unregister "%~dp0ProcreateThumbHandler.dll" >nul 2>&1
    )
    if exist "%REGASM32%" (
        "%REGASM32%" /unregister "%~dp0ProcreateThumbHandler.dll" >nul 2>&1
    )
)

REM Remove COM CLSID
reg delete "HKCR\CLSID\%CLSID%" /f >nul 2>&1
reg delete "HKLM\Software\Classes\CLSID\%CLSID%" /f >nul 2>&1

REM Remove approved shell extensions
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved" /v "%CLSID%" /f >nul 2>&1

echo  [OK] Thumbnail handler unregistered.

echo.
echo  [3/4] Cleaning thumbnail cache...

taskkill /f /im dllhost.exe >nul 2>&1
timeout /t 1 /nobreak >nul

for %%F in ("%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache_*.db") do (
    del /f /q "%%F" >nul 2>&1
)

echo  [OK] Thumbnail cache cleaned.

echo.
echo  [4/4] Removing application files...

REM Remove settings and marker files
del /f /q "%~dp0.procreate_installed" >nul 2>&1
del /f /q "%~dp0.setup_log.txt" >nul 2>&1
del /f /q "%~dp0ProcreateThumbHandler.dll" >nul 2>&1

REM Remove the exe (may fail if running)
del /f /q "%~dp0ProcreateViewer.exe" >nul 2>&1
del /f /q "%~dp0ProcreateViewerNew.exe" >nul 2>&1

echo  [OK] Application files removed.

REM Notify Explorer of changes
powershell -Command "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class SN { [DllImport(\"shell32.dll\")] public static extern void SHChangeNotify(uint a, uint b, IntPtr c, IntPtr d); }'; [SN]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)" >nul 2>&1

echo.
echo  +-------------------------------------------------------+
echo  :        Uninstall Complete!                            :
echo  +-------------------------------------------------------+
echo.
echo  All ProcreateViewer registrations have been removed.
echo  You may now delete this folder.
echo.

REM Self-delete this batch in 3 seconds
echo  This window will close in 5 seconds...
timeout /t 5 /nobreak >nul

REM Try self-delete
(goto) 2>nul & del /f /q "%~f0"
