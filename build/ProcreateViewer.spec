# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['..\\src\\procreate_viewer.py'],
    pathex=[],
    binaries=[],
    datas=[('..\\resources', 'resources'), ('..\\dist\\ProcreateThumbHandler.dll', '.')],
    hiddenimports=['PIL', 'PIL.Image', 'PIL.ImageTk', 'lz4', 'lz4.block'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ProcreateViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='..\\src\\version_info.txt',
    icon=['..\\resources\\icon.ico'],
)
