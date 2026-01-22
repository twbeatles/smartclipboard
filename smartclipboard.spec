# -*- mode: python ; coding: utf-8 -*-
"""
SmartClipboard Pro v10.3 - PyInstaller Spec File
경량화 및 최적화된 빌드 설정

빌드 명령어:
    pyinstaller smartclipboard.spec

결과물:
    dist/SmartClipboard.exe (단일 실행 파일, ~40MB)
"""

# ============================================
# 기본 설정
# ============================================
APP_NAME = 'SmartClipboard'
APP_VERSION = '10.3'
MAIN_SCRIPT = '클립모드 매니저.py'
ICON_FILE = None  # 아이콘 파일 경로: 'app.ico'

# ============================================
# 경량화를 위한 제외 목록
# ============================================
EXCLUDES = [
    # 테스트/개발 관련
    'pytest', 'unittest', 'test', 'tests', 'setuptools', 'pip', 'wheel',
    'pkg_resources', '_pytest', 'nose', 'mock',
    
    # 대형 라이브러리 (미사용)
    'numpy', 'pandas', 'scipy', 'matplotlib', 'tensorflow', 'torch',
    'sklearn', 'cv2', 'IPython', 'jupyter', 'notebook',
    
    # PyQt6 미사용 모듈
    'PyQt6.QtBluetooth', 'PyQt6.QtDBus', 'PyQt6.QtDesigner', 'PyQt6.QtHelp',
    'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtNetwork',
    'PyQt6.QtNetworkAuth', 'PyQt6.QtNfc', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
    'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets', 'PyQt6.QtPositioning', 'PyQt6.QtPrintSupport',
    'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets',
    'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort',
    'PyQt6.QtSpatialAudio', 'PyQt6.QtSql', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
    'PyQt6.QtTest', 'PyQt6.QtTextToSpeech', 'PyQt6.QtWebChannel',
    'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebSockets', 'PyQt6.QtXml',
    'PyQt6.Qt3DAnimation', 'PyQt6.Qt3DCore', 'PyQt6.Qt3DExtras',
    'PyQt6.Qt3DInput', 'PyQt6.Qt3DLogic', 'PyQt6.Qt3DRender',
    
    # 기타 불필요 모듈
    'tkinter', 'tcl', 'tk', '_tkinter', 'xmlrpc', 'pydoc', 'doctest',
    'distutils', 'lib2to3', 'multiprocessing', 'asyncio', 'concurrent',
    'curses', 'ensurepip', 'email', 'http.server', 'socketserver',
    'ftplib', 'imaplib', 'poplib', 'smtplib', 'telnetlib',
    'turtle', 'turtledemo', 'pydoc_data', 'idlelib',
]

# ============================================
# 숨겨진 임포트 (동적 임포트)
# ============================================
HIDDEN_IMPORTS = [
    'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    'logging.handlers', 'hashlib',
    # 선택적 라이브러리
    'cryptography', 'cryptography.fernet',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'requests', 'bs4', 'qrcode', 'PIL', 'PIL.ImageQt',
]

# ============================================
# Analysis
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
    optimize=2,  # -OO 최적화 (docstring 제거)
)

# ============================================
# 바이너리 필터링 (경량화)
# ============================================
EXCLUDE_BINARIES = [
    'Qt6Bluetooth', 'Qt6DBus', 'Qt6Designer', 'Qt6Help', 'Qt6Multimedia',
    'Qt6Network', 'Qt6Nfc', 'Qt6OpenGL', 'Qt6Pdf', 'Qt6Positioning',
    'Qt6PrintSupport', 'Qt6Qml', 'Qt6Quick', 'Qt6RemoteObjects',
    'Qt6Sensors', 'Qt6SerialPort', 'Qt6Sql', 'Qt6Svg', 'Qt6Test',
    'Qt6WebChannel', 'Qt6WebEngine', 'Qt6WebSockets', 'Qt6Xml', 'Qt63D',
    'Qt6VirtualKeyboard', 'Qt6Charts', 'Qt6DataVisualization',
    'd3dcompiler', 'opengl32sw', 'libGLESv2', 'libEGL', '.pdb',
]

a.binaries = [b for b in a.binaries 
              if not any(ex.lower() in b[0].lower() for ex in EXCLUDE_BINARIES)]

# Qt 번역 파일 제거
a.datas = [d for d in a.datas if not d[0].startswith('PyQt6/Qt6/translations')]

# ============================================
# PYZ 아카이브
# ============================================
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll', 'vcruntime140_1.dll', 'python*.dll',
        'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
    version=None,
    uac_admin=False,
    uac_uiaccess=False,
)

# ============================================
# 빌드 정보
# ============================================
print(f"""
{'='*50}
  SmartClipboard Pro v{APP_VERSION} Build
{'='*50}
  Output: dist/{APP_NAME}.exe
  UPX: {'Enabled' if exe.upx else 'Disabled'}
  Optimization: Level {a.optimize}
  Excluded: {len(EXCLUDES)} modules
{'='*50}
""")
