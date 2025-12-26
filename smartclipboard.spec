# -*- mode: python ; coding: utf-8 -*-
"""
SmartClipboard Pro v6.2 - PyInstaller Build Spec
빌드 명령: pyinstaller smartclipboard.spec
"""

import sys
import os

block_cipher = None

# 데이터 파일 수집 함수
def collect_data_files_safe(package):
    """안전하게 데이터 파일 수집"""
    try:
        from PyInstaller.utils.hooks import collect_data_files
        return collect_data_files(package)
    except Exception:
        return []

# 추가 숨겨진 임포트
hidden_imports = [
    # PyQt6
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui', 
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    
    # 표준 라이브러리
    'sqlite3',
    'winreg',
    'logging',
    'json',
    're',
    'threading',
    'time',
    'webbrowser',
    'datetime',
    'os',
    'sys',
    
    # 외부 라이브러리
    'keyboard',
    'qrcode',
    'qrcode.main',
    'qrcode.constants',
    'qrcode.util',
    'qrcode.base',
    'qrcode.image',
    'qrcode.image.base',
    'qrcode.image.pil',
    'PIL',
    'PIL.Image',
    'PIL.ImageQt',
    'PIL.ImageDraw',
]

# 데이터 파일 수집
datas = []
datas += collect_data_files_safe('PIL')
datas += collect_data_files_safe('qrcode')

# PyQt6 플러그인 경로 추가
try:
    import PyQt6
    pyqt6_path = os.path.dirname(PyQt6.__file__)
    plugins_path = os.path.join(pyqt6_path, 'Qt6', 'plugins')
    if os.path.exists(plugins_path):
        datas.append((plugins_path, 'PyQt6/Qt6/plugins'))
except Exception:
    pass

a = Analysis(
    ['클립모드 매니저.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy', 
        'pandas',
        'scipy',
        'tkinter',
        '_tkinter',
        'unittest',
        'test',
        'tests',
        'IPython',
        'jupyter',
        'notebook',
        'setuptools',
        'pkg_resources',
        'distutils',
        'lib2to3',
        'xmlrpc',
        'multiprocessing',
    ],
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
    console=False,  # GUI 앱이므로 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 파일이 있으면 'icon.ico' 지정
    uac_admin=False,  # keyboard 라이브러리가 관리자 권한 필요 시 True
)
