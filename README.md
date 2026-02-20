# ProcreateViewer for Windows - The Ultimate .procreate File Viewer
<div style="display: flex; justify-content: center; align-items: center; height: 100vh;"> <img width="500" height="500" alt="ProcreateViewer Logo" src="https://github.com/user-attachments/assets/62274360-731f-462a-8701-afc7b537633d" /> </div>


**Preview, open, and export [Procreate](https://procreate.com/) files (`.procreate`) directly on Windows — with native thumbnail previews in File Explorer, just like `.png` or `.jpg` files!**

Are you an iPad artist using Procreate but working on a Windows PC? **ProcreateViewer** is the missing link for your digital art workflow. It allows you to seamlessly view your `.procreate` artwork files on Windows without needing an iPad or Mac. No more guessing what's inside your Procreate files!

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4.svg)
![Version](https://img.shields.io/badge/version-1.0.0-green.svg)

---

## ✨ Features & Capabilities

| Feature | Description |
|---------|-------------|
| **📁 Native Explorer Thumbnails** | See `.procreate` artwork previews directly in Windows File Explorer. Instantly identify your digital paintings without opening them. |
| **🖼️ Full Standalone Viewer** | Open and view `.procreate` files with zoom, pan, and a sleek dark theme UI inspired by Procreate itself. |
| **📑 Detailed Layer Info** | Inspect your artwork's structure. View all layers with their names, opacity levels, visibility status, and blend modes. |
| **🎨 Advanced Layer Compositing** | Full layer compositing and rendering engine. Supports custom visibility overrides to see specific parts of your illustration. |
| **📤 High-Quality Export** | Convert `.procreate` to standard image formats. Export your art to PNG, JPEG, BMP, or TIFF for easy sharing or printing. |
| **📦 Batch Conversion Tool** | Save time by converting entire folders of `.procreate` files to PNG/JPEG at once. Perfect for backing up your portfolio. |
| **🔗 Seamless File Association** | Double-click any `.procreate` file in Windows to open it automatically in the viewer. |
| **⚡ One-Click Installation** | A single, hassle-free installer sets up the application, thumbnail handler, and file associations in seconds. |

---

## 🔍 Why use ProcreateViewer on Windows?

If you transfer your Procreate backups to a Windows PC, you've likely noticed that `.procreate` files show up as blank, unrecognized icons. **ProcreateViewer solves this problem.** 

By installing this lightweight tool, you get:
- **Visual File Management:** Organize your digital art portfolio easily with visual thumbnails in Windows Explorer.
- **Quick Previews:** Check the contents of a `.procreate` file without having to send it back to your iPad.
- **Easy Extraction:** Need a flattened PNG of your artwork? Export it directly from the `.procreate` file on your PC.
- **Layer Inspection:** Review how a piece was constructed by looking at the layer stack, opacity, and blend modes right from your desktop.

---

## 📥 Quick Install (Recommended)

### Option A: Download Setup Installer
1. Go to [**Releases**](../../releases) and download `ProcreateViewer_Setup_v1.0.0.exe`
2. Run the installer — it handles everything automatically
3. Done! Navigate to a folder with `.procreate` files and see thumbnails

### Option B: One-Click Script Install
1. Download or clone this repository
2. Right-click **`INSTALL.bat`** → **Run as administrator**
3. Follow the on-screen prompts
4. Restart Windows Explorer (or sign out/in) for thumbnails

---

## 📸 How It Works Under the Hood

`.procreate` files are essentially ZIP archives containing a `QuickLook/Thumbnail.png` preview image and raw layer data. ProcreateViewer leverages this structure:

1. **Windows Shell Extension** (`ProcreateThumbHandler.dll`) — A custom Windows COM component that instructs File Explorer on how to generate thumbnails for `.procreate` files, making them visible alongside your JPEGs and PNGs.
2. **Standalone Viewer Application** (`ProcreateViewer.exe`) — A dedicated GUI app for opening, inspecting, and exporting `.procreate` files without needing the original Procreate app.
3. **System File Association** — Registers `.procreate` as "Procreate Artwork" in the Windows Registry, complete with a custom icon.

---

## 🏗️ Building from Source

### Prerequisites
- **Python 3.8+** — [python.org](https://www.python.org/downloads/)
- **Windows 10/11** (includes .NET Framework 4 for DLL compilation)
- **Inno Setup 6** *(optional, for building the Setup installer)* — [jrsoftware.org](https://jrsoftware.org/isinfo.php)

### Build Everything
```bat
git clone https://github.com/NothingData/ProcreateViewer.git
cd ProcreateViewer
build.bat
```

This will:
1. Install Python dependencies (Pillow, PyInstaller)
2. Generate the application icon
3. Build `ProcreateViewer.exe` (standalone, ~24 MB)
4. Compile `ProcreateThumbHandler.dll` (shell extension, ~10 KB)
5. Build `ProcreateViewer_Setup_v1.0.0.exe` *(if Inno Setup is installed)*

### Output
```
dist/
  ProcreateViewer.exe          ← Main application
  ProcreateThumbHandler.dll    ← Explorer thumbnail handler

release/
  ProcreateViewer_Setup_v1.0.0.exe  ← Full installer (if Inno Setup available)
```

---

## 📂 Project Structure

```
ProcreateViewer/
├── INSTALL.bat                     # One-click installer (right-click → Run as admin)
├── UNINSTALL.bat                   # One-click uninstaller
├── build.bat                       # Build everything from source
├── requirements.txt                # Python dependencies
├── LICENSE                         # MIT License
├── README.md                       # This file
│
├── src/                            # Source code
│   ├── procreate_viewer.py         # Main GUI application (tkinter)
│   ├── procreate_reader.py         # .procreate file parser
│   ├── generate_icon.py            # Application icon generator
│   ├── install_associations.py     # File association helper
│   └── shell_extension/
│       ├── ProcreateThumbHandler.cs    # C# COM thumbnail provider
│       └── ProcreateThumbHandler.csproj # .NET project file
│
├── resources/
│   └── icon.ico                    # Application icon
│
├── dist/                           # Built binaries (after build.bat)
│   ├── ProcreateViewer.exe
│   └── ProcreateThumbHandler.dll
│
├── installer/
│   └── ProcreateViewer_Setup.iss   # Inno Setup installer script
│
├── scripts/
│   ├── install.ps1                 # PowerShell installer (with progress bar)
│   └── uninstall.ps1               # PowerShell uninstaller
│
└── release/                        # Setup installer output (after build)
    └── ProcreateViewer_Setup_v1.0.0.exe
```

---

## 🔧 Technical Details & Architecture

### The `.procreate` File Format Explained
A `.procreate` file is a ZIP archive containing:
| Path in ZIP | Content |
|-------------|---------|
| `QuickLook/Thumbnail.png` | The preview thumbnail (used by our Shell Extension for Explorer previews) |
| `Document.archive` | A binary plist containing canvas size, layer structure, and metadata |
| `1.chunk`, `2.chunk`, ... | Raw layer pixel data (often LZO or LZ4 compressed) |

### Windows Shell Extension (COM Thumbnail Provider)
- Implements `IThumbnailProvider`, `IInitializeWithFile`, and `IInitializeWithStream` interfaces.
- CLSID: `{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}`
- Extracts `QuickLook/Thumbnail.png` from the `.procreate` ZIP and returns an HBITMAP to Windows Explorer.
- Uses a manual ZIP parser (no external dependencies) for maximum compatibility and speed.
- Compiled with `csc.exe` (.NET Framework 4, no SDK needed, works out-of-the-box on Windows 10/11).

### Python Viewer Application
- Built with Python and `tkinter` (featuring a dark theme, Procreate-inspired UI).
- Uses `Pillow` (PIL) for image processing, compositing, and exporting.
- Packaged as a standalone `.exe` via PyInstaller (no Python installation needed for end-users).
- Supports drag & drop, zoom/pan, and a detailed layer tree view.

---

## 🛠️ Manual Installation

If you prefer to install manually:

### 1. File Association Only
```powershell
# Run as Administrator
New-PSDrive -PSProvider Registry -Root HKEY_CLASSES_ROOT -Name HKCR -EA SilentlyContinue | Out-Null
New-Item -Path "HKCR:\.procreate" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\.procreate" -Name "(Default)" -Value "ProcreateViewer.procreate"
New-Item -Path "HKCR:\ProcreateViewer.procreate\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\ProcreateViewer.procreate\shell\open\command" -Name "(Default)" -Value '"C:\Path\To\ProcreateViewer.exe" "%1"'
```

### 2. Thumbnail Handler Only
```bat
REM Run as Administrator
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe /codebase ProcreateThumbHandler.dll
```

### 3. Unregister Thumbnail Handler
```bat
REM Run as Administrator
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe /unregister ProcreateThumbHandler.dll
```

---

## 💡 Troubleshooting

| Issue | Solution |
|-------|----------|
| **Thumbnails not showing** | Restart Explorer (`taskkill /f /im explorer.exe && start explorer.exe`) or sign out/in |
| **Still no thumbnails** | Set folder view to "Large icons" or "Extra large icons" |
| **Thumbnails broken after update** | Run `INSTALL.bat` again to re-register |
| **Need to uninstall** | Run `UNINSTALL.bat` as administrator, or use "Add/Remove Programs" if you used the Setup installer |
| **"Access denied" errors** | Make sure you right-click → "Run as administrator" |

---

## 📄 License

[MIT License](LICENSE) — free to use, modify, and distribute.

---

## 🤝 Contributing

Contributions welcome! Feel free to:
- Open issues for bugs or feature requests
- Submit pull requests
- Star the repo if you find it useful ⭐

---

**Made with ❤️ for digital artists who use Procreate and Windows**



