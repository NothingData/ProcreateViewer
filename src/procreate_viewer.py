"""
Procreate Viewer -- Windows GUI Application
============================================
A standalone viewer for .procreate files.
Displays thumbnail / composite preview, layer info, and file metadata.
Supports export to PNG / JPEG / BMP / TIFF.

On first run the .exe automatically:
  - Associates .procreate files with this viewer
  - Registers the COM thumbnail handler for Explorer previews
  - Extracts ProcreateThumbHandler.dll next to the .exe

Author: ProcreateViewer (Open Source)
License: MIT
"""

import os
import sys
import subprocess
import tempfile
import shutil
import threading
import traceback as _tb
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from PIL import Image, ImageTk

# -- Ensure our module is importable when running from any directory --
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
    # PyInstaller --onefile extracts resources to sys._MEIPASS
    _RES_DIR = getattr(sys, "_MEIPASS", _BASE_DIR)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _RES_DIR = _BASE_DIR
sys.path.insert(0, _BASE_DIR)

from procreate_reader import ProcreateFile  # noqa: E402

# =====================================================================
# Auto-Setup:  file association  +  thumbnail handler  +  DLL extract
# =====================================================================

def _get_marker_path() -> str:
    """Return path to the 'already installed' marker file."""
    return os.path.join(_BASE_DIR, ".procreate_installed")


def _is_already_installed() -> bool:
    """Check if we already ran the auto-setup for this exe location.

    Checks the marker file first.  If missing, falls back to the
    Windows registry – the Inno Setup installer writes registry
    keys but may not always create the marker file in the same
    directory the exe actually runs from.
    """
    marker = _get_marker_path()
    if os.path.isfile(marker):
        try:
            with open(marker, "r") as f:
                stored = f.read().strip()
            # Re-install if exe moved to a different folder
            if getattr(sys, "frozen", False):
                if stored == os.path.abspath(sys.executable):
                    return True
            else:
                return True
        except Exception:
            pass

    # Fallback: check if Inno Setup (or a previous run) already
    # registered the file association + thumbnail handler.
    if _check_file_association():
        # Registry is good – write the marker so future checks
        # are instant.
        try:
            with open(marker, "w") as f:
                if getattr(sys, "frozen", False):
                    f.write(os.path.abspath(sys.executable))
                else:
                    f.write("dev")
            _hide_file(marker)
        except Exception:
            pass
        return True

    return False


def _extract_dll() -> str:
    """Extract ProcreateThumbHandler.dll next to the exe (bundled data)."""
    dll_dest = os.path.join(_BASE_DIR, "ProcreateThumbHandler.dll")
    if os.path.isfile(dll_dest):
        return dll_dest

    # PyInstaller stores --add-data files in _MEIPASS (onefile) or _BASE_DIR
    search_dirs = [_BASE_DIR]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.insert(0, meipass)

    for d in search_dirs:
        src = os.path.join(d, "ProcreateThumbHandler.dll")
        if os.path.isfile(src) and os.path.normcase(src) != os.path.normcase(dll_dest):
            try:
                shutil.copy2(src, dll_dest)
                return dll_dest
            except OSError:
                pass
        # also check a sub-folder
        src2 = os.path.join(d, "shell_extension", "ProcreateThumbHandler.dll")
        if os.path.isfile(src2):
            try:
                shutil.copy2(src2, dll_dest)
                return dll_dest
            except OSError:
                pass

    return dll_dest  # may not exist -- caller should check


def _extract_icon() -> str:
    """Ensure icon.ico exists next to the exe as a permanent file.

    When packaged as PyInstaller --onefile, resources in _MEIPASS are
    in a temp folder that changes every launch.  Registry entries need
    a stable path, so we copy the icon next to the .exe.
    """
    icon_dest = os.path.join(_BASE_DIR, "icon.ico")
    if os.path.isfile(icon_dest):
        return icon_dest

    # Search bundled resources
    search_dirs = [_BASE_DIR]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.insert(0, meipass)

    for d in search_dirs:
        for sub in [os.path.join(d, "resources", "icon.ico"),
                    os.path.join(d, "icon.ico")]:
            if os.path.isfile(sub) and os.path.normcase(sub) != os.path.normcase(icon_dest):
                try:
                    shutil.copy2(sub, icon_dest)
                    return icon_dest
                except OSError:
                    pass

    # Last resort: use the exe itself as icon source
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return icon_dest


def _hide_file(path: str) -> None:
    """Mark a file as hidden on Windows (silently ignored on failure)."""
    try:
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02
        attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
        if attrs != -1 and not (attrs & FILE_ATTRIBUTE_HIDDEN):
            ctypes.windll.kernel32.SetFileAttributesW(
                path, attrs | FILE_ATTRIBUTE_HIDDEN
            )
    except Exception:
        pass


def _create_desktop_shortcut() -> bool:
    """Create a Desktop shortcut to ProcreateViewer.exe using PowerShell.

    Uses COM WScript.Shell — works on every Windows version without
    extra dependencies.  Returns True on success.
    """
    if not getattr(sys, "frozen", False):
        return False

    exe_path = os.path.abspath(sys.executable)
    icon_path = _extract_icon()
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        # Fallback for localised Windows (OneDrive Desktop, etc.)
        try:
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(260)
            # CSIDL_DESKTOPDIRECTORY = 0x0010
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
            desktop = buf.value
        except Exception:
            return False

    lnk = os.path.join(desktop, "Procreate Viewer.lnk")

    # Build a tiny PS1 that creates the .lnk via COM
    ps_lines = [
        "$ws = New-Object -ComObject WScript.Shell",
        f"$s = $ws.CreateShortcut('{lnk.replace(chr(39), chr(39)+chr(39))}')",
        f"$s.TargetPath = '{exe_path.replace(chr(39), chr(39)+chr(39))}'",
        f"$s.WorkingDirectory = '{os.path.dirname(exe_path).replace(chr(39), chr(39)+chr(39))}'",
        f"$s.IconLocation = '{icon_path.replace(chr(39), chr(39)+chr(39))},0'",
        "$s.Description = 'Procreate Viewer'",
        "$s.Save()",
    ]
    try:
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass",
             "-WindowStyle", "Hidden", "-Command",
             ";".join(ps_lines)],
            check=True, timeout=15,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return True
    except Exception:
        return False


def _remove_desktop_shortcut() -> bool:
    """Delete the Desktop shortcut if it exists. Returns True on success."""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        try:
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
            desktop = buf.value
        except Exception:
            return False
    lnk = os.path.join(desktop, "Procreate Viewer.lnk")
    if os.path.isfile(lnk):
        try:
            os.remove(lnk)
            return True
        except Exception:
            return False
    return True


def _build_setup_ps1(viewer_exe: str, icon_path: str, dll_path: str) -> str:
    """Build a PowerShell script that registers everything in one shot."""

    has_dll = os.path.isfile(dll_path)
    dll_path_fwd = dll_path.replace("\\", "/")
    clsid = "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"
    thumb_guid = "{e357fccd-a995-4576-b01f-234630154e96}"
    asm_name = "ProcreateThumbHandler, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"

    # Escape single quotes in paths for PowerShell single-quoted strings
    def _ps_esc(s: str) -> str:
        return s.replace("'", "''")

    lines = [
        "# ProcreateViewer - Auto Setup (runs elevated)",
        "# Use Continue so one section failing does not skip the rest",
        "$ErrorActionPreference = 'Continue'",
        "",
        "New-PSDrive -PSProvider Registry -Root HKEY_CLASSES_ROOT -Name HKCR -EA SilentlyContinue | Out-Null",
        "",
        f"$viewer = '{_ps_esc(viewer_exe)}'",
        f"$icon   = '{_ps_esc(icon_path)}'",
        f"$openCmd = '\"" + _ps_esc(viewer_exe) + "\" \"%1\"'",
        "$ext    = '.procreate'",
        "$progId = 'ProcreateViewer.procreate'",
        "$desc   = 'Procreate Artwork'",
        "",
        "# --- 1. File Association ---",
        'New-Item -Path "HKCR:\\$progId" -Force | Out-Null',
        'Set-ItemProperty -Path "HKCR:\\$progId" -Name "(Default)" -Value $desc',
        'New-Item -Path "HKCR:\\$progId\\DefaultIcon" -Force | Out-Null',
        'Set-ItemProperty -Path "HKCR:\\$progId\\DefaultIcon" -Name "(Default)" -Value "`"$icon`",0"',
        'New-Item -Path "HKCR:\\$progId\\shell\\open\\command" -Force | Out-Null',
        'Set-ItemProperty -Path "HKCR:\\$progId\\shell\\open\\command" -Name "(Default)" -Value $openCmd',
        'Set-ItemProperty -Path "HKCR:\\$progId\\shell\\open" -Name "FriendlyAppName" -Value "Procreate Viewer" -Force',
        "",
        'New-Item -Path "HKCR:\\$ext" -Force | Out-Null',
        'Set-ItemProperty -Path "HKCR:\\$ext" -Name "(Default)" -Value $progId',
        'Set-ItemProperty -Path "HKCR:\\$ext" -Name "Content Type" -Value "application/x-procreate"',
        'Set-ItemProperty -Path "HKCR:\\$ext" -Name "PerceivedType" -Value "image"',
        "",
        'New-Item -Path "HKCR:\\$ext\\OpenWithProgids" -Force | Out-Null',
        'New-ItemProperty -Path "HKCR:\\$ext\\OpenWithProgids" -Name $progId -PropertyType None -Force -EA SilentlyContinue | Out-Null',
        "",
        '# Context menu',
        'New-Item -Path "HKCR:\\$ext\\shell\\ProcreateViewer\\command" -Force | Out-Null',
        'Set-ItemProperty -Path "HKCR:\\$ext\\shell\\ProcreateViewer" -Name "(Default)" -Value "Open with Procreate Viewer"',
        'Set-ItemProperty -Path "HKCR:\\$ext\\shell\\ProcreateViewer" -Name "Icon" -Value $icon',
        'Set-ItemProperty -Path "HKCR:\\$ext\\shell\\ProcreateViewer\\command" -Name "(Default)" -Value $openCmd',
        "",
        '# Current-user fallback',
        'New-Item -Path "HKCU:\\Software\\Classes\\$ext" -Force | Out-Null',
        'Set-ItemProperty -Path "HKCU:\\Software\\Classes\\$ext" -Name "(Default)" -Value $progId',
        'New-Item -Path "HKCU:\\Software\\Classes\\$progId\\shell\\open\\command" -Force | Out-Null',
        'Set-ItemProperty -Path "HKCU:\\Software\\Classes\\$progId\\shell\\open\\command" -Name "(Default)" -Value $openCmd',
        "Log 'File association registered'",
    ]

    if has_dll:
        lines += [
            "",
            "# --- 2. Thumbnail Handler (COM DLL) ---",
            "Log 'Registering thumbnail handler DLL'",
            f"$dllPath   = '{_ps_esc(dll_path)}'",
            f"$clsid     = '{clsid}'",
            f"$thumbGuid = '{thumb_guid}'",
            f"$codeBase  = 'file:///{dll_path_fwd}'",
            f"$asmName   = '{asm_name}'",
            "Log \"DLL path: $dllPath\"",
            "Log \"DLL exists: $(Test-Path $dllPath)\"",
            "",
            "# RegAsm (64-bit + 32-bit) -- errors are OK",
            "$regasm64 = 'C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\RegAsm.exe'",
            "$regasm32 = 'C:\\Windows\\Microsoft.NET\\Framework\\v4.0.30319\\RegAsm.exe'",
            "Log 'Running RegAsm...'",
            "try { if (Test-Path $regasm64) { & $regasm64 /codebase \"`\"$dllPath`\"\" 2>&1 | Out-Null; Log \"RegAsm64 exit: $LASTEXITCODE\" } } catch { Log \"RegAsm64 error: $_\" }",
            "try { if (Test-Path $regasm32) { & $regasm32 /codebase \"`\"$dllPath`\"\" 2>&1 | Out-Null; Log \"RegAsm32 exit: $LASTEXITCODE\" } } catch { Log \"RegAsm32 error: $_\" }",
            "",
            "# InprocServer32 (HKCR + HKLM)",
            "foreach ($root in @(",
            "    \"HKCR:\\CLSID\\$clsid\\InprocServer32\",",
            "    \"HKLM:\\Software\\Classes\\CLSID\\$clsid\\InprocServer32\"",
            ")) {",
            "    New-Item -Path $root -Force -EA SilentlyContinue | Out-Null",
            "    Set-ItemProperty -Path $root -Name '(Default)'       -Value 'mscoree.dll'   -EA SilentlyContinue",
            "    Set-ItemProperty -Path $root -Name 'Assembly'        -Value $asmName         -EA SilentlyContinue",
            "    Set-ItemProperty -Path $root -Name 'Class'           -Value 'ProcreateThumbHandler.ProcreateThumbProvider' -EA SilentlyContinue",
            "    Set-ItemProperty -Path $root -Name 'CodeBase'        -Value $codeBase        -EA SilentlyContinue",
            "    Set-ItemProperty -Path $root -Name 'RuntimeVersion'  -Value 'v4.0.30319'    -EA SilentlyContinue",
            "    Set-ItemProperty -Path $root -Name 'ThreadingModel'  -Value 'Both'           -EA SilentlyContinue",
            "}",
            "",
            "# CLSID properties",
            "Set-ItemProperty -Path \"HKCR:\\CLSID\\$clsid\" -Name '(Default)' -Value 'Procreate Thumbnail Handler' -EA SilentlyContinue",
            "New-ItemProperty -Path \"HKCR:\\CLSID\\$clsid\" -Name 'DisableProcessIsolation' -Value 1 -PropertyType DWord -Force -EA SilentlyContinue | Out-Null",
            "New-Item -Path \"HKCR:\\CLSID\\$clsid\\Implemented Categories\\{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}\" -Force -EA SilentlyContinue | Out-Null",
            "",
            "# ShellEx -> thumbnail GUID -> our CLSID",
            "New-Item -Path \"HKCR:\\$ext\\ShellEx\\$thumbGuid\" -Force -EA SilentlyContinue | Out-Null",
            "# Use .NET API to set default value (Set-ItemProperty '(Default)' is unreliable on HKCR PSDrive)",
            "$shellKey = [Microsoft.Win32.Registry]::ClassesRoot.OpenSubKey('.procreate\\ShellEx\\' + $thumbGuid, $true)",
            "if ($shellKey) { $shellKey.SetValue($null, $clsid); $shellKey.Close() }",
            "New-Item -Path \"HKLM:\\Software\\Classes\\$ext\\ShellEx\\$thumbGuid\" -Force -EA SilentlyContinue | Out-Null",
            "$shellKey2 = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('Software\\Classes\\.procreate\\ShellEx\\' + $thumbGuid, $true)",
            "if ($shellKey2) { $shellKey2.SetValue($null, $clsid); $shellKey2.Close() }",
            "",
            "# Approved shell extensions",
            "$ap = 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Shell Extensions\\Approved'",
            "if (Test-Path $ap) { Set-ItemProperty -Path $ap -Name $clsid -Value 'Procreate Thumbnail Handler' -EA SilentlyContinue }",
            "",
            "# Clear thumbnail cache",
            "Stop-Process -Name 'dllhost' -Force -EA SilentlyContinue",
            "$cache = \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\"",
            "Get-ChildItem \"$cache\\thumbcache_*.db\" -EA SilentlyContinue | ForEach-Object { try { Remove-Item $_.FullName -Force } catch {} }",
        ]

    # Add logging to help diagnose failures
    _log_file = _ps_esc(os.path.join(_BASE_DIR, ".setup_log.txt"))
    lines.insert(3, f"$logFile = '{_log_file}'")
    lines.insert(4, "function Log($msg) { Add-Content -Path $logFile -Value \"$(Get-Date -F 'HH:mm:ss') $msg\" -Encoding UTF8 -EA SilentlyContinue }")
    lines.insert(5, "Log 'Auto-setup PS1 started'")
    lines.insert(6, "Log \"Viewer: $viewer\"")
    lines.insert(7, "Log \"Icon: $icon\"")

    lines += [
        "",
        "# --- 3. Notify Explorer ---",
        "Log 'Notifying Explorer of changes'",
        "Add-Type -TypeDefinition @\"",
        "using System;",
        "using System.Runtime.InteropServices;",
        "public class ShellNotify {",
        "    [DllImport(\"shell32.dll\")]",
        "    public static extern void SHChangeNotify(uint wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);",
        "}",
        "\"@ -EA SilentlyContinue",
        "[ShellNotify]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)",
        "Log 'Auto-setup PS1 completed successfully'",
    ]

    return "\n".join(lines)


def _run_ps1_elevated(ps1_path: str, timeout: int = 120) -> bool:
    """Run a PowerShell script with UAC elevation using ShellExecuteW.

    Uses the native Windows ShellExecuteW API with 'runas' verb.
    This is the most reliable way to request admin privileges —
    no nested PowerShell quoting issues.
    """
    import ctypes
    log = os.path.join(_BASE_DIR, ".setup_log.txt")

    try:
        # ShellExecuteW with 'runas' triggers UAC directly
        params = f'-WindowStyle Hidden -ExecutionPolicy Bypass -File "{ps1_path}"'
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "runas",        # verb → triggers UAC
            "powershell.exe",
            params,
            None,           # working directory
            0,              # SW_HIDE
        )
        # ShellExecuteW returns > 32 on success
        if ret <= 32:
            with open(log, "a") as f:
                f.write(f"ShellExecuteW returned {ret} (error)\n")
            return False

        # ShellExecuteW is async — wait for the PS1 log to confirm completion
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(1.5)
            # Check if our PS1 wrote its "completed successfully" line
            if os.path.isfile(log):
                try:
                    with open(log, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if "PS1 completed successfully" in content:
                        with open(log, "a") as f:
                            f.write("_run_ps1_elevated: SUCCESS (confirmed via log)\n")
                        return True
                except Exception:
                    pass

        # Timeout — check if anything was written at all
        with open(log, "a") as f:
            f.write(f"_run_ps1_elevated: TIMEOUT after {timeout}s\n")
        # Still return True if ShellExecute launched OK — the PS1 may
        # have finished but just didn't write the final log line
        return True

    except Exception as exc:
        with open(log, "a") as f:
            f.write(f"_run_ps1_elevated FAIL: {type(exc).__name__}: {exc}\n")
        # Fallback: try the subprocess approach
        return _run_ps1_fallback(ps1_path, timeout)


def _run_ps1_fallback(ps1_path: str, timeout: int = 120) -> bool:
    """Fallback: visible PowerShell window for elevation."""
    log = os.path.join(_BASE_DIR, ".setup_log.txt")
    try:
        subprocess.run(
            [
                "powershell.exe", "-ExecutionPolicy", "Bypass", "-Command",
                f'Start-Process powershell.exe -Verb RunAs '
                f'-ArgumentList "-ExecutionPolicy Bypass -File \\"{ps1_path}\\"" '
                f'-Wait',
            ],
            check=True,
            timeout=timeout,
        )
        with open(log, "a") as f:
            f.write("_run_ps1_fallback: SUCCESS\n")
        return True
    except Exception as exc:
        with open(log, "a") as f:
            f.write(f"_run_ps1_fallback FAIL: {type(exc).__name__}: {exc}\n")
        return False


def _get_setup_paths():
    """Return (viewer_exe, icon_path, dll_path) used by setup scripts."""
    if getattr(sys, "frozen", False):
        viewer_exe = os.path.abspath(sys.executable)
    else:
        viewer_exe = os.path.abspath(
            os.path.join(_BASE_DIR, "procreate_viewer.py")
        )
    # Extract icon to a stable path next to the exe (not in _MEIPASS temp)
    icon_path = _extract_icon()
    dll_path = _extract_dll()
    return viewer_exe, icon_path, dll_path


def _check_file_association() -> bool:
    """Check if .procreate is associated with this viewer."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Classes\.procreate"
        )
        val, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        return val == "ProcreateViewer.procreate"
    except Exception:
        return False


def _check_thumbnail_handler() -> bool:
    """Check if the COM thumbnail handler is registered."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT,
            r".procreate\ShellEx\{e357fccd-a995-4576-b01f-234630154e96}",
        )
        val, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        return val == "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"
    except Exception:
        return False


def _find_inno_uninstaller() -> Optional[str]:
    """Find the Inno Setup uninstaller for ProcreateViewer if present.

    The Inno Setup installer writes an UninstallString to the registry
    under HKLM (or HKCU) Uninstall keys.  We look it up by our AppId.
    """
    import winreg
    app_id = "{B4C5D6E7-F8A9-0B1C-2D3E-4F5A6B7C8D9E}_is1"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for wow in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                    winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
            try:
                key = winreg.OpenKey(
                    hive,
                    rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_id}",
                    0, wow,
                )
                val, _ = winreg.QueryValueEx(key, "UninstallString")
                winreg.CloseKey(key)
                # val is like '"C:\Program Files\Procreate Viewer\unins000.exe"'
                path = val.strip('"')
                if os.path.isfile(path):
                    return path
            except Exception:
                continue
    return None


def _build_uninstall_ps1() -> str:
    """Build a PowerShell script that removes all registrations."""
    clsid = "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"
    return "\n".join([
        "$ErrorActionPreference = 'Continue'",
        "New-PSDrive -PSProvider Registry -Root HKEY_CLASSES_ROOT "
        "-Name HKCR -EA SilentlyContinue | Out-Null",
        "",
        "Remove-Item 'HKCR:\\.procreate' -Recurse -Force -EA SilentlyContinue",
        "Remove-Item 'HKCR:\\ProcreateViewer.procreate' -Recurse -Force "
        "-EA SilentlyContinue",
        "Remove-Item 'HKCU:\\Software\\Classes\\.procreate' -Recurse -Force "
        "-EA SilentlyContinue",
        "Remove-Item 'HKCU:\\Software\\Classes\\ProcreateViewer.procreate' "
        "-Recurse -Force -EA SilentlyContinue",
        "",
        f"Remove-Item 'HKCR:\\CLSID\\{clsid}' -Recurse -Force "
        f"-EA SilentlyContinue",
        f"Remove-Item 'HKLM:\\Software\\Classes\\CLSID\\{clsid}' -Recurse "
        f"-Force -EA SilentlyContinue",
        "Remove-Item 'HKLM:\\Software\\Classes\\.procreate' -Recurse -Force "
        "-EA SilentlyContinue",
        "",
        "$ap = 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion"
        "\\Shell Extensions\\Approved'",
        f"if (Test-Path $ap) {{ Remove-ItemProperty -Path $ap "
        f"-Name '{clsid}' -EA SilentlyContinue }}",
        "",
        "Add-Type -TypeDefinition @\"",
        "using System;",
        "using System.Runtime.InteropServices;",
        "public class ShellNotify2 {",
        "    [DllImport(\"shell32.dll\")]",
        "    public static extern void SHChangeNotify(uint wEventId, "
        "uint uFlags, IntPtr dwItem1, IntPtr dwItem2);",
        "}",
        "\"@ -EA SilentlyContinue",
        "[ShellNotify2]::SHChangeNotify(0x08000000, 0, "
        "[IntPtr]::Zero, [IntPtr]::Zero)",
    ])


def run_auto_setup() -> bool:
    """Silently register file association + thumbnail handler.

    Uses hidden PowerShell — no console windows.  Only the standard
    Windows UAC prompt is shown.  Returns True on success.
    """
    if _is_already_installed():
        return True

    viewer_exe, icon_path, dll_path = _get_setup_paths()
    ps1 = _build_setup_ps1(viewer_exe, icon_path, dll_path)
    tmp = os.path.join(tempfile.gettempdir(), "procreate_auto_setup.ps1")
    with open(tmp, "w", encoding="utf-8-sig") as f:
        f.write(ps1)

    ok = _run_ps1_elevated(tmp)

    if ok:
        marker = _get_marker_path()
        try:
            with open(marker, "w") as f:
                f.write(viewer_exe)
            _hide_file(marker)
        except Exception:
            pass
        _hide_file(os.path.join(_BASE_DIR, ".setup_log.txt"))

    try:
        os.remove(tmp)
    except Exception:
        pass
    return ok


# ═══════════════════════════════════════════════════════════════════════
# Theme colours (Procreate-inspired dark theme)
# ═══════════════════════════════════════════════════════════════════════
COLORS = {
    "bg":        "#1A1A2E",
    "bg2":       "#16213E",
    "panel":     "#0F3460",
    "accent":    "#E94560",
    "accent2":   "#533483",
    "text":      "#EAEAEA",
    "text_dim":  "#8899AA",
    "border":    "#2A2A4A",
    "canvas_bg": "#0D0D1A",
    "btn":       "#0F3460",
    "btn_hover": "#1A4A7A",
    "success":   "#00D2A0",
    "warning":   "#FFA500",
}

APP_TITLE = "Procreate Viewer"
APP_VERSION = "1.0.0"
WINDOW_MIN_W = 960
WINDOW_MIN_H = 640


# ═══════════════════════════════════════════════════════════════════════
# Helper: Tooltip
# ═══════════════════════════════════════════════════════════════════════
class ToolTip:
    """Simple tooltip for widgets."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#333", foreground="#EEE",
            relief="solid", borderwidth=1,
            font=("Segoe UI", 9),
            padx=6, pady=3,
        )
        label.pack()

    def hide(self, _event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# ═══════════════════════════════════════════════════════════════════════
# Themed Message Dialogs (match the dark Procreate-inspired theme)
# ═══════════════════════════════════════════════════════════════════════

class _ThemedDialog(tk.Toplevel):
    """Base class for dark-themed message dialogs."""

    # Unicode symbols used as icons
    _ICONS = {
        "info":    "\u2139",   # ℹ
        "success": "\u2714",   # ✔
        "warning": "\u26A0",   # ⚠
        "error":   "\u2716",   # ✖
        "ask":     "?",
    }
    _ICON_COLORS = {
        "info":    COLORS["accent"],
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "error":   "#FF4444",
        "ask":     COLORS["accent2"],
    }

    def __init__(self, parent, title, message, kind="info",
                 buttons=("OK",), default_btn=0):
        super().__init__(parent)
        self.result = None
        self._kind = kind

        self.title(title)
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Icon
        icon_path = os.path.join(_RES_DIR, "resources", "icon.ico")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(_BASE_DIR, "resources", "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # ── Build UI ──
        # Accent strip at top
        accent_color = self._ICON_COLORS.get(kind, COLORS["accent"])
        strip = tk.Frame(self, bg=accent_color, height=4)
        strip.pack(fill="x")

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=(20, 10))

        # Icon + title row
        top_row = tk.Frame(body, bg=COLORS["bg"])
        top_row.pack(fill="x", pady=(0, 12))

        icon_char = self._ICONS.get(kind, "\u2139")
        tk.Label(
            top_row, text=icon_char,
            font=("Segoe UI", 26), bg=COLORS["bg"],
            fg=accent_color,
        ).pack(side="left", padx=(0, 14))

        tk.Label(
            top_row, text=title,
            font=("Segoe UI Semibold", 14), bg=COLORS["bg"],
            fg=COLORS["text"], anchor="w", wraplength=360,
        ).pack(side="left", fill="x", expand=True)

        # Message
        tk.Label(
            body, text=message,
            font=("Segoe UI", 10), bg=COLORS["bg"],
            fg=COLORS["text"], anchor="w", justify="left",
            wraplength=400,
        ).pack(fill="x", pady=(0, 4))

        # Separator
        tk.Frame(body, bg=COLORS["border"], height=1).pack(fill="x", pady=(12, 0))

        # Buttons
        btn_frame = tk.Frame(self, bg=COLORS["bg"])
        btn_frame.pack(fill="x", padx=28, pady=(8, 20))

        for i, label in enumerate(buttons):
            is_primary = (i == default_btn)
            btn = tk.Button(
                btn_frame, text=f"  {label}  ",
                font=("Segoe UI Semibold" if is_primary else "Segoe UI", 10),
                bg=accent_color if is_primary else COLORS["bg2"],
                fg="white" if is_primary else COLORS["text"],
                activebackground=COLORS["btn_hover"],
                activeforeground="white",
                relief="flat", bd=0, padx=20, pady=8,
                cursor="hand2",
                command=lambda lbl=label: self._click(lbl),
            )
            btn.pack(side="right", padx=(6, 0))
            if is_primary:
                self._default_btn = btn

        # Center on parent
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 420)
        h = self.winfo_reqheight()
        self.geometry(f"{w}x{h}")
        if parent and parent.winfo_exists():
            px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        else:
            px = (self.winfo_screenwidth() - w) // 2
            py = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

        if parent and parent.winfo_exists():
            self.transient(parent)
        self.grab_set()
        self.focus_force()
        if hasattr(self, '_default_btn'):
            self._default_btn.focus_set()
        self.bind("<Return>", lambda e: self._click(buttons[default_btn]))
        if "Cancel" in buttons or "No" in buttons:
            cancel = "Cancel" if "Cancel" in buttons else "No"
            self.bind("<Escape>", lambda e: self._click(cancel))

    def _click(self, label):
        self.result = label
        self.destroy()

    def _on_close(self):
        self.result = None
        self.destroy()


def themed_showinfo(title, message, parent=None):
    """Show an info dialog in the app's dark theme."""
    dlg = _ThemedDialog(parent, title, message, kind="info")
    dlg.wait_window()


def themed_showsuccess(title, message, parent=None):
    """Show a success dialog in the app's dark theme."""
    dlg = _ThemedDialog(parent, title, message, kind="success")
    dlg.wait_window()


def themed_showwarning(title, message, parent=None):
    """Show a warning dialog in the app's dark theme."""
    dlg = _ThemedDialog(parent, title, message, kind="warning")
    dlg.wait_window()


def themed_showerror(title, message, parent=None):
    """Show an error dialog in the app's dark theme."""
    dlg = _ThemedDialog(parent, title, message, kind="error")
    dlg.wait_window()


def themed_askyesno(title, message, parent=None) -> bool:
    """Show a yes/no dialog in the app's dark theme. Returns True for Yes."""
    dlg = _ThemedDialog(
        parent, title, message, kind="ask",
        buttons=("No", "Yes"), default_btn=1,
    )
    dlg.wait_window()
    return dlg.result == "Yes"


# ═══════════════════════════════════════════════════════════════════════
# First-Run Setup Dialog (beautiful welcome + progress bar)
# ═══════════════════════════════════════════════════════════════════════
class SetupDialog(tk.Toplevel):
    """First-run setup dialog with option cards and animated progress."""

    def __init__(self, parent):
        super().__init__(parent)
        self.result = False
        self._installing = False

        self.title("Procreate Viewer \u2014 Setup")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.geometry("500x520")
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

        icon_path = os.path.join(_RES_DIR, "resources", "icon.ico")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(_BASE_DIR, "resources", "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 500) // 2
        y = (self.winfo_screenheight() - 520) // 2
        self.geometry(f"+{x}+{y}")

        self._build_ui()
        # NOTE: do NOT call self.transient(parent) here. If the parent
        # is withdrawn (first-run flow), a transient Toplevel is hidden
        # together with its parent, which causes the mainloop to exit
        # immediately because no mapped windows remain.
        self.grab_set()
        self.focus_force()

    # ── UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Accent header
        header = tk.Frame(self, bg=COLORS["accent"], height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        hdr_inner = tk.Frame(header, bg=COLORS["accent"])
        hdr_inner.pack(side="left", fill="both", expand=True, padx=24, pady=12)
        tk.Label(
            hdr_inner, text="Procreate Viewer",
            font=("Segoe UI Semibold", 18),
            bg=COLORS["accent"], fg="white", anchor="w",
        ).pack(fill="x")
        tk.Label(
            hdr_inner, text="First-time setup",
            font=("Segoe UI", 11),
            bg=COLORS["accent"], fg="#FFD0D8", anchor="w",
        ).pack(fill="x")

        # Body
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=20)

        tk.Label(
            body,
            text="This will configure Windows to work with\n"
                 ".procreate files. You only need to do this once.",
            font=("Segoe UI", 10), bg=COLORS["bg"], fg=COLORS["text"],
            anchor="w", justify="left",
        ).pack(fill="x", pady=(0, 18))

        # Option cards
        self.var_assoc = tk.BooleanVar(value=True)
        self.var_thumbs = tk.BooleanVar(value=True)
        self._option_card(
            body, self.var_assoc,
            "File Association",
            "Double-click .procreate files to open them here",
        )
        self._option_card(
            body, self.var_thumbs,
            "Explorer Thumbnails",
            "See artwork previews in File Explorer like PNG files",
        )

        self.var_shortcut = tk.BooleanVar(value=True)
        self._option_card(
            body, self.var_shortcut,
            "Desktop Shortcut",
            "Place a Procreate Viewer icon on your Desktop",
        )

        tk.Label(
            body,
            text="Windows will ask for administrator permission.",
            font=("Segoe UI", 9), bg=COLORS["bg"],
            fg=COLORS["text_dim"], anchor="w",
        ).pack(fill="x", pady=(14, 0))

        # Progress area
        self._pf = tk.Frame(body, bg=COLORS["bg"])
        self._pf.pack(fill="x", pady=(12, 0))

        self._plbl = tk.Label(
            self._pf, text="", font=("Segoe UI", 9),
            bg=COLORS["bg"], fg=COLORS["success"], anchor="w",
        )
        self._plbl.pack(fill="x")

        style = ttk.Style()
        style.configure(
            "Setup.Horizontal.TProgressbar",
            background=COLORS["accent"], troughcolor=COLORS["bg2"],
        )
        self._pbar = ttk.Progressbar(
            self._pf, style="Setup.Horizontal.TProgressbar",
            mode="determinate", maximum=100,
        )
        self._pbar_shown = False

        # Buttons
        bf = tk.Frame(self, bg=COLORS["bg"])
        bf.pack(fill="x", padx=28, pady=(0, 22))

        self._btn_skip = tk.Button(
            bf, text="Skip",
            font=("Segoe UI", 10), bg=COLORS["bg2"],
            fg=COLORS["text_dim"],
            activebackground=COLORS["bg2"],
            activeforeground=COLORS["text"],
            relief="flat", bd=0, padx=20, pady=8,
            cursor="hand2", command=self._on_skip,
        )
        self._btn_skip.pack(side="left")

        self._btn_go = tk.Button(
            bf, text="   Install   ",
            font=("Segoe UI Semibold", 11), bg=COLORS["accent"],
            fg="white", activebackground="#C03050",
            activeforeground="white",
            relief="flat", bd=0, padx=28, pady=9,
            cursor="hand2", command=self._on_install,
        )
        self._btn_go.pack(side="right")

    def _option_card(self, parent, var, title, desc):
        card = tk.Frame(parent, bg=COLORS["bg2"])
        card.pack(fill="x", pady=4, ipady=8)

        tk.Checkbutton(
            card, variable=var,
            bg=COLORS["bg2"], fg=COLORS["text"],
            selectcolor=COLORS["bg"],
            activebackground=COLORS["bg2"],
            activeforeground=COLORS["text"],
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(10, 4))

        tf = tk.Frame(card, bg=COLORS["bg2"])
        tf.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(
            tf, text=title, font=("Segoe UI Semibold", 10),
            bg=COLORS["bg2"], fg=COLORS["text"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            tf, text=desc, font=("Segoe UI", 9),
            bg=COLORS["bg2"], fg=COLORS["text_dim"], anchor="w",
        ).pack(fill="x")

    # ── Actions ────────────────────────────────────────────────────────

    def _on_skip(self):
        if self._installing:
            return
        self.result = False
        # Write marker so we don't ask again
        try:
            exe = (os.path.abspath(sys.executable)
                   if getattr(sys, "frozen", False) else "dev")
            marker = _get_marker_path()
            with open(marker, "w") as f:
                f.write(exe)
            _hide_file(marker)
        except Exception:
            pass
        self.destroy()

    def _on_install(self):
        if self._installing:
            return
        if (not self.var_assoc.get() and not self.var_thumbs.get()
                and not self.var_shortcut.get()):
            self._on_skip()
            return

        self._installing = True
        self._btn_go.config(state="disabled", text="Installing\u2026")
        self._btn_skip.config(state="disabled")
        if not self._pbar_shown:
            self._pbar.pack(fill="x", pady=(4, 0))
            self._pbar_shown = True
        self._pbar["value"] = 0
        self.after(50, self._step_extract)

    def _step_extract(self):
        self._plbl.config(text="Extracting components\u2026", fg=COLORS["text"])
        self._pbar["value"] = 10
        self.update_idletasks()
        _extract_dll()
        self.after(80, self._step_prepare)

    def _step_prepare(self):
        self._plbl.config(text="Preparing registration\u2026")
        self._pbar["value"] = 25
        self.update_idletasks()

        viewer_exe, icon_path, dll_path = _get_setup_paths()
        self._viewer_exe = viewer_exe

        ps1 = _build_setup_ps1(viewer_exe, icon_path, dll_path)
        self._tmp = os.path.join(
            tempfile.gettempdir(), "procreate_auto_setup.ps1"
        )
        with open(self._tmp, "w", encoding="utf-8-sig") as f:
            f.write(ps1)
        self.after(80, self._step_register)

    def _step_register(self):
        self._plbl.config(text="Registering with Windows\u2026")
        self._pbar["value"] = 40
        self.update_idletasks()

        t = threading.Thread(target=self._do_register, daemon=True)
        t.start()
        self._poll(t)

    def _poll(self, t):
        if t.is_alive():
            v = self._pbar["value"]
            if v < 88:
                self._pbar["value"] = v + 1
            self.after(250, lambda: self._poll(t))
        else:
            self._step_finish()

    def _do_register(self):
        self._reg_ok = _run_ps1_elevated(self._tmp)
        try:
            os.remove(self._tmp)
        except Exception:
            pass

    def _step_finish(self):
        self._pbar["value"] = 100
        if self._reg_ok:
            # Create desktop shortcut if requested
            if self.var_shortcut.get():
                try:
                    _create_desktop_shortcut()
                except Exception:
                    pass

            self._plbl.config(
                text="Setup complete!  Restart Explorer for thumbnails.",
                fg=COLORS["success"],
            )
            marker = _get_marker_path()
            try:
                with open(marker, "w") as f:
                    f.write(self._viewer_exe)
                _hide_file(marker)
            except Exception:
                pass
            # Hide the setup log
            _hide_file(os.path.join(_BASE_DIR, ".setup_log.txt"))
            self.result = True
        else:
            self._plbl.config(
                text="Setup was cancelled or failed.  "
                     "Use Settings to retry.",
                fg=COLORS["warning"],
            )
            self.result = False

        self._btn_go.config(
            state="normal", text="   Done   ", command=self.destroy
        )
        self._btn_skip.pack_forget()


# ═══════════════════════════════════════════════════════════════════════
# Uninstall Dialog (beautiful UI with option cards + progress bar)
# ═══════════════════════════════════════════════════════════════════════
class UninstallDialog(tk.Toplevel):
    """Themed uninstall dialog with selectable options and progress."""

    def __init__(self, parent, full=False):
        super().__init__(parent)
        self._parent = parent
        self._full = full
        self._working = False
        self.result = False

        mode = "Full Uninstall" if full else "Uninstall"
        self.title(f"Procreate Viewer \u2014 {mode}")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        _h = 600 if full else 520
        self.geometry(f"500x{_h}")
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        icon_path = os.path.join(_RES_DIR, "resources", "icon.ico")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(_BASE_DIR, "resources", "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.update_idletasks()
        if parent and parent.winfo_exists():
            px = parent.winfo_rootx() + (parent.winfo_width() - 500) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - _h) // 2
        else:
            px = (self.winfo_screenwidth() - 500) // 2
            py = (self.winfo_screenheight() - _h) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

        if parent and parent.winfo_exists():
            self.transient(parent)
        self.grab_set()
        self.focus_force()
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Warning header
        hdr_color = "#8B0000" if self._full else COLORS["warning"]
        header = tk.Frame(self, bg=hdr_color, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        hdr_inner = tk.Frame(header, bg=hdr_color)
        hdr_inner.pack(side="left", fill="both", expand=True, padx=24, pady=12)
        tk.Label(
            hdr_inner,
            text="\u26A0  Full Uninstall" if self._full else "\u26A0  Uninstall",
            font=("Segoe UI Semibold", 18),
            bg=hdr_color, fg="white", anchor="w",
        ).pack(fill="x")
        tk.Label(
            hdr_inner,
            text="Remove all components from this PC"
            if self._full else "Remove selected registrations",
            font=("Segoe UI", 11),
            bg=hdr_color, fg="#FFD0B0", anchor="w",
        ).pack(fill="x")

        # Body
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=20)

        tk.Label(
            body,
            text="Deselect any items you want to keep." if not self._full
            else "All items will be removed.\n"
                 "The application will close after uninstall.",
            font=("Segoe UI", 10), bg=COLORS["bg"], fg=COLORS["text"],
            anchor="w", justify="left",
        ).pack(fill="x", pady=(0, 14))

        # Option cards
        self.var_assoc = tk.BooleanVar(value=True)
        self.var_thumbs = tk.BooleanVar(value=True)
        self.var_shortcut = tk.BooleanVar(value=True)
        self.var_files = tk.BooleanVar(value=self._full)

        self._option_card(
            body, self.var_assoc,
            "File Associations",
            "Remove .procreate file type registration",
        )
        self._option_card(
            body, self.var_thumbs,
            "Thumbnail Handler",
            "Unregister DLL and clear Explorer thumbnail cache",
        )
        # Check if shortcut exists
        _desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        _has_lnk = os.path.isfile(
            os.path.join(_desktop, "Procreate Viewer.lnk")
        )
        if _has_lnk:
            self._option_card(
                body, self.var_shortcut,
                "Desktop Shortcut",
                "Delete the Procreate Viewer shortcut from Desktop",
            )
        else:
            self.var_shortcut.set(False)

        if self._full:
            self._option_card(
                body, self.var_files,
                "Settings & Data Files",
                "Delete DLL, marker file, and log files next to the exe",
            )

        # Admin notice
        tk.Label(
            body,
            text="Windows will ask for administrator permission.",
            font=("Segoe UI", 9), bg=COLORS["bg"],
            fg=COLORS["text_dim"], anchor="w",
        ).pack(fill="x", pady=(10, 0))

        # Progress area
        self._pf = tk.Frame(body, bg=COLORS["bg"])
        self._pf.pack(fill="x", pady=(12, 0))

        self._plbl = tk.Label(
            self._pf, text="", font=("Segoe UI", 9),
            bg=COLORS["bg"], fg=COLORS["success"], anchor="w",
        )
        self._plbl.pack(fill="x")

        style = ttk.Style()
        style.configure(
            "Uninstall.Horizontal.TProgressbar",
            background=COLORS["warning"], troughcolor=COLORS["bg2"],
        )
        self._pbar = ttk.Progressbar(
            self._pf, style="Uninstall.Horizontal.TProgressbar",
            mode="determinate", maximum=100,
        )
        self._pbar_shown = False

        # Buttons
        bf = tk.Frame(self, bg=COLORS["bg"])
        bf.pack(fill="x", padx=28, pady=(0, 22))

        self._btn_cancel = tk.Button(
            bf, text="Cancel",
            font=("Segoe UI", 10), bg=COLORS["bg2"],
            fg=COLORS["text_dim"],
            activebackground=COLORS["bg2"],
            activeforeground=COLORS["text"],
            relief="flat", bd=0, padx=20, pady=8,
            cursor="hand2", command=self._on_cancel,
        )
        self._btn_cancel.pack(side="left")

        btn_color = "#8B0000" if self._full else COLORS["warning"]
        self._btn_go = tk.Button(
            bf,
            text="   Uninstall All   " if self._full else "   Uninstall   ",
            font=("Segoe UI Semibold", 11),
            bg=btn_color, fg="white",
            activebackground="#601010" if self._full else "#CC8800",
            activeforeground="white",
            relief="flat", bd=0, padx=28, pady=9,
            cursor="hand2", command=self._on_uninstall,
        )
        self._btn_go.pack(side="right")

    def _option_card(self, parent, var, title, desc):
        card = tk.Frame(parent, bg=COLORS["bg2"])
        card.pack(fill="x", pady=4, ipady=8)

        tk.Checkbutton(
            card, variable=var,
            bg=COLORS["bg2"], fg=COLORS["text"],
            selectcolor=COLORS["bg"],
            activebackground=COLORS["bg2"],
            activeforeground=COLORS["text"],
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(10, 4))

        tf = tk.Frame(card, bg=COLORS["bg2"])
        tf.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(
            tf, text=title, font=("Segoe UI Semibold", 10),
            bg=COLORS["bg2"], fg=COLORS["text"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            tf, text=desc, font=("Segoe UI", 9),
            bg=COLORS["bg2"], fg=COLORS["text_dim"], anchor="w",
        ).pack(fill="x")

    # ── Actions ────────────────────────────────────────────────────────

    def _on_cancel(self):
        if self._working:
            return
        self.result = False
        self.destroy()

    def _run_inno_uninstall(self, uninstaller_path: str):
        """Launch the Inno Setup uninstaller and close the app."""
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", uninstaller_path, "/SILENT", None, 1,
            )
            self._uninstall_ok = True
        except Exception:
            self._uninstall_ok = False

    def _on_uninstall(self):
        if self._working:
            return
        # Check if anything is selected
        if (not self.var_assoc.get() and not self.var_thumbs.get()
                and not self.var_shortcut.get() and not self.var_files.get()):
            self._on_cancel()
            return

        self._working = True
        self._btn_go.config(state="disabled", text="Uninstalling\u2026")
        self._btn_cancel.config(state="disabled")
        if not self._pbar_shown:
            self._pbar.pack(fill="x", pady=(4, 0))
            self._pbar_shown = True
        self._pbar["value"] = 0
        self.after(50, self._step_start)

    def _step_start(self):
        self._plbl.config(text="Preparing\u2026", fg=COLORS["text"])
        self._pbar["value"] = 5
        self.update_idletasks()

        t = threading.Thread(target=self._do_uninstall, daemon=True)
        t.start()
        self._poll(t)

    def _do_uninstall(self):
        """Background thread: run uninstall steps."""
        self._uninstall_ok = True
        try:
            # If installed via Inno Setup, use its uninstaller
            inno_uninstall = _find_inno_uninstaller()
            if inno_uninstall and self._full:
                self._run_inno_uninstall(inno_uninstall)
                return

            # 1. Build PS1 for registry removal
            need_ps1 = self.var_assoc.get() or self.var_thumbs.get()
            if need_ps1:
                _log_path = os.path.join(_BASE_DIR, ".setup_log.txt")
                _log_esc = _log_path.replace("'", "''")
                ps1_parts = []
                ps1_parts.append("$ErrorActionPreference = 'Continue'")
                ps1_parts.append(f"$logFile = '{_log_esc}'")
                ps1_parts.append(
                    "function Log($msg) { Add-Content -Path $logFile "
                    "-Value \"$(Get-Date -F 'HH:mm:ss') $msg\" "
                    "-Encoding UTF8 -EA SilentlyContinue }"
                )
                ps1_parts.append("Log 'Uninstall PS1 started'")
                ps1_parts.append(
                    "New-PSDrive -PSProvider Registry -Root "
                    "HKEY_CLASSES_ROOT -Name HKCR "
                    "-EA SilentlyContinue | Out-Null"
                )

                if self.var_assoc.get():
                    clsid = "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"
                    ps1_parts += [
                        "",
                        "# Remove file associations",
                        "Remove-Item 'HKCR:\\.procreate' -Recurse -Force "
                        "-EA SilentlyContinue",
                        "Remove-Item 'HKCR:\\ProcreateViewer.procreate' "
                        "-Recurse -Force -EA SilentlyContinue",
                        "Remove-Item 'HKCU:\\Software\\Classes\\.procreate' "
                        "-Recurse -Force -EA SilentlyContinue",
                        "Remove-Item "
                        "'HKCU:\\Software\\Classes\\ProcreateViewer.procreate' "
                        "-Recurse -Force -EA SilentlyContinue",
                    ]

                if self.var_thumbs.get():
                    clsid = "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"
                    dll_path = os.path.join(
                        _BASE_DIR, "ProcreateThumbHandler.dll"
                    )
                    ps1_parts += [
                        "",
                        "# Remove thumbnail handler",
                        f"Remove-Item 'HKCR:\\CLSID\\{clsid}' -Recurse "
                        f"-Force -EA SilentlyContinue",
                        f"Remove-Item "
                        f"'HKLM:\\Software\\Classes\\CLSID\\{clsid}' "
                        f"-Recurse -Force -EA SilentlyContinue",
                        "Remove-Item "
                        "'HKLM:\\Software\\Classes\\.procreate' -Recurse "
                        "-Force -EA SilentlyContinue",
                        "$ap = 'HKLM:\\Software\\Microsoft\\Windows"
                        "\\CurrentVersion\\Shell Extensions\\Approved'",
                        f"if (Test-Path $ap) {{ Remove-ItemProperty "
                        f"-Path $ap -Name '{clsid}' "
                        f"-EA SilentlyContinue }}",
                        "",
                        "# Unregister DLL",
                        "Stop-Process -Name 'dllhost' -Force "
                        "-EA SilentlyContinue",
                    ]
                    if os.path.isfile(dll_path):
                        regasm = ("C:\\Windows\\Microsoft.NET"
                                  "\\Framework64\\v4.0.30319\\RegAsm.exe")
                        ps1_parts.append(
                            f"try {{ if (Test-Path '{regasm}') "
                            f"{{ & '{regasm}' /unregister '{dll_path}' "
                            f"2>&1 | Out-Null }} }} catch {{}}"
                        )
                    ps1_parts += [
                        "",
                        "# Clear thumbnail cache",
                        "$cache = "
                        "\"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\"",
                        "Get-ChildItem \"$cache\\thumbcache_*.db\" "
                        "-EA SilentlyContinue | ForEach-Object "
                        "{ try { Remove-Item $_.FullName -Force } catch {} }",
                    ]

                # SHChangeNotify
                ps1_parts += [
                    "",
                    "Add-Type -TypeDefinition @\"",
                    "using System;",
                    "using System.Runtime.InteropServices;",
                    "public class ShellNotify3 {",
                    "    [DllImport(\"shell32.dll\")]",
                    "    public static extern void SHChangeNotify("
                    "uint wEventId, uint uFlags, "
                    "IntPtr dwItem1, IntPtr dwItem2);",
                    "}",
                    "\"@ -EA SilentlyContinue",
                    "[ShellNotify3]::SHChangeNotify(0x08000000, 0, "
                    "[IntPtr]::Zero, [IntPtr]::Zero)",
                    "",
                    "Log 'Uninstall PS1 completed successfully'",
                ]

                tmp = os.path.join(
                    tempfile.gettempdir(), "procreate_uninstall.ps1"
                )
                with open(tmp, "w", encoding="utf-8-sig") as f:
                    f.write("\n".join(ps1_parts))
                _run_ps1_elevated(tmp)
                try:
                    os.remove(tmp)
                except Exception:
                    pass

            # 2. Desktop shortcut
            if self.var_shortcut.get():
                _remove_desktop_shortcut()

            # 3. Local files
            if self.var_files.get():
                if self._full:
                    # Full uninstall: schedule deletion of the entire
                    # application folder after the exe exits.
                    self._schedule_folder_delete()
                else:
                    for fn in [
                        ".procreate_installed", ".setup_log.txt",
                        "ProcreateThumbHandler.dll", "icon.ico",
                    ]:
                        fp = os.path.join(_BASE_DIR, fn)
                        try:
                            if os.path.isfile(fp):
                                os.remove(fp)
                        except Exception:
                            pass
            else:
                # Even without full, remove the marker so setup can re-run
                if self.var_assoc.get() or self.var_thumbs.get():
                    try:
                        os.remove(_get_marker_path())
                    except Exception:
                        pass

        except Exception:
            self._uninstall_ok = False

    def _poll(self, t):
        if t.is_alive():
            v = self._pbar["value"]
            if v < 90:
                self._pbar["value"] = v + 2
            self.after(200, lambda: self._poll(t))
            return

        self._pbar["value"] = 100
        self._working = False

        if self._uninstall_ok:
            self._plbl.config(
                text="\u2714  Uninstall complete!",
                fg=COLORS["success"],
            )
            self.result = True

            if self._full:
                self._btn_go.config(
                    state="normal", text="   Close App   ",
                    command=self._close_app,
                )
            else:
                self._btn_go.config(
                    state="normal", text="   Done   ",
                    command=self.destroy,
                )
        else:
            self._plbl.config(
                text="Uninstall failed or was cancelled.",
                fg=COLORS["warning"],
            )
            self._btn_go.config(
                state="normal", text="   Close   ",
                command=self.destroy,
            )
        self._btn_cancel.pack_forget()

    def _close_app(self):
        """Close the dialog and the main application."""
        self.destroy()
        if self._parent and self._parent.winfo_exists():
            # If parent is SettingsDialog, close both it and the main app
            try:
                main_app = self._parent._parent
                self._parent.destroy()
                if main_app and main_app.winfo_exists():
                    main_app.destroy()
            except Exception:
                self._parent.destroy()

    # ── Self-delete helper ─────────────────────────────────────────────

    def _schedule_folder_delete(self):
        """Create a self-deleting batch script that removes the entire
        application folder after the .exe process exits.

        The batch waits in a loop until the exe is no longer running,
        then deletes the folder and itself.
        """
        folder = os.path.normpath(_BASE_DIR)
        # Determine the exe path so the bat can wait for it to exit
        if getattr(sys, "frozen", False):
            exe_path = os.path.normpath(os.path.abspath(sys.executable))
            exe_name = os.path.basename(exe_path)
        else:
            # Running from Python — just delete data files, not the source
            for fn in os.listdir(folder):
                fp = os.path.join(folder, fn)
                if fn.lower().endswith((".py", ".pyw")):
                    continue
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                except Exception:
                    pass
            return

        pid = os.getpid()
        bat_path = os.path.join(
            tempfile.gettempdir(), "_procreate_cleanup.bat"
        )
        # The batch script:
        # 1) Waits until the exe process (by PID) is gone
        # 2) Deletes the entire application folder
        # 3) Deletes itself
        bat_content = (
            "@echo off\r\n"
            "chcp 65001 >nul 2>&1\r\n"
            f"set \"TARGET={folder}\"\r\n"
            f"set \"PID={pid}\"\r\n"
            ":WAIT\r\n"
            "timeout /t 1 /nobreak >nul\r\n"
            "tasklist /FI \"PID eq %PID%\" 2>nul | find /i \"%PID%\" >nul\r\n"
            "if not errorlevel 1 goto WAIT\r\n"
            "timeout /t 1 /nobreak >nul\r\n"
            "rd /s /q \"%TARGET%\" >nul 2>&1\r\n"
            "del /f /q \"%~f0\" >nul 2>&1\r\n"
        )
        try:
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
            # Launch the cleanup bat hidden (CREATE_NO_WINDOW)
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=0x08000000,
                close_fds=True,
            )
        except Exception:
            # Fallback: at least delete individual files we can
            for fn in os.listdir(folder):
                fp = os.path.join(folder, fn)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                    elif os.path.isdir(fp):
                        import shutil
                        shutil.rmtree(fp, ignore_errors=True)
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════════════
# Settings Dialog (status, install/repair, uninstall, restart Explorer)
# ═══════════════════════════════════════════════════════════════════════
class SettingsDialog(tk.Toplevel):
    """Settings panel showing registration status with actions."""

    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self._status_labels: dict = {}

        self.title("Settings \u2014 Procreate Viewer")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.geometry("460x420")

        icon_path = os.path.join(_RES_DIR, "resources", "icon.ico")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(_BASE_DIR, "resources", "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 460) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 420) // 2
        self.geometry(f"+{px}+{py}")

        self.transient(parent)
        self.grab_set()
        self.focus_force()
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        header = tk.Frame(self, bg=COLORS["panel"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Settings",
            font=("Segoe UI Semibold", 14),
            bg=COLORS["panel"], fg=COLORS["text"],
        ).pack(side="left", padx=20, pady=8)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=22, pady=16)

        # Status section
        self._section(body, "SYSTEM INTEGRATION")
        assoc = _check_file_association()
        thumb = _check_thumbnail_handler()
        dll = os.path.isfile(
            os.path.join(_BASE_DIR, "ProcreateThumbHandler.dll")
        )

        self._status_row(
            body, "File Association",
            "Installed" if assoc else "Not installed",
            COLORS["success"] if assoc else COLORS["text_dim"],
        )
        self._status_row(
            body, "Explorer Thumbnails",
            "Installed" if thumb else "Not installed",
            COLORS["success"] if thumb else COLORS["text_dim"],
        )
        self._status_row(
            body, "Thumbnail DLL",
            "Present" if dll else "Missing",
            COLORS["success"] if dll else COLORS["warning"],
        )

        tk.Frame(body, height=16, bg=COLORS["bg"]).pack()

        # Actions section
        self._section(body, "ACTIONS")
        bk = dict(
            font=("Segoe UI", 10), relief="flat", bd=0,
            padx=16, pady=8, cursor="hand2",
        )
        self._btn_inst = tk.Button(
            body, text="Install / Repair Everything",
            bg=COLORS["accent"], fg="white",
            activebackground="#C03050", activeforeground="white",
            command=self._install_all, **bk,
        )
        self._btn_inst.pack(fill="x", pady=3)

        tk.Button(
            body, text="Restart Explorer  (apply thumbnails now)",
            bg=COLORS["panel"], fg=COLORS["text"],
            activebackground=COLORS["btn_hover"],
            activeforeground="white",
            command=self._restart_explorer, **bk,
        ).pack(fill="x", pady=3)

        tk.Button(
            body, text="Uninstall All Registrations",
            bg=COLORS["bg2"], fg=COLORS["text_dim"],
            activebackground="#402020", activeforeground="#FF8888",
            command=self._uninstall_all, **bk,
        ).pack(fill="x", pady=3)

        tk.Button(
            body, text="\u26a0  Full Uninstall (Delete App + Settings)",
            bg="#3A1010", fg="#FF6666",
            activebackground="#601010", activeforeground="#FF4444",
            command=self._full_uninstall, **bk,
        ).pack(fill="x", pady=3)

        # Progress label
        self._plbl = tk.Label(
            body, text="", font=("Segoe UI", 9),
            bg=COLORS["bg"], fg=COLORS["success"], anchor="w",
        )
        self._plbl.pack(fill="x", pady=(10, 0))

        # Close button
        bottom = tk.Frame(self, bg=COLORS["bg"])
        bottom.pack(fill="x", padx=22, pady=(0, 14))
        tk.Button(
            bottom, text="Close",
            font=("Segoe UI", 10), bg=COLORS["bg2"],
            fg=COLORS["text"],
            activebackground=COLORS["btn_hover"],
            activeforeground="white",
            relief="flat", bd=0, padx=20, pady=6,
            cursor="hand2", command=self.destroy,
        ).pack(side="right")

    def _section(self, parent, text):
        tk.Label(
            parent, text=text, font=("Segoe UI Semibold", 10),
            bg=COLORS["bg"], fg=COLORS["accent"], anchor="w",
        ).pack(fill="x", pady=(4, 2))
        tk.Frame(
            parent, bg=COLORS["accent"], height=1,
        ).pack(fill="x", pady=(0, 6))

    def _status_row(self, parent, label_text, status_text, color):
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill="x", pady=2)
        tk.Label(
            row, text=label_text, font=("Segoe UI", 10),
            bg=COLORS["bg"], fg=COLORS["text"], anchor="w",
        ).pack(side="left")
        lbl = tk.Label(
            row, text=status_text, font=("Segoe UI Semibold", 10),
            bg=COLORS["bg"], fg=color, anchor="e",
        )
        lbl.pack(side="right")
        self._status_labels[label_text] = lbl

    # ── Actions ────────────────────────────────────────────────────────

    def _install_all(self):
        self._btn_inst.config(state="disabled", text="Installing\u2026")
        self._plbl.config(text="Registering with Windows\u2026", fg=COLORS["text"])
        self.update_idletasks()

        def _work():
            try:
                os.remove(_get_marker_path())
            except Exception:
                pass
            self._ok = run_auto_setup()

        t = threading.Thread(target=_work, daemon=True)
        t.start()
        self._poll(t, "install")

    def _poll(self, t, action):
        if t.is_alive():
            self.after(200, lambda: self._poll(t, action))
            return

        self._btn_inst.config(
            state="normal", text="Install / Repair Everything"
        )
        if getattr(self, "_ok", False):
            self._plbl.config(
                text="Installed!  Restart Explorer for thumbnails.",
                fg=COLORS["success"],
            )
        else:
            self._plbl.config(
                text="Installation cancelled or failed.",
                fg=COLORS["warning"],
            )
        self._refresh_status()

    def _refresh_status(self):
        assoc = _check_file_association()
        thumb = _check_thumbnail_handler()
        dll = os.path.isfile(
            os.path.join(_BASE_DIR, "ProcreateThumbHandler.dll")
        )
        sl = self._status_labels
        if "File Association" in sl:
            sl["File Association"].config(
                text="Installed" if assoc else "Not installed",
                fg=COLORS["success"] if assoc else COLORS["text_dim"],
            )
        if "Explorer Thumbnails" in sl:
            sl["Explorer Thumbnails"].config(
                text="Installed" if thumb else "Not installed",
                fg=COLORS["success"] if thumb else COLORS["text_dim"],
            )
        if "Thumbnail DLL" in sl:
            sl["Thumbnail DLL"].config(
                text="Present" if dll else "Missing",
                fg=COLORS["success"] if dll else COLORS["warning"],
            )

    def _restart_explorer(self):
        if not themed_askyesno(
            "Restart Explorer",
            "This will briefly close and reopen File Explorer\n"
            "so thumbnail changes take effect.\n\nContinue?",
            parent=self,
        ):
            return
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", "explorer.exe"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.after(1500, lambda: subprocess.Popen(["explorer.exe"]))
            self._plbl.config(
                text="Explorer restarting\u2026", fg=COLORS["success"],
            )
        except Exception as e:
            self._plbl.config(
                text=f"Could not restart: {e}", fg=COLORS["warning"],
            )

    def _uninstall_all(self):
        """Open the themed uninstall dialog (partial)."""
        dlg = UninstallDialog(self, full=False)
        self.wait_window(dlg)
        if dlg.result:
            self._refresh_status()
            self._plbl.config(
                text="Uninstalled.  Restart Explorer to clear cache.",
                fg=COLORS["text"],
            )

    def _full_uninstall(self):
        """Open the themed uninstall dialog (full)."""
        UninstallDialog(self, full=True)


# ═══════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════
class ProcreateViewer(tk.Tk):
    """Main application window."""

    def __init__(self, filepath: Optional[str] = None):
        super().__init__()

        self.procreate: Optional[ProcreateFile] = None
        self._photo_image: Optional[ImageTk.PhotoImage] = None
        self._display_image: Optional[Image.Image] = None
        self._original_image: Optional[Image.Image] = None
        self._zoom_level: float = 1.0
        self._pan_x: int = 0
        self._pan_y: int = 0
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._layer_overrides: dict = {}     # {layer_index: visible_bool}
        self._can_composite: bool = False
        self._layer_cache: dict = {}         # {layer_index: Image}

        self._configure_window()
        self._build_menu()
        self._build_toolbar()
        self._build_main_area()
        self._build_statusbar()
        self._apply_theme()

        # Open file if provided via CLI
        if filepath and os.path.isfile(filepath):
            self.after(100, lambda: self._open_file(filepath))

        # Accept dropped files (via command line)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Window Setup ───────────────────────────────────────────────────

    def _configure_window(self):
        self.title(APP_TITLE)
        self.minsize(WINDOW_MIN_W, WINDOW_MIN_H)
        self.geometry("1100x750")
        self.configure(bg=COLORS["bg"])

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 1100) // 2
        y = (sh - 750) // 2
        self.geometry(f"+{x}+{y}")

        # Try to set icon
        icon_path = os.path.join(_RES_DIR, "resources", "icon.ico")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(_BASE_DIR, "resources", "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

    # ── Menu Bar ───────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self, bg=COLORS["bg2"], fg=COLORS["text"],
                          activebackground=COLORS["accent"],
                          activeforeground="white", relief="flat")

        # File
        file_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["bg2"],
                            fg=COLORS["text"],
                            activebackground=COLORS["accent"])
        file_menu.add_command(label="Open…", accelerator="Ctrl+O",
                              command=self._on_open)
        file_menu.add_separator()
        file_menu.add_command(label="Export as PNG…", command=lambda: self._on_export("PNG"))
        file_menu.add_command(label="Export as JPEG…", command=lambda: self._on_export("JPEG"))
        file_menu.add_command(label="Export as BMP…", command=lambda: self._on_export("BMP"))
        file_menu.add_command(label="Export as TIFF…", command=lambda: self._on_export("TIFF"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["bg2"],
                            fg=COLORS["text"],
                            activebackground=COLORS["accent"])
        view_menu.add_command(label="Zoom In", accelerator="Ctrl++",
                              command=self._zoom_in)
        view_menu.add_command(label="Zoom Out", accelerator="Ctrl+-",
                              command=self._zoom_out)
        view_menu.add_command(label="Fit to Window", accelerator="Ctrl+0",
                              command=self._zoom_fit)
        view_menu.add_command(label="Actual Size", accelerator="Ctrl+1",
                              command=self._zoom_actual)
        menubar.add_cascade(label="View", menu=view_menu)

        # Tools
        tools_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["bg2"],
                             fg=COLORS["text"],
                             activebackground=COLORS["accent"])
        tools_menu.add_command(
            label="Settings\u2026",
            command=self._on_settings,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Batch Convert Folder…",
            command=self._on_batch_convert,
        )
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["bg2"],
                            fg=COLORS["text"],
                            activebackground=COLORS["accent"])
        help_menu.add_command(label="About", command=self._on_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

        # Keyboard shortcuts
        self.bind_all("<Control-o>", lambda e: self._on_open())
        self.bind_all("<Control-plus>", lambda e: self._zoom_in())
        self.bind_all("<Control-equal>", lambda e: self._zoom_in())
        self.bind_all("<Control-minus>", lambda e: self._zoom_out())
        self.bind_all("<Control-0>", lambda e: self._zoom_fit())
        self.bind_all("<Control-1>", lambda e: self._zoom_actual())

    # ── Toolbar ────────────────────────────────────────────────────────

    def _build_toolbar(self):
        self.toolbar = tk.Frame(self, bg=COLORS["bg2"], height=44)
        self.toolbar.pack(fill="x", side="top")
        self.toolbar.pack_propagate(False)

        btn_style = dict(
            bg=COLORS["btn"], fg=COLORS["text"],
            activebackground=COLORS["btn_hover"],
            activeforeground="white",
            relief="flat", bd=0, padx=14, pady=6,
            font=("Segoe UI", 10),
            cursor="hand2",
        )

        self.btn_open = tk.Button(self.toolbar, text="📂 Open", command=self._on_open, **btn_style)
        self.btn_open.pack(side="left", padx=(8, 2), pady=6)
        ToolTip(self.btn_open, "Open .procreate file (Ctrl+O)")

        self.btn_export = tk.Button(self.toolbar, text="💾 Export", command=lambda: self._on_export("PNG"), **btn_style)
        self.btn_export.pack(side="left", padx=2, pady=6)
        ToolTip(self.btn_export, "Export preview as PNG")

        sep = tk.Frame(self.toolbar, width=2, bg=COLORS["border"])
        sep.pack(side="left", fill="y", padx=8, pady=8)

        self.btn_zin = tk.Button(self.toolbar, text="🔍+", command=self._zoom_in, **btn_style)
        self.btn_zin.pack(side="left", padx=2, pady=6)
        ToolTip(self.btn_zin, "Zoom In (Ctrl++)")

        self.btn_zout = tk.Button(self.toolbar, text="🔍−", command=self._zoom_out, **btn_style)
        self.btn_zout.pack(side="left", padx=2, pady=6)
        ToolTip(self.btn_zout, "Zoom Out (Ctrl+-)")

        self.btn_zfit = tk.Button(self.toolbar, text="⊞ Fit", command=self._zoom_fit, **btn_style)
        self.btn_zfit.pack(side="left", padx=2, pady=6)
        ToolTip(self.btn_zfit, "Fit to Window (Ctrl+0)")

        sep2 = tk.Frame(self.toolbar, width=2, bg=COLORS["border"])
        sep2.pack(side="left", fill="y", padx=8, pady=8)

        self.btn_settings = tk.Button(
            self.toolbar, text="\u2699 Settings",
            command=self._on_settings, **btn_style,
        )
        self.btn_settings.pack(side="left", padx=2, pady=6)
        ToolTip(self.btn_settings, "Settings \u2014 file associations & thumbnails")

        # Zoom label on right
        self.zoom_label = tk.Label(
            self.toolbar, text="100%",
            bg=COLORS["bg2"], fg=COLORS["text_dim"],
            font=("Segoe UI", 10),
        )
        self.zoom_label.pack(side="right", padx=12)

    # ── Main Area ──────────────────────────────────────────────────────

    def _build_main_area(self):
        self.main_pane = tk.PanedWindow(
            self, orient="horizontal",
            bg=COLORS["border"], sashwidth=4,
            sashrelief="flat",
        )
        self.main_pane.pack(fill="both", expand=True)

        # ── Canvas Area (left) ──
        self.canvas_frame = tk.Frame(self.main_pane, bg=COLORS["canvas_bg"])
        self.main_pane.add(self.canvas_frame, stretch="always", minsize=400)

        self.canvas = tk.Canvas(
            self.canvas_frame,
            bg=COLORS["canvas_bg"],
            highlightthickness=0,
            cursor="fleur",
        )
        self.canvas.pack(fill="both", expand=True)

        # Welcome text
        self.canvas.create_text(
            0, 0, text="Drag & drop or press Ctrl+O\nto open a .procreate file",
            fill=COLORS["text_dim"], font=("Segoe UI", 16),
            tags="welcome", anchor="center",
        )
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Pan bindings
        self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<B1-Motion>", self._on_pan_move)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)

        # ── Info Panel (right) ──
        self.info_frame = tk.Frame(self.main_pane, bg=COLORS["bg"], width=280)
        self.main_pane.add(self.info_frame, stretch="never", minsize=240)

        self._build_info_panel()

    def _build_info_panel(self):
        """Build the right-side information panel."""
        container = tk.Frame(self.info_frame, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # ── File Info Section ──
        self._section_label(container, "FILE INFO")
        self.info_text = tk.Text(
            container, bg=COLORS["bg2"], fg=COLORS["text"],
            font=("Consolas", 10), relief="flat", height=9,
            wrap="word", state="disabled", bd=0,
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            padx=8, pady=6,
        )
        self.info_text.pack(fill="x", pady=(0, 10))

        # ── Layers Section ──
        self._section_label(container, "LAYERS")
        layers_frame = tk.Frame(container, bg=COLORS["bg"])
        layers_frame.pack(fill="both", expand=True)

        self.layers_tree = ttk.Treeview(
            layers_frame, columns=("opacity", "blend"),
            show="tree headings", height=12,
            selectmode="browse",
        )
        self.layers_tree.heading("#0", text="Layer", anchor="w")
        self.layers_tree.heading("opacity", text="Opacity", anchor="center")
        self.layers_tree.heading("blend", text="Blend", anchor="w")
        self.layers_tree.column("#0", width=130, minwidth=80)
        self.layers_tree.column("opacity", width=60, minwidth=50, anchor="center")
        self.layers_tree.column("blend", width=80, minwidth=60)

        scrollbar = ttk.Scrollbar(layers_frame, orient="vertical",
                                  command=self.layers_tree.yview)
        self.layers_tree.configure(yscrollcommand=scrollbar.set)

        self.layers_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Layer toggle hint
        self._layers_hint = tk.Label(
            container,
            text="Double-click a layer to toggle visibility",
            font=("Segoe UI", 8), bg=COLORS["bg"],
            fg=COLORS["text_dim"], anchor="w",
        )
        self._layers_hint.pack(fill="x", pady=(2, 6))

        # Bind double-click & right-click on layers
        self.layers_tree.bind("<Double-1>", self._on_layer_toggle)
        self.layers_tree.bind("<Button-3>", self._on_layer_context_menu)

        # ── Archive Contents Section ──
        self._section_label(container, "ARCHIVE CONTENTS")
        self.archive_text = tk.Text(
            container, bg=COLORS["bg2"], fg=COLORS["text_dim"],
            font=("Consolas", 9), relief="flat", height=6,
            wrap="word", state="disabled", bd=0,
            padx=8, pady=6,
        )
        self.archive_text.pack(fill="x", pady=(0, 4))

    def _section_label(self, parent, text):
        tk.Label(
            parent, text=text,
            bg=COLORS["bg"], fg=COLORS["accent"],
            font=("Segoe UI Semibold", 10),
            anchor="w",
        ).pack(fill="x", pady=(8, 4))
        tk.Frame(parent, bg=COLORS["accent"], height=1).pack(fill="x", pady=(0, 4))

    # ── Status Bar ─────────────────────────────────────────────────────

    def _build_statusbar(self):
        self.statusbar = tk.Frame(self, bg=COLORS["bg2"], height=28)
        self.statusbar.pack(fill="x", side="bottom")
        self.statusbar.pack_propagate(False)

        self.status_label = tk.Label(
            self.statusbar, text="Ready",
            bg=COLORS["bg2"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9), anchor="w", padx=10,
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.status_right = tk.Label(
            self.statusbar, text=f"v{APP_VERSION}",
            bg=COLORS["bg2"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9), anchor="e", padx=10,
        )
        self.status_right.pack(side="right")

    # ── Theme ──────────────────────────────────────────────────────────

    def _apply_theme(self):
        """Apply dark theme to ttk widgets."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                         background=COLORS["bg2"],
                         foreground=COLORS["text"],
                         fieldbackground=COLORS["bg2"],
                         borderwidth=0,
                         font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                         background=COLORS["panel"],
                         foreground=COLORS["text"],
                         font=("Segoe UI Semibold", 9))
        style.map("Treeview",
                   background=[("selected", COLORS["accent2"])],
                   foreground=[("selected", "white")])
        style.configure("Vertical.TScrollbar",
                         background=COLORS["bg2"],
                         troughcolor=COLORS["bg"],
                         borderwidth=0,
                         arrowsize=12)

    # ═══════════════════════════════════════════════════════════════════
    # Event Handlers
    # ═══════════════════════════════════════════════════════════════════

    def _on_canvas_resize(self, event):
        # Keep welcome text centered
        self.canvas.coords("welcome", event.width // 2, event.height // 2)
        if self._display_image:
            self._render_image()

    def _on_open(self):
        filepath = filedialog.askopenfilename(
            title="Open Procreate File",
            filetypes=[
                ("Procreate Files", "*.procreate"),
                ("All Files", "*.*"),
            ],
        )
        if filepath:
            self._open_file(filepath)

    def _open_file(self, filepath: str):
        """Load and display a .procreate file."""
        self._set_status(f"Opening {os.path.basename(filepath)}…")
        self.update_idletasks()

        try:
            if self.procreate:
                self.procreate.close()

            self.procreate = ProcreateFile(filepath)
            self._display_image = self.procreate.get_best_image()
            self._original_image = self._display_image
            self._layer_overrides = {}
            self._layer_cache = {}
            self._can_composite = False

            # Check if layer compositing is possible
            self._probe_compositing()

            if not self._display_image:
                themed_showwarning(
                    "No Preview",
                    "This .procreate file does not contain a preview image.\n"
                    "The file may be corrupted or in an unsupported format.",
                    parent=self,
                )
                self._set_status("No preview available")
                return

            self.title(f"{self.procreate.filename} — {APP_TITLE}")
            self._zoom_fit()
            self._update_info_panel()
            self._update_layers_panel()
            self._update_archive_panel()
            self._set_status(
                f"{self.procreate.filename}  |  "
                f"{self.procreate.canvas_width}×{self.procreate.canvas_height}  |  "
                f"{self.procreate.layer_count} layers  |  "
                f"{self.procreate.get_file_size_human()}"
            )

        except Exception as e:
            themed_showerror("Error", f"Could not open file:\n{e}", parent=self)
            self._set_status("Error opening file")

    # ── Image Rendering ────────────────────────────────────────────────

    def _render_image(self):
        """Render the current image with zoom/pan to the canvas."""
        if not self._display_image:
            return

        self.canvas.delete("all")

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        # Draw checkerboard background for transparency
        self._draw_checkerboard(cw, ch)

        # Scale image
        iw = int(self._display_image.width * self._zoom_level)
        ih = int(self._display_image.height * self._zoom_level)

        if iw < 1 or ih < 1:
            return

        resample = Image.LANCZOS if self._zoom_level < 1 else Image.NEAREST
        if self._zoom_level > 2:
            resample = Image.NEAREST
        elif self._zoom_level <= 1:
            resample = Image.LANCZOS

        resized = self._display_image.resize((iw, ih), resample)
        self._photo_image = ImageTk.PhotoImage(resized)

        x = cw // 2 + self._pan_x
        y = ch // 2 + self._pan_y

        self.canvas.create_image(x, y, image=self._photo_image, anchor="center")

        # Update zoom label
        self.zoom_label.config(text=f"{self._zoom_level:.0%}")

    def _draw_checkerboard(self, width, height):
        """Draw a subtle checkerboard to indicate transparency."""
        size = 16
        c1 = "#151525"
        c2 = "#1A1A30"
        for y in range(0, height + size, size):
            for x in range(0, width + size, size):
                color = c1 if (x // size + y // size) % 2 == 0 else c2
                self.canvas.create_rectangle(
                    x, y, x + size, y + size,
                    fill=color, outline="", tags="checker",
                )

    # ── Zoom / Pan ─────────────────────────────────────────────────────

    def _zoom_in(self):
        self._zoom_level = min(self._zoom_level * 1.25, 10.0)
        self._render_image()

    def _zoom_out(self):
        self._zoom_level = max(self._zoom_level / 1.25, 0.05)
        self._render_image()

    def _zoom_fit(self):
        """Fit image to canvas."""
        if not self._display_image:
            return
        self._pan_x = 0
        self._pan_y = 0
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 700, 500
        iw = self._display_image.width
        ih = self._display_image.height
        if iw == 0 or ih == 0:
            return
        scale = min(cw / iw, ch / ih) * 0.92
        self._zoom_level = scale
        self._render_image()

    def _zoom_actual(self):
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._render_image()

    def _on_pan_start(self, event):
        self._drag_start_x = event.x - self._pan_x
        self._drag_start_y = event.y - self._pan_y

    def _on_pan_move(self, event):
        self._pan_x = event.x - self._drag_start_x
        self._pan_y = event.y - self._drag_start_y
        self._render_image()

    def _on_mouse_wheel(self, event):
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    # ── Info Panel Updates ─────────────────────────────────────────────

    def _update_info_panel(self):
        pf = self.procreate
        if not pf:
            return

        info_lines = [
            f"File:       {pf.filename}",
            f"Size:       {pf.get_file_size_human()}",
            f"Canvas:     {pf.canvas_width} × {pf.canvas_height} px",
            f"DPI:        {pf.dpi}",
            f"Layers:     {pf.layer_count}",
            f"Profile:    {pf.color_profile}",
        ]
        if pf.video_enabled:
            info_lines.append("Timelapse:  Yes")

        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", "\n".join(info_lines))
        self.info_text.config(state="disabled")

    def _update_layers_panel(self):
        pf = self.procreate
        if not pf:
            return

        self.layers_tree.delete(*self.layers_tree.get_children())

        overridden = bool(self._layer_overrides)
        for i, layer in enumerate(pf.layers):
            # Use override visibility if present, else the file's value
            if i in self._layer_overrides:
                vis = self._layer_overrides[i]
            else:
                vis = layer.visible
            icon = "\U0001f441" if vis else "\u2298"   # 👁 / ⊘
            name = f"{icon}  {layer.name}"
            opacity = f"{layer.opacity:.0%}"
            blend = pf.get_blend_mode_name(layer.blend_mode)
            tag = "hidden_layer" if not vis else ""
            self.layers_tree.insert("", "end", text=name,
                                     values=(opacity, blend),
                                     tags=(tag,))

        # Dim hidden layers
        self.layers_tree.tag_configure(
            "hidden_layer", foreground=COLORS["text_dim"]
        )

        if not pf.layers:
            self.layers_tree.insert("", "end", text="  (no layer data)",
                                     values=("", ""))

        # Update hint
        if hasattr(self, '_layers_hint'):
            if self._can_composite:
                self._layers_hint.config(
                    text="Double-click layer to toggle visibility",
                    fg=COLORS["text_dim"],
                )
            else:
                self._layers_hint.config(
                    text="Layer compositing not available for this file",
                    fg=COLORS["warning"],
                )

    def _update_archive_panel(self):
        pf = self.procreate
        if not pf:
            return

        files = pf.get_file_list()
        text = "\n".join(files[:50])
        if len(files) > 50:
            text += f"\n… and {len(files) - 50} more files"

        self.archive_text.config(state="normal")
        self.archive_text.delete("1.0", "end")
        self.archive_text.insert("1.0", text)
        self.archive_text.config(state="disabled")

    # ── Layer visibility helpers ─────────────────────────────────────

    def _probe_compositing(self):
        """Test whether layer chunk data is available."""
        self._can_composite = False
        if not self.procreate or not self.procreate.layers:
            return
        for i in range(len(self.procreate.layers)):
            img = self.procreate.load_layer_image(i)
            if img is not None:
                self._layer_cache[i] = img
                self._can_composite = True
                return

    def _on_layer_toggle(self, event):
        """Toggle layer visibility on double-click."""
        item = self.layers_tree.identify_row(event.y)
        if not item:
            return
        idx = self.layers_tree.index(item)
        if not self.procreate or idx < 0 or idx >= len(self.procreate.layers):
            return

        if not self._can_composite:
            self._set_status(
                "Cannot toggle: layer pixel data not readable in this file"
            )
            return

        current = self._layer_overrides.get(
            idx, self.procreate.layers[idx].visible
        )
        self._layer_overrides[idx] = not current
        self._update_layers_panel()
        self._recomposite()

    def _on_layer_context_menu(self, event):
        """Right-click context menu for layer actions."""
        if not self.procreate or not self.procreate.layers:
            return

        menu = tk.Menu(self, tearoff=0, bg=COLORS["bg2"],
                       fg=COLORS["text"],
                       activebackground=COLORS["accent"])

        item = self.layers_tree.identify_row(event.y)
        if item:
            idx = self.layers_tree.index(item)
            cur = self._layer_overrides.get(
                idx, self.procreate.layers[idx].visible
            )
            lbl = "Hide Layer" if cur else "Show Layer"
            menu.add_command(
                label=lbl,
                command=lambda: self._toggle_layer(idx),
            )
            menu.add_separator()

        menu.add_command(label="Show All Layers",
                         command=self._show_all_layers)
        menu.add_command(label="Hide All Layers",
                         command=self._hide_all_layers)
        menu.add_separator()
        menu.add_command(label="Reset to Original",
                         command=self._reset_layers)

        menu.tk_popup(event.x_root, event.y_root)

    def _toggle_layer(self, idx: int):
        """Toggle a single layer's visibility."""
        if not self._can_composite:
            self._set_status(
                "Cannot toggle: layer pixel data not readable"
            )
            return
        cur = self._layer_overrides.get(
            idx, self.procreate.layers[idx].visible
        )
        self._layer_overrides[idx] = not cur
        self._update_layers_panel()
        self._recomposite()

    def _show_all_layers(self):
        if not self.procreate:
            return
        self._layer_overrides = {
            i: True for i in range(len(self.procreate.layers))
        }
        self._update_layers_panel()
        self._recomposite()

    def _hide_all_layers(self):
        if not self.procreate:
            return
        self._layer_overrides = {
            i: False for i in range(len(self.procreate.layers))
        }
        self._update_layers_panel()
        self._recomposite()

    def _reset_layers(self):
        """Reset all layer visibility to the original file values."""
        self._layer_overrides = {}
        self._display_image = self._original_image
        self._update_layers_panel()
        self._render_image()
        self._set_status("Layer visibility reset to original")

    def _recomposite(self):
        """Re-composite visible layers and update the preview."""
        if not self.procreate:
            return

        self._set_status("Compositing layers\u2026")
        self.update_idletasks()

        if self._can_composite:
            img = self.procreate.composite_layers(self._layer_overrides)
            if img:
                self._display_image = img
                self._render_image()
                hidden_n = sum(
                    1 for i, v in self._layer_overrides.items() if not v
                )
                self._set_status(
                    f"Preview updated  \u2014  "
                    f"{hidden_n} layer(s) hidden"
                )
                return

        # Fallback to original
        self._display_image = self._original_image
        self._render_image()
        self._set_status("Layer compositing failed \u2014 showing original")

    # ── Export ─────────────────────────────────────────────────────────

    def _on_export(self, fmt: str = "PNG"):
        if not self._display_image:
            themed_showinfo("No File", "Open a .procreate file first.", parent=self)
            return

        ext_map = {"PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp", "TIFF": ".tiff"}
        ext = ext_map.get(fmt, ".png")
        base = os.path.splitext(self.procreate.filename)[0] if self.procreate else "export"

        # Note in filename when layers are hidden
        suffix = ""
        if self._layer_overrides:
            hidden_n = sum(1 for v in self._layer_overrides.values() if not v)
            if hidden_n:
                suffix = f"_({hidden_n}_hidden)"

        filepath = filedialog.asksaveasfilename(
            title=f"Export as {fmt}",
            defaultextension=ext,
            initialfile=f"{base}{suffix}{ext}",
            filetypes=[(f"{fmt} Image", f"*{ext}"), ("All Files", "*.*")],
        )
        if not filepath:
            return

        try:
            img = self._display_image
            save_kw = {"format": fmt}
            if fmt.upper() in ("JPEG", "JPG"):
                save_kw["quality"] = 95
                if img.mode == "RGBA":
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
            img.save(filepath, **save_kw)
            self._set_status(f"Exported to {os.path.basename(filepath)}")
            themed_showsuccess("Success", f"Image exported to:\n{filepath}", parent=self)
        except Exception as e:
            themed_showerror("Export Error", str(e), parent=self)

    # ── Batch Convert ──────────────────────────────────────────────────

    def _on_batch_convert(self):
        folder = filedialog.askdirectory(title="Select folder with .procreate files")
        if not folder:
            return

        files = [f for f in os.listdir(folder) if f.lower().endswith(".procreate")]
        if not files:
            themed_showinfo("No Files", "No .procreate files found in this folder.", parent=self)
            return

        out_folder = os.path.join(folder, "PNG_Export")
        os.makedirs(out_folder, exist_ok=True)

        converted = 0
        errors = 0
        for filename in files:
            self._set_status(f"Converting {filename}… ({converted+1}/{len(files)})")
            self.update_idletasks()
            try:
                with ProcreateFile(os.path.join(folder, filename)) as pf:
                    out_name = os.path.splitext(filename)[0] + ".png"
                    pf.export_image(os.path.join(out_folder, out_name))
                    converted += 1
            except Exception:
                errors += 1

        msg = f"Converted {converted} of {len(files)} files.\n"
        if errors:
            msg += f"{errors} file(s) had errors.\n"
        msg += f"\nOutput folder:\n{out_folder}"
        themed_showsuccess("Batch Convert Complete", msg, parent=self)
        self._set_status(f"Batch convert: {converted}/{len(files)} done")

    # ── File Association ───────────────────────────────────────────────

    def _on_settings(self):
        """Open the Settings dialog."""
        SettingsDialog(self)

    # ── About ──────────────────────────────────────────────────────────

    def _on_about(self):
        themed_showinfo(
            "About Procreate Viewer",
            f"Procreate Viewer v{APP_VERSION}\n\n"
            "Open-source Windows application for\n"
            "viewing and previewing .procreate files.\n\n"
            "Features:\n"
            "• View .procreate file previews\n"
            "• Toggle layer visibility\n"
            "• Export to PNG/JPEG/BMP/TIFF\n"
            "• Batch convert folders\n"
            "• Windows Explorer integration\n\n"
            "License: MIT\n"
            "https://github.com/NothingData/ProcreateViewer",
            parent=self,
        )

    # ── Utilities ──────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self.status_label.config(text=text)

    def _on_close(self):
        if self.procreate:
            self.procreate.close()
        self.destroy()


# =====================================================================
# Entry Point
# =====================================================================
def main():
    filepath = None
    if len(sys.argv) > 1:
        filepath = sys.argv[1]

    first_run = not _is_already_installed()

    app = ProcreateViewer(filepath=filepath)

    if first_run:
        app.withdraw()

        def _show_setup():
            dialog = SetupDialog(app)
            app.wait_window(dialog)
            app.deiconify()

        app.after(100, _show_setup)

    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as _exc:
        _crash_path = os.path.join(_BASE_DIR, "crash_log.txt")
        with open(_crash_path, "w", encoding="utf-8") as _f:
            _tb.print_exc(file=_f)
        _hide_file(_crash_path)
        raise
