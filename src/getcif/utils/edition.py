"""版本线检测：Standard（无 3D 依赖）/ Plus（含 3D，预留功能扩展）。

判定依据：Plus 版打包了 matplotlib（3D 预览）；标准版裁剪掉。
开发环境两者依赖齐备，按 Plus 处理。
"""
from __future__ import annotations

from functools import lru_cache

STANDARD = "Standard"
PLUS = "Plus"


@lru_cache(maxsize=1)
def get_edition() -> str:
    """返回当前运行版本线（``Standard`` / ``Plus``）。"""
    try:
        import matplotlib  # noqa: F401
    except Exception:  # noqa: BLE001 - 标准版有意裁剪
        return STANDARD
    return PLUS


def is_plus() -> bool:
    return get_edition() == PLUS
