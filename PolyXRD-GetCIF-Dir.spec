# -*- mode: python ; coding: utf-8 -*-
"""PolyXRD GetCIF 标准版 —— PyInstaller 配置（**onedir**，供 Setup 安装包使用）。

与 PolyXRD-GetCIF.spec（onefile 标准版）的唯一差异是打包形态：
    * onedir 目录模式 —— 安装包直接引用目录内容，启动**无需自解压**；
    * 输出 ``dist\\PolyXRD-GetCIF\\``（内含 ``PolyXRD-GetCIF.exe``）；
    * 其余（去 3D + 裁剪 Qt + 注册机制）与 onefile 标准版完全一致。

用法::

    set GETCIF_VERSION=1.2.0
    python -m PyInstaller PolyXRD-GetCIF-Dir.spec --noconfirm --clean
    # 产物: dist\PolyXRD-GetCIF\PolyXRD-GetCIF.exe
"""
from __future__ import annotations

import os

from PyInstaller.utils.hooks import collect_all

APP_NAME = "PolyXRD-GetCIF"
VERSION = os.environ.get("GETCIF_VERSION", "1.2.0")

_ROOT = os.path.abspath(SPECPATH)  # noqa: F821

datas = [
    (os.path.join(_ROOT, "resources"), "getcif/resources"),
]
binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = [
    "getcif.gui",
    "getcif.search",
    "getcif.cifparse",
    "getcif.viz_elements",
    "getcif.i18n",
    "getcif.core.config",
    "getcif.core.schema",
    "getcif.core.formula",
    "getcif.adapters",
    "getcif.adapters.base",
    "getcif.adapters.cod",
    "getcif.adapters.cod_local",
    "getcif.adapters.amcsd",
    "getcif.adapters.mp",
    "getcif.adapters.atomly",
    "getcif.ui.main_window",
    "getcif.ui.search_panel",
    "getcif.ui.result_table",
    "getcif.ui.preview_dialog",
    "getcif.ui.settings_dialog",
    "getcif.ui.about_dialog",
    "getcif.ui.theme",
    "getcif.utils.resources",
    "getcif.utils.edition",
    "getcif.utils.registration",
]

# ---- 标准版体积裁剪（与 onefile 标准版保持一致）--------------------------
_QT_BLOAT_TOKENS: tuple[str, ...] = (
    "webengine", "qtwebengine", "qtqml", "qtquick", "qt3d",
    "qtmultimedia", "qtaudio", "qt6camera",
    "qtpdf",
    "qtcharts", "qtdatavis",
    "qtsql",
    "qttest",
    "qtdesigner", "quitools", "qthelp", "qtlinguist", "qtassistant",
    "qtnetwork",
    "qtserialport", "qtserialbus",
    "qtsensors", "qtpositioning", "qtlocation",
    "qtwebchannel", "qtwebsockets", "qtwebview",
    "qtbluetooth", "qtnfc",
    "qtvirtualkeyboard",
    "qttexttospeech",
    "qtscxml", "qtremoteobjects", "qtstatemachine",
    "qtspatialaudio", "qthttpserver", "qtgrpc", "qtprotobuf",
    "qtquick3d", "qtlabs",
)

ANALYSIS_EXCLUDES: list[str] = [
    "tkinter",
    "pydoc_data",
    "pytest",
    "matplotlib",
    "numpy",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtHelp",
    "PySide6.QtNetwork", "PySide6.QtNetworkAuth",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.QtSensors", "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtWebView",
    "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtTextToSpeech",
    "PySide6.QtScxml", "PySide6.QtRemoteObjects", "PySide6.QtStateMachine",
]


def _is_bloat(item: object) -> bool:
    text = str(item).lower()
    return any(token in text for token in _QT_BLOAT_TOKENS)


def _write_version_info() -> str:
    major, minor, patch = (VERSION.split(".") + ["0", "0", "0"])[:3]
    tuple_version = tuple(int(p) for p in (major, minor, patch)) + (0,)
    text = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tuple_version},
    prodvers={tuple_version},
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          "080404B0",
          [
            StringStruct("CompanyName", "PolyXRD Team"),
            StringStruct("FileDescription", "PolyXRD GetCIF (Standard) - CIF Search & Fetch Tool"),
            StringStruct("FileVersion", "{VERSION}"),
            StringStruct("InternalName", "PolyXRD-GetCIF"),
            StringStruct("LegalCopyright", "Copyright (c) 2026 PolyXRD Team"),
            StringStruct("OriginalFilename", "PolyXRD-GetCIF.exe"),
            StringStruct("ProductName", "PolyXRD GetCIF (Standard)"),
            StringStruct("ProductVersion", "{VERSION}"),
          ],
        )
      ]
    ),
    VarFileInfo([VarStruct("Translation", [0x804, 1200])]),
  ],
)
"""
    target = os.path.join(_ROOT, "build", "version_info_dir.txt")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    return target


# 标准版只收 PySide6（过滤后），不收 matplotlib / numpy
_d, _b, _h = collect_all("PySide6")
datas += [entry for entry in _d if not _is_bloat(entry)]
binaries += [entry for entry in _b if not _is_bloat(entry)]
hiddenimports += list(_h)


a = Analysis(
    [os.path.join(_ROOT, "src", "getcif", "gui.py")],
    pathex=[os.path.join(_ROOT, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=ANALYSIS_EXCLUDES,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(_ROOT, "resources", "app-icon.ico")],
    version=_write_version_info(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
