# -*- mode: python ; coding: utf-8 -*-
"""
SmartClipboard Pro v8.0 - PyInstaller Spec File
빌드 명령: pyinstaller smartclipboard.spec
"""

import sys
from pathlib import Path

block_cipher = None

# 소스 파일 경로
source_file = '클립모드 매니저.py'

a = Analysis(
    [source_file],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt6
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        # 암호화
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.backends',
        # 웹 스크래핑
        'requests',
        'bs4',
        'beautifulsoup4',
        # QR 코드
        'qrcode',
        'PIL',
        'PIL.Image',
        # 키보드
        'keyboard',
        # 기타
        'sqlite3',
        'json',
        'csv',
        'uuid',
        'base64',
        'logging',
        'threading',
        'winreg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'tkinter',
        'test',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SmartClipboard Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 앱이므로 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 파일이 있으면 여기에 경로 지정: 'app.ico'
    version_info=None,
    uac_admin=False,  # 관리자 권한 불필요
)
