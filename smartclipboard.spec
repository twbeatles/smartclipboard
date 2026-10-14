# -*- mode: python ; coding: utf-8 -*-
"""
SmartClipboard Pro v10.6 - PyInstaller spec

Build:
    python scripts/preflight_local.py --with-pyright
    pyinstaller --clean smartclipboard.spec

Optional:
    python scripts/preflight_local.py --skip-payload-build --strict-optional-deps --with-pyright

Notes:
    - Static analysis scope lives in pyrightconfig.json and intentionally
      excludes legacy archive/source snapshots from the default Pylance run.
    - Repo-wide pyright is expected to stay at 0 errors.
    - Runtime behavior is restored via legacy marshal payload.
    - Payload builds carry a sidecar manifest with Python/source sync metadata
      plus payload size/SHA-256 validation before marshal load.
    - FILE clipboard/history support depends on smartclipboard_core.file_paths
      and repo-local temp usage during Windows test runs.
    - 2026-04-11 through 2026-04-15 stabilization/refactor keeps the same payload
      data assets and expands hidden-import collection to feature/core
      subpackages (`smartclipboard_app.features`, `smartclipboard_core.automation`).
    - 2026-04-16 functional follow-up keeps packaging scope unchanged:
      action-chain writeback, search relevance preservation, and import filter
      refresh did not require new hidden imports or datas.
    - 2026-04-27 functional implementation review keeps packaging scope
      unchanged: DB restore hardening, FTS backfill, import normalization,
      app path resolver, and DB typing helpers are covered by existing
      collect_submodules rules and the existing payload/manifest datas.
    - 2026-05-11 functional hardening keeps packaging scope unchanged:
      privacy debounce cancellation, deleted_history.url_title migration,
      action writeback merge, restore full/minimal validation, visible hotkey
      failure notices, settings write/read-back checks, and the 1MB text
      clipboard limit use existing modules and datas.
    - 2026-06-10 SOLID split keeps packaging scope unchanged: MainWindow
      bootstrap/dialog/history helpers, settings style submodules,
      import_export services, and db_parts/history subpackages are covered by
      the existing collect_submodules rules and payload/manifest datas.
    - CI now enforces optional runtime dependency presence and pyright via
      `python scripts/preflight_local.py --skip-payload-build --strict-optional-deps --with-pyright`.
    - Frozen packaging is covered by the manual `package-smoke` workflow rather
      than every normal CI matrix run.
    - If legacy source changes, rebuild payload first and keep tests green
      (`test_core`, `test_ui_dialogs_widgets`, `test_payload_sync`,
       `test_legacy_loader`, `test_migration_collections`, `test_legacy_ui_contracts`,
       `test_signal_snapshot`, `test_public_surfaces`, `test_action_palette_core`,
       `test_action_palette_ui`).
    - 2026-08-14 Contextual Action Palette keeps packaging scope unchanged:
      `smartclipboard_core.action_palette` and
      `smartclipboard_app.features.action_palette` are collected by the existing
      `collect_submodules("smartclipboard_core")` and
      `collect_submodules("smartclipboard_app.features")` rules.
"""

from pathlib import Path
from importlib.util import find_spec
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "SmartClipboard"
APP_VERSION = "10.6"
MAIN_SCRIPT = "클립모드 매니저.py"
ICON_FILE = "smartclipboard.ico"
LEGACY_PAYLOAD = Path("smartclipboard_app/legacy_main_payload.marshal")
LEGACY_PAYLOAD_MANIFEST = Path("smartclipboard_app/legacy_main_payload.manifest.json")

if not LEGACY_PAYLOAD.exists():
    raise FileNotFoundError(f"Required legacy payload not found: {LEGACY_PAYLOAD}")
if not LEGACY_PAYLOAD_MANIFEST.exists():
    raise FileNotFoundError(f"Required legacy payload manifest not found: {LEGACY_PAYLOAD_MANIFEST}")

# Keep refactor-safe module coverage for payload runtime imports.
CORE_SUBMODULES = collect_submodules("smartclipboard_core")
DB_PARTS_SUBMODULES = collect_submodules("smartclipboard_core.db_parts")
AUTOMATION_SUBMODULES = collect_submodules("smartclipboard_core.automation")
FEATURE_SUBMODULES = collect_submodules("smartclipboard_app.features")
MAINWINDOW_PARTS_SUBMODULES = collect_submodules("smartclipboard_app.ui.mainwindow_parts")

EXCLUDES = [
    "pytest", "unittest", "test", "tests", "setuptools", "pip", "wheel",
    "pkg_resources", "_pytest", "nose", "mock",
    "numpy", "pandas", "scipy", "matplotlib", "tensorflow", "torch",
    "sklearn", "cv2", "IPython", "jupyter", "notebook",
    "PySide6.QtBluetooth", "PySide6.QtDBus", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtNetwork",
    "PySide6.QtNetworkAuth", "PySide6.QtNfc", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtPositioning", "PySide6.QtPrintSupport",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio", "PySide6.QtSql", "PySide6.QtSvg", "PySide6.QtSvgWidgets",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtWebChannel",
    "PySide6.QtWebEngine", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets", "PySide6.QtXml",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "tkinter", "tcl", "tk", "_tkinter", "xmlrpc", "pydoc", "doctest",
    "distutils", "lib2to3", "multiprocessing", "asyncio", "concurrent",
    "curses", "ensurepip", "email", "http.server", "socketserver",
    "ftplib", "imaplib", "poplib", "smtplib", "telnetlib",
    "turtle", "turtledemo", "pydoc_data", "idlelib",
]

HIDDEN_IMPORTS = [
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "logging.handlers", "hashlib",
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
    "smartclipboard_app.legacy_payload",
    "smartclipboard_app.legacy_main_src",
    "smartclipboard_app.ui.main_window",
    "smartclipboard_app.ui.clipboard_guard",
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
    "smartclipboard_app.ui.dialogs.collections",
    "smartclipboard_app.ui.controllers.clipboard_controller",
    "smartclipboard_app.ui.controllers.table_controller",
    "smartclipboard_app.ui.controllers.tray_hotkey_controller",
    "smartclipboard_app.ui.controllers.lifecycle_controller",
    "smartclipboard_app.managers.secure_vault",
    "smartclipboard_app.managers.export_import",
    "smartclipboard_core.file_paths",
]

OPTIONAL_HIDDEN_IMPORTS = [
    # loaded via legacy_main_payload.marshal (runtime exec); import only if available locally
    "keyboard",
    "cryptography",
    "cryptography.fernet",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "requests",
    "bs4",
    "qrcode",
    "PIL",
    "PIL.ImageQt",
]


def _append_hidden_import(module_name: str) -> None:
    try:
        available = find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        available = False
    if available and module_name not in HIDDEN_IMPORTS:
        HIDDEN_IMPORTS.append(module_name)


for optional_module in OPTIONAL_HIDDEN_IMPORTS:
    _append_hidden_import(optional_module)

for submodule in CORE_SUBMODULES + DB_PARTS_SUBMODULES + AUTOMATION_SUBMODULES + FEATURE_SUBMODULES + MAINWINDOW_PARTS_SUBMODULES:
    if submodule not in HIDDEN_IMPORTS:
        HIDDEN_IMPORTS.append(submodule)

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[],
    binaries=[],
    datas=[
        (str(LEGACY_PAYLOAD), "smartclipboard_app"),
        (str(LEGACY_PAYLOAD_MANIFEST), "smartclipboard_app"),
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
a.datas = [d for d in a.datas if not d[0].startswith("PySide6/Qt/translations")]

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
  Payload manifest: {LEGACY_PAYLOAD_MANIFEST}
{'='*50}
""")
