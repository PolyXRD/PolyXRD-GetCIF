"""PolyXRD 家族资源路径（开发 / PyInstaller _MEIPASS 自适应）。"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG = "getcif"


def get_resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base_dir / _PKG / "resources" / relative_path
    return Path(__file__).resolve().parent.parent.parent / "resources" / relative_path


def _first_existing(*names: str) -> str:
    for name in names:
        path = get_resource_path(name)
        if path.exists():
            return str(path)
    return ""


def get_app_icon_path() -> str:
    """窗口图标（优先 PNG：Qt6 内建解码，启动阶段更稳）。"""
    return _first_existing("app-icon.png", "app-icon.ico")


def get_splash_screen_path() -> str:
    return _first_existing("splash-screen.png")


def get_logo_horizontal_path() -> str:
    return _first_existing("logo-horizontal.png")


def get_crystal_mark_path() -> str:
    return _first_existing("crystal-mark.png")
