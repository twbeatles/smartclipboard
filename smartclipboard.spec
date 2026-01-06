# -*- mode: python ; coding: utf-8 -*-
"""
SmartClipboard Pro v10.0 - PyInstaller Spec File
경량화 및 최적화된 빌드 설정

빌드 명령어:
    pyinstaller smartclipboard.spec

결과물:
    dist/SmartClipboard.exe (단일 실행 파일)
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ============================================
# 기본 설정
# ============================================
APP_NAME = 'SmartClipboard'
APP_VERSION = '10.0'
MAIN_SCRIPT = '클립모드 매니저.py'
ICON_FILE = None  # 아이콘 파일이 있으면 경로 지정: 'app.ico'

# ============================================
# 경량화를 위한 제외 목록 (강화됨)
# ============================================
EXCLUDES = [
    # 테스트/개발 관련
    'pytest', 'unittest', 'test', 'tests',
    'setuptools', 'pip', 'wheel', 'pkg_resources',
    '_pytest', 'nose', 'mock',
    
    # 사용하지 않는 대형 라이브러리
    'numpy', 'pandas', 'scipy', 'matplotlib',
    'tensorflow', 'torch', 'sklearn', 'cv2',
    'IPython', 'jupyter', 'notebook',
    'sympy', 'networkx', 'nltk',
    
    # Qt 사용하지 않는 모듈 (전체 목록)
    'PyQt6.QtBluetooth',
    'PyQt6.QtDBus',
    'PyQt6.QtDesigner',
    'PyQt6.QtHelp',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtNetworkAuth',
    'PyQt6.QtNfc',
    'PyQt6.QtOpenGL',
    'PyQt6.QtOpenGLWidgets',
    'PyQt6.QtPdf',
    'PyQt6.QtPdfWidgets',
    'PyQt6.QtPositioning',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtQml',
    'PyQt6.QtQuick',
    'PyQt6.QtQuick3D',
    'PyQt6.QtQuickWidgets',
    'PyQt6.QtRemoteObjects',
    'PyQt6.QtSensors',
    'PyQt6.QtSerialPort',
    'PyQt6.QtSpatialAudio',
    'PyQt6.QtSql',
    'PyQt6.QtSvg',
    'PyQt6.QtSvgWidgets',
    'PyQt6.QtTest',
    'PyQt6.QtTextToSpeech',
    'PyQt6.QtWebChannel',
    'PyQt6.QtWebEngine',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebSockets',
    'PyQt6.QtXml',
    'PyQt6.Qt3DAnimation',
    'PyQt6.Qt3DCore',
    'PyQt6.Qt3DExtras',
    'PyQt6.Qt3DInput',
    'PyQt6.Qt3DLogic',
    'PyQt6.Qt3DRender',
    
    # 기타 불필요한 모듈
    'tkinter', 'tcl', 'tk', '_tkinter',
    'xmlrpc', 'pydoc', 'doctest',
    'distutils', 'lib2to3',
    'multiprocessing',
    'asyncio',
    'concurrent',
    'curses',
    'ensurepip',
    
    # 추가 경량화 (v10.0)
    'html.parser',
    'email',
    'http.server',
    'socketserver',
    'ftplib',
    'imaplib',
    'poplib',
    'smtplib',
    'telnetlib',
    'turtle',
    'turtledemo',
    'pydoc_data',
    'idlelib',
]

# ============================================
# 숨겨진 임포트 (동적 임포트 처리)
# ============================================
HIDDEN_IMPORTS = [
    # PyQt6 필수 모듈
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    
    # 로깅 핸들러
    'logging.handlers',
    
    # hashlib (이미지 중복 체크용)
    'hashlib',
    
    # 선택적 라이브러리 (없으면 무시됨)
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'requests',
    'bs4',
    'qrcode',
    'PIL',
    'PIL.ImageQt',
]

# ============================================
# Analysis 설정
# ============================================
a = Analysis(
    [MAIN_SCRIPT],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,  # Python 최적화 레벨 (2 = -OO, docstring 제거)
)

# ============================================
# 불필요한 바이너리 제거 (경량화)
# ============================================
EXCLUDE_BINARIES = [
    # Qt 관련 불필요 DLL
    'Qt6Bluetooth', 'Qt6DBus', 'Qt6Designer', 'Qt6Help',
    'Qt6Multimedia', 'Qt6Network', 'Qt6Nfc', 'Qt6OpenGL',
    'Qt6Pdf', 'Qt6Positioning', 'Qt6PrintSupport', 'Qt6Qml',
    'Qt6Quick', 'Qt6RemoteObjects', 'Qt6Sensors', 'Qt6SerialPort',
    'Qt6Sql', 'Qt6Svg', 'Qt6Test', 'Qt6WebChannel',
    'Qt6WebEngine', 'Qt6WebSockets', 'Qt6Xml', 'Qt63D',
    
    # 언어 리소스 (영어만 유지)
    'qtbase_', 'qt_',  # 부분 매칭으로 번역 파일 제외
    
    # 디버그 심볼
    '.pdb',
    
    # 개발용 파일
    'd3dcompiler',
    'opengl32sw',
    'libGLESv2',
    'libEGL',
    
    # 추가 경량화 (v10.0)
    'Qt6VirtualKeyboard',
    'Qt6Charts',
    'Qt6DataVisualization',
    'Qt6Scxml',
    'Qt6ShaderTools',
]

def should_exclude_binary(name):
    """바이너리 제외 여부 결정"""
    name_lower = name.lower()
    for exclude in EXCLUDE_BINARIES:
        if exclude.lower() in name_lower:
            return True
    return False

# 바이너리 필터링
a.binaries = [b for b in a.binaries if not should_exclude_binary(b[0])]

# ============================================
# 데이터 파일 정리 (경량화)
# ============================================
# Qt 번역 파일 제거
a.datas = [d for d in a.datas if not d[0].startswith('PyQt6/Qt6/translations')]

# 불필요한 데이터 파일 제거
EXCLUDE_DATA_PATTERNS = [
    'certifi',  # SSL 인증서 (필요 시 유지)
    'tcl', 'tk',
    'matplotlib',
    'numpy',
]
a.datas = [d for d in a.datas if not any(p in d[0] for p in EXCLUDE_DATA_PATTERNS)]

# ============================================
# PYZ 아카이브 (Python 바이트코드)
# ============================================
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

# ============================================
# EXE 설정
# ============================================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Windows에서는 strip 비활성화
    upx=True,     # UPX 압축 활성화 (설치 필요)
    upx_exclude=[
        # UPX 압축에서 제외할 파일 (문제 발생 시)
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'python*.dll',
        'Qt6Core.dll',
        'Qt6Gui.dll',
        'Qt6Widgets.dll',
    ],
    runtime_tmpdir=None,
    console=False,  # 콘솔 창 숨김 (GUI 앱)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
    version=None,
    uac_admin=False,  # 관리자 권한 불필요
    uac_uiaccess=False,
)

# ============================================
# 빌드 정보 출력
# ============================================
print("\n" + "=" * 50)
print(f"  SmartClipboard Pro v{APP_VERSION} Build Configuration")
print("=" * 50)
print(f"  Main Script: {MAIN_SCRIPT}")
print(f"  Output: dist/{APP_NAME}.exe")
print(f"  Console: {'Yes' if exe.console else 'No (GUI)'}")
print(f"  UPX Compression: {'Enabled' if exe.upx else 'Disabled'}")
print(f"  Optimization Level: {a.optimize}")
print(f"  Excluded Modules: {len(EXCLUDES)}")
print(f"  Hidden Imports: {len(HIDDEN_IMPORTS)}")
print("=" * 50)
print("  경량화 최적화 적용:")
print("    - 불필요한 Qt 모듈 제외")
print("    - 번역 파일 제거")
print("    - UPX 압축 활성화")
print("    - Python -OO 최적화")
print("=" * 50 + "\n")
