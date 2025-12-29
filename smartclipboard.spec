# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['클립모드 매니저.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PIL', 'qrcode', 'sqlite3', 'keyboard', 'sys', 'os', 'shutil', 'logging', 'json'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'email', 'http', 'xmlrpc', 'pydoc', 'multiprocessing', 'asyncio', 'concurrent', 'ftplib', 'distutils', '_bz2', '_lzma'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SmartClipboardPro',
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
    icon=None, 
)
