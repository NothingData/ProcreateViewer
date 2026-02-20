"""
Windows File Association Installer for .procreate files
=======================================================
Registers the .procreate file extension with Windows so that:
  1. .procreate files have a recognizable description ("Procreate Artwork")
  2. Double-clicking opens ProcreateViewer
  3. A custom icon is set (if available)
  4. "Open with Procreate Viewer" appears in context menu

Must be run as Administrator.

Usage:
    python install_associations.py --viewer "C:\\path\\to\\ProcreateViewer.exe"
    python install_associations.py --uninstall

Author: ProcreateViewer (Open Source)
License: MIT
"""

import sys
import os
import ctypes
import argparse
import winreg


PROG_ID = "ProcreateViewer.procreate"
EXTENSION = ".procreate"
FILE_DESCRIPTION = "Procreate Artwork"
CONTENT_TYPE = "application/x-procreate"


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_viewer_path() -> str:
    """Determine the viewer executable path."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(os.path.join(
        os.path.dirname(__file__), "procreate_viewer.py"
    ))


def install_association(viewer_path: str, icon_path: str = ""):
    """Register .procreate file association in Windows Registry."""
    if not is_admin():
        print("ERROR: Administrator privileges required.")
        print("Right-click and 'Run as Administrator', or use:")
        print('  Start-Process -Verb RunAs -FilePath python -ArgumentList "install_associations.py"')
        sys.exit(1)

    # Determine how to launch
    if viewer_path.lower().endswith(".exe"):
        open_command = f'"{viewer_path}" "%1"'
    else:
        # It's a .py script – launch via Python
        python_exe = sys.executable
        open_command = f'"{python_exe}" "{viewer_path}" "%1"'

    if not icon_path:
        # Try to find icon next to viewer
        base = os.path.dirname(viewer_path)
        for candidate in ["resources/icon.ico", "icon.ico", "ProcreateViewer.ico"]:
            p = os.path.join(base, candidate)
            if os.path.isfile(p):
                icon_path = p
                break

    print(f"Installing .procreate file association...")
    print(f"  Viewer:  {viewer_path}")
    print(f"  Command: {open_command}")
    print(f"  Icon:    {icon_path or '(default)'}")

    try:
        # ── 1. Register the ProgID ──
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, PROG_ID) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, FILE_DESCRIPTION)

            # Default icon
            if icon_path and os.path.isfile(icon_path):
                with winreg.CreateKey(key, "DefaultIcon") as icon_key:
                    winreg.SetValue(icon_key, "", winreg.REG_SZ, f'"{icon_path}",0')
            else:
                # Use the viewer exe itself as icon source
                if viewer_path.lower().endswith(".exe"):
                    with winreg.CreateKey(key, "DefaultIcon") as icon_key:
                        winreg.SetValue(icon_key, "", winreg.REG_SZ, f'"{viewer_path}",0')

            # Shell open command
            with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                winreg.SetValue(cmd_key, "", winreg.REG_SZ, open_command)

            # Friendly app name
            with winreg.CreateKey(key, r"shell\open") as open_key:
                winreg.SetValueEx(open_key, "FriendlyAppName", 0,
                                  winreg.REG_SZ, "Procreate Viewer")

        # ── 2. Register the file extension ──
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, EXTENSION) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, PROG_ID)
            winreg.SetValueEx(key, "Content Type", 0,
                              winreg.REG_SZ, CONTENT_TYPE)
            winreg.SetValueEx(key, "PerceivedType", 0,
                              winreg.REG_SZ, "image")

        # ── 3. Register in OpenWithProgids ──
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT,
                              rf"{EXTENSION}\OpenWithProgids") as key:
            winreg.SetValueEx(key, PROG_ID, 0, winreg.REG_NONE, b"")

        # ── 4. Add "Open with Procreate Viewer" to context menu ──
        with winreg.CreateKey(
            winreg.HKEY_CLASSES_ROOT,
            rf"{EXTENSION}\shell\ProcreateViewer"
        ) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "Open with Procreate Viewer")
            if icon_path and os.path.isfile(icon_path):
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_path)
            with winreg.CreateKey(key, "command") as cmd_key:
                winreg.SetValue(cmd_key, "", winreg.REG_SZ, open_command)

        # ── 5. Register under Applications ──
        app_name = os.path.basename(viewer_path)
        with winreg.CreateKey(
            winreg.HKEY_CLASSES_ROOT,
            rf"Applications\{app_name}\shell\open\command"
        ) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, open_command)

        with winreg.CreateKey(
            winreg.HKEY_CLASSES_ROOT,
            rf"Applications\{app_name}\SupportedTypes"
        ) as key:
            winreg.SetValueEx(key, EXTENSION, 0, winreg.REG_SZ, "")

        # ── 6. Register for current user as well ──
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{EXTENSION}"
        ) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, PROG_ID)

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{PROG_ID}\shell\open\command"
        ) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, open_command)

        # ── 7. Notify Windows of the change ──
        _notify_shell()

        print("\n✓ File association installed successfully!")
        print("  You may need to restart Windows Explorer for changes to take effect.")
        print("  (Or sign out and back in)")

    except PermissionError:
        print("\nERROR: Permission denied. Please run as Administrator.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


def uninstall_association():
    """Remove .procreate file association from Windows Registry."""
    if not is_admin():
        print("ERROR: Administrator privileges required.")
        sys.exit(1)

    print("Removing .procreate file association...")

    keys_to_delete = [
        (winreg.HKEY_CLASSES_ROOT, PROG_ID),
        (winreg.HKEY_CLASSES_ROOT, EXTENSION),
        (winreg.HKEY_CURRENT_USER, rf"Software\Classes\{EXTENSION}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROG_ID}"),
    ]

    for hive, path in keys_to_delete:
        try:
            _delete_key_recursive(hive, path)
            print(f"  Removed: {path}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"  Warning: Could not remove {path}: {e}")

    _notify_shell()
    print("\n✓ File association removed.")


def _delete_key_recursive(hive, path):
    """Recursively delete a registry key and all subkeys."""
    try:
        with winreg.OpenKey(hive, path, 0,
                            winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    subkey = winreg.EnumKey(key, 0)
                    _delete_key_recursive(hive, rf"{path}\{subkey}")
                except OSError:
                    break
        winreg.DeleteKey(hive, path)
    except FileNotFoundError:
        pass


def _notify_shell():
    """Notify Windows Shell that file associations have changed."""
    try:
        from ctypes import windll
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        windll.shell32.SHChangeNotify(
            SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Install/uninstall .procreate file association for Windows"
    )
    parser.add_argument(
        "--viewer", type=str, default="",
        help="Path to ProcreateViewer.exe (or .py script)",
    )
    parser.add_argument(
        "--icon", type=str, default="",
        help="Path to .ico icon file",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove file association",
    )
    args = parser.parse_args()

    if args.uninstall:
        uninstall_association()
    else:
        viewer = args.viewer or get_viewer_path()
        install_association(viewer, args.icon)


if __name__ == "__main__":
    main()
