# -*- mode: python ; coding: utf-8 -*-
"""
SmartClipboard Pro v10.6 - PyInstaller spec

Build:
    pyinstaller smartclipboard.spec
"""

from pathlib import Path

APP_NAME = "SmartClipboard"
APP_VERSION = "10.6"
MAIN_SCRIPT = "클립모드 매니저.py"
ICON_FILE = None
LEGACY_PAYLOAD = Path("smartclipboard_app/legacy_main_payload.marshal")

if not LEGACY_PAYLOAD.exists():
    raise FileNotFoundError(f"Required legacy payload not found: {LEGACY_PAYLOAD}")

EXCLUDES = [
    "pytest", "unittest", "test", "tests", "setuptools", "pip", "wheel",
    "pkg_resources", "_pytest", "nose", "mock",
    "numpy", "pandas", "scipy", "matplotlib", "tensorflow", "torch",
    "sklearn", "cv2", "IPython", "jupyter", "notebook",
    "PyQt6.QtBluetooth", "PyQt6.QtDBus", "PyQt6.QtDesigner", "PyQt6.QtHelp",
    "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets", "PyQt6.QtNetwork",
    "PyQt6.QtNetworkAuth", "PyQt6.QtNfc", "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets",
    "PyQt6.QtPdf", "PyQt6.QtPdfWidgets", "PyQt6.QtPositioning", "PyQt6.QtPrintSupport",
    "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtQuick3D", "PyQt6.QtQuickWidgets",
    "PyQt6.QtRemoteObjects", "PyQt6.QtSensors", "PyQt6.QtSerialPort",
    "PyQt6.QtSpatialAudio", "PyQt6.QtSql", "PyQt6.QtSvg", "PyQt6.QtSvgWidgets",
    "PyQt6.QtTest", "PyQt6.QtTextToSpeech", "PyQt6.QtWebChannel",
    "PyQt6.QtWebEngine", "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebSockets", "PyQt6.QtXml",
    "PyQt6.Qt3DAnimation", "PyQt6.Qt3DCore", "PyQt6.Qt3DExtras",
    "PyQt6.Qt3DInput", "PyQt6.Qt3DLogic", "PyQt6.Qt3DRender",
    "tkinter", "tcl", "tk", "_tkinter", "xmlrpc", "pydoc", "doctest",
    "distutils", "lib2to3", "multiprocessing", "asyncio", "concurrent",
    "curses", "ensurepip", "email", "http.server", "socketserver",
    "ftplib", "imaplib", "poplib", "smtplib", "telnetlib",
    "turtle", "turtledemo", "pydoc_data", "idlelib",
]

HIDDEN_IMPORTS = [
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "logging.handlers", "hashlib",
    # loaded via legacy_main_payload.marshal (runtime exec); PyInstaller can't see these statically
    "keyboard",
    # stdlib modules used inside the legacy payload
    "uuid",
    "winreg",
    "webbrowser",
    "csv",
    "base64",
    "shutil",
    "urllib.parse",
    "smartclipboard_app.bootstrap",
    "smartclipboard_app.legacy_main",
    "smartclipboard_app.legacy_main_src",
    "smartclipboard_app.ui.main_window",
    "smartclipboard_app.ui.widgets.toast",
    "smartclipboard_app.ui.widgets.floating_mini_window",
    "smartclipboard_app.ui.dialogs.settings",
    "smartclipboard_app.ui.dialogs.secure_vault",
    "smartclipboard_app.ui.dialogs.clipboard_actions",
    "smartclipboard_app.ui.dialogs.export_dialog",
    "smartclipboard_app.ui.dialogs.import_dialog",
    "smartclipboard_app.ui.dialogs.trash_dialog",
    "smartclipboard_app.ui.dialogs.hotkeys",
    "smartclipboard_app.ui.dialogs.snippets",
    "smartclipboard_app.ui.dialogs.tags",
    "smartclipboard_app.ui.dialogs.statistics",
    "smartclipboard_app.ui.dialogs.copy_rules",
    "smartclipboard_app.ui.controllers.clipboard_controller",
    "smartclipboard_app.ui.controllers.table_controller",
    "smartclipboard_app.ui.controllers.tray_hotkey_controller",
    "smartclipboard_app.ui.controllers.lifecycle_controller",
    "smartclipboard_app.managers.secure_vault",
    "smartclipboard_app.managers.export_import",
    "cryptography", "cryptography.fernet",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "requests", "bs4", "qrcode", "PIL", "PIL.ImageQt",
]

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[],
    binaries=[],
    datas=[
        (str(LEGACY_PAYLOAD), "smartclipboard_app"),
    ],
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,
)

EXCLUDE_BINARIES = [
    "Qt6Bluetooth", "Qt6DBus", "Qt6Designer", "Qt6Help", "Qt6Multimedia",
    "Qt6Network", "Qt6Nfc", "Qt6OpenGL", "Qt6Pdf", "Qt6Positioning",
    "Qt6PrintSupport", "Qt6Qml", "Qt6Quick", "Qt6RemoteObjects",
    "Qt6Sensors", "Qt6SerialPort", "Qt6Sql", "Qt6Svg", "Qt6Test",
    "Qt6WebChannel", "Qt6WebEngine", "Qt6WebSockets", "Qt6Xml", "Qt63D",
    "Qt6VirtualKeyboard", "Qt6Charts", "Qt6DataVisualization",
    "d3dcompiler", "opengl32sw", "libGLESv2", "libEGL", ".pdb",
]

a.binaries = [
    b for b in a.binaries if not any(ex.lower() in b[0].lower() for ex in EXCLUDE_BINARIES)
]
a.datas = [d for d in a.datas if not d[0].startswith("PyQt6/Qt6/translations")]

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
        "vcruntime140.dll", "vcruntime140_1.dll", "python*.dll",
        "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll",
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

print(f"""
{'='*50}
  SmartClipboard Pro v{APP_VERSION} Build
{'='*50}
  Output: dist/{APP_NAME}.exe
  UPX: {'Enabled' if exe.upx else 'Disabled'}
  Optimization: Level {a.optimize}
  Excluded: {len(EXCLUDES)} modules
  Legacy payload: {LEGACY_PAYLOAD}
{'='*50}
""")
