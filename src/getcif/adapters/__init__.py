"""适配器注册表。"""
from __future__ import annotations

from getcif.adapters.amcsd import AmcsdAdapter
from getcif.adapters.atomly import AtomlyAdapter
from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.adapters.cod import CodAdapter
from getcif.adapters.cod_local import CodLocalAdapter
from getcif.adapters.mp import MpAdapter
from getcif.adapters.polydb import PolyDbAdapter
from getcif.adapters.xindb import XinDbAdapter

#: 检索顺序（COD 优先，本地库兜底：COD 索引 / polyDB / xinDB）
ADAPTER_CLASSES = [
    CodAdapter, AmcsdAdapter, MpAdapter, AtomlyAdapter,
    CodLocalAdapter, PolyDbAdapter, XinDbAdapter,
]


def create_adapters(timeout: int) -> list[BaseAdapter]:
    """构造全部适配器（可用性由各适配器自查）。"""
    return [cls(timeout=timeout) for cls in ADAPTER_CLASSES]


__all__ = [
    "ADAPTER_CLASSES",
    "AdapterError",
    "AmcsdAdapter",
    "AtomlyAdapter",
    "BaseAdapter",
    "CodAdapter",
    "CodLocalAdapter",
    "MpAdapter",
    "PolyDbAdapter",
    "XinDbAdapter",
    "create_adapters",
]
