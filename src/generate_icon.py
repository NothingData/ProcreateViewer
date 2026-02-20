"""
Copy the project logo (logo.ico) to icon.ico in the resources folder.
No icon generation — uses the hand-crafted logo as-is.
"""

import os
import shutil
import sys


def generate_icon():
    """Copy resources/logo.ico → resources/icon.ico."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    res_dir = os.path.join(project_root, "resources")

    logo = os.path.join(res_dir, "logo.ico")
    icon = os.path.join(res_dir, "icon.ico")

    if not os.path.isfile(logo):
        print(f"ERROR: logo.ico not found at {logo}")
        sys.exit(1)

    shutil.copy2(logo, icon)
    file_size = os.path.getsize(icon)
    print(f"Icon ready: {icon} (copied from logo.ico, {file_size:,} bytes)")
    return icon


if __name__ == "__main__":
    generate_icon()
