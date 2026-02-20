# Changelog

All notable changes to ProcreateViewer will be documented in this file.

## [1.0.0] - 2026-02-20

### Added
- **ProcreateViewer.exe** — Standalone GUI application for viewing `.procreate` files
  - Dark theme (Procreate-inspired)
  - Zoom and pan controls
  - Layer tree view with opacity, visibility, blend modes
  - Full layer compositing and rendering (supports custom visibility overrides)
  - Extract and view individual layer images
  - Export to PNG, JPEG, BMP, TIFF
  - Batch convert entire folders
  - File metadata display (canvas size, DPI, layer count)
- **ProcreateThumbHandler.dll** — Windows Shell Extension for Explorer thumbnails
  - Implements COM `IThumbnailProvider` interface
  - Extracts `QuickLook/Thumbnail.png` from `.procreate` ZIP archives
  - Manual ZIP parser (no external dependencies)
  - Works with .NET Framework 4 (pre-installed on Windows 10/11)
- **File Association** — `.procreate` registered as "Procreate Artwork"
  - Custom icon
  - Double-click to open
  - "Open with Procreate Viewer" context menu
- **One-Click Installer** — `INSTALL.bat` installs everything with admin elevation
- **Inno Setup Script** — Professional Setup wizard with component selection
- **Uninstaller** — `UNINSTALL.bat` cleanly removes everything
