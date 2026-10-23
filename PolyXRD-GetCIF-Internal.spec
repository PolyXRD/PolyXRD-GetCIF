# -*- mode: python ; coding: utf-8 -*-
"""PolyXRD GetCIF Internal —— PyInstaller 配置（onefile，Plus 基底，无注册机制）。

内部评估版特性：
    * 基于 **Plus 版**（含 matplotlib/numpy 3D 预览 + 全量 Qt）；
    * 打包时注入标记文件 ``_internal_edition.marker``，运行时
      ``utils/build_variant.py`` 据此判定 —— 注册机制整体停用，
      状态栏最右侧固定显示「内部评估版本」；
    * exe 命名为 ``PolyXRD-GetCIF-Internal.exe``。

用法::

    set GETCIF_VERSION=1.2.0
    python -m PyInstaller PolyXRD-GetCIF-Internal.spec --noconfirm --clean
    # 产物: dist\PolyXRD-GetCIF-Internal.exe
"""
from __future__ import annotations

import os

from PyInstaller.utils.hooks import collect_all

APP_NAME = "PolyXRD-GetCIF-Internal"
VERSION = os.environ.get("GETCIF_VERSION", "1.2.0")

_ROOT = os.path.abspath(SPECPATH)  # noqa: F821

datas = [
    (os.path.join(_ROOT, "resources"), "getcif/resources"),
]

# ---- 内部评估版标记（运行时 build_variant.is_internal_edition 检测）------
_MARKER = os.path.join(_ROOT, "build", "_internal_edition.marker")
os.makedirs(os.path.dirname(_MARKER), exist_ok=True)
with open(_MARKER, "w", encoding="utf-8") as _handle:
    _handle.write("PolyXRD GetCIF Internal Evaluation Edition\n")
datas.append((_MARKER, "."))

binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = [
    "getcif.gui",
    "getcif.search",
    "getcif.cifparse",
    "getcif.viz3d",
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
    "getcif.adapters.polydb",
    "getcif.adapters.xindb",
    "getcif.ui.main_window",
    "getcif.ui.search_panel",
    "getcif.ui.result_table",
    "getcif.ui.preview_dialog",
    "getcif.ui.settings_dialog",
    "getcif.ui.about_dialog",
    "getcif.ui.license_dialog",
    "getcif.ui.theme",
    "getcif.utils.resources",
    "getcif.utils.edition",
    "getcif.utils.build_variant",
    # matplotlib Qt 后端（3D 预览）
    "matplotlib.backends.backend_qtagg",
]

#: 仅用于过滤 PySide6 收集结果的大件（WebEngine / QML）
_QT_BLOAT_TOKENS: tuple[str, ...] = (
    "webengine", "qtwebengine", "qtqml", "qtquick", "qt3d",
)

ANALYSIS_EXCLUDES: list[str] = [
    "tkinter",
    "pydoc_data",
    "pytest",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
]


def _is_qt_bloat(item: object) -> bool:
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
            StringStruct("FileDescription", "PolyXRD GetCIF Internal - CIF Search & Fetch Tool (3D)"),
            StringStruct("FileVersion", "{VERSION}"),
            StringStruct("InternalName", "PolyXRD-GetCIF-Internal"),
            StringStruct("LegalCopyright", "Copyright (c) 2026 PolyXRD Team"),
            StringStruct("OriginalFilename", "PolyXRD-GetCIF-Internal.exe"),
            StringStruct("ProductName", "PolyXRD GetCIF Internal"),
            StringStruct("ProductVersion", "{VERSION}"),
          ],
        )
      ]
    ),
    VarFileInfo([VarStruct("Translation", [0x804, 1200])]),
  ],
)
"""
    target = os.path.join(_ROOT, "build", "version_info_internal.txt")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    return target


for _package in ("PySide6", "matplotlib", "numpy"):
    _d, _b, _h = collect_all(_package)
    if _package == "PySide6":
        datas += [entry for entry in _d if not _is_qt_bloat(entry)]
        binaries += [entry for entry in _b if not _is_qt_bloat(entry)]
    else:
        datas += list(_d)
        binaries += list(_b)
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
    a.binaries,
    a.datas,
    [],
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
