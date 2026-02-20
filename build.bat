@echo off
REM ===================================================================
REM  ProcreateViewer - Complete Build Script
REM  Builds everything from source: .exe, .dll, and Setup installer
REM ===================================================================
setlocal enabledelayedexpansion

echo.
echo  +-------------------------------------------------------+
echo  :       ProcreateViewer - Complete Build Script          :
echo  :                                                       :
echo  :  Builds:                                              :
echo  :    1. Application icon                                :
echo  :    2. ProcreateViewer.exe  (Python - standalone)      :
echo  :    3. ProcreateThumbHandler.dll  (C# shell ext)       :
echo  :    4. ProcreateViewer_Setup.exe  (Inno Setup)         :
echo  +-------------------------------------------------------+
echo.

cd /d "%~dp0"

REM -- Check Python ---------------------------------------------------------
echo [CHECK] Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  ERROR: Python not found!
    echo  Install Python 3.8+ from https://www.python.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo         %%i
echo.

REM ======================================================================
REM  STEP 1: Install dependencies
REM ======================================================================
echo ---------------------------------------------------------
echo  [1/5] Installing Python dependencies...
echo ---------------------------------------------------------
pip install --upgrade pip >nul 2>&1
pip install Pillow pyinstaller pywin32-ctypes lz4
if %errorLevel% neq 0 (
    echo  WARNING: Some packages may not have installed correctly.
)
echo.

REM ======================================================================
REM  STEP 2: Copy logo to icon.ico
REM ======================================================================
echo ---------------------------------------------------------
echo  [2/5] Copying logo.ico to icon.ico...
echo ---------------------------------------------------------
cd src
python generate_icon.py
cd ..
if not exist resources\icon.ico (
    echo  WARNING: logo.ico copy failed, check resources\logo.ico exists
)
echo.

REM ======================================================================
REM  STEP 3: Compile Shell Extension DLL (needed before .exe bundling)
REM ======================================================================
echo ---------------------------------------------------------
echo  [3/5] Compiling ProcreateThumbHandler.dll...
echo ---------------------------------------------------------

if not exist dist mkdir dist

set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" (
    set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
)

if exist "%CSC%" (
    "%CSC%" /target:library ^
        /out:dist\ProcreateThumbHandler.dll ^
        /reference:System.Drawing.dll ^
        /reference:System.IO.Compression.dll ^
        /platform:x64 ^
        /optimize ^
        src\shell_extension\ProcreateThumbHandler.cs

    if exist dist\ProcreateThumbHandler.dll (
        for %%A in (dist\ProcreateThumbHandler.dll) do echo   [OK] ProcreateThumbHandler.dll compiled (%%~zA bytes^)
    ) else (
        echo   [FAIL] DLL compilation failed!
    )
) else (
    echo   ! .NET Framework csc.exe not found - skipping DLL build
    echo     The pre-built DLL in dist\ will be used if available.
)
echo.

REM ======================================================================
REM  STEP 4: Build ProcreateViewer.exe (bundles DLL + icon inside)
REM ======================================================================
echo ---------------------------------------------------------
echo  [4/5] Building ProcreateViewer.exe...
echo         (this takes 30-60 seconds)
echo         The .exe will include the thumbnail DLL inside!
echo ---------------------------------------------------------

set ADD_DLL=
if exist dist\ProcreateThumbHandler.dll (
    set ADD_DLL=--add-data "..\dist\ProcreateThumbHandler.dll;."
)

cd src
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "ProcreateViewer" ^
    --icon "..\resources\icon.ico" ^
    --version-file "..\src\version_info.txt" ^
    --add-data "..\resources;resources" ^
    %ADD_DLL% ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageTk ^
    --hidden-import lz4 ^
    --hidden-import lz4.block ^
    --distpath "..\dist" ^
    --workpath "..\build\pyinstaller" ^
    --specpath "..\build" ^
    procreate_viewer.py

cd ..

if exist dist\ProcreateViewer.exe (
    for %%A in (dist\ProcreateViewer.exe) do echo   [OK] ProcreateViewer.exe built successfully (%%~zA bytes^)
) else (
    echo   [FAIL] Build failed!
    pause
    exit /b 1
)

REM Copy Uninstall.bat to dist
if exist scripts\Uninstall.bat (
    copy /Y scripts\Uninstall.bat dist\Uninstall.bat >nul 2>&1
    echo   [OK] Uninstall.bat copied to dist\
) else (
    echo   [!] scripts\Uninstall.bat not found - skipped
)
echo.

REM ======================================================================
REM  STEP 5: Build Inno Setup Installer (optional)
REM ======================================================================
echo ---------------------------------------------------------
echo  [5/5] Building Setup installer...
echo ---------------------------------------------------------

set ISCC=
where iscc >nul 2>&1
if %errorLevel% equ 0 (
    set ISCC=iscc
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if defined ISCC (
    if not exist release mkdir release
    "%ISCC%" installer\ProcreateViewer_Setup.iss
    if exist release\ProcreateViewer_Setup_v1.0.0.exe (
        for %%A in (release\ProcreateViewer_Setup_v1.0.0.exe) do echo   [OK] Installer built: release\ProcreateViewer_Setup_v1.0.0.exe (%%~zA bytes^)
    ) else (
        echo   [FAIL] Installer build failed
    )
) else (
    echo   ! Inno Setup not found - skipping installer build
    echo     Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    echo     Then re-run this script to build the Setup.exe
)

echo.
echo  +-------------------------------------------------------+
echo  :                 BUILD COMPLETE!                       :
echo  +-------------------------------------------------------+
echo  :
if exist dist\ProcreateViewer.exe (
echo  :  [OK]   dist\ProcreateViewer.exe
) else (
echo  :  [FAIL] dist\ProcreateViewer.exe  MISSING
)
if exist dist\ProcreateThumbHandler.dll (
echo  :  [OK]   dist\ProcreateThumbHandler.dll
) else (
echo  :  [FAIL] dist\ProcreateThumbHandler.dll  MISSING
)
if exist dist\Uninstall.bat (
echo  :  [OK]   dist\Uninstall.bat
) else (
echo  :  [ - ]  dist\Uninstall.bat  MISSING
)
if exist release\ProcreateViewer_Setup_v1.0.0.exe (
echo  :  [OK]   release\ProcreateViewer_Setup_v1.0.0.exe
) else (
echo  :  [ - ]  release\ProcreateViewer_Setup_v1.0.0.exe  (Inno Setup needed^)
)
echo  :
echo  +-------------------------------------------------------+
echo.
pause
