"""本地库发现与路径解析（v1.4.0：多库挂载公共层）。

PolyXRD v4.0.0 与 XinMatch v2.0.0 都把外挂库从「一种格式一个槽位」改成
**列表式多库挂载**：同一格式可以挂多份（COD 无机子集 + COD 全库、别人裁的
子集、移动硬盘上的另一份）。本模块把这套语义的**发现规则**抽出来，供
polyDB / xinDB 两个适配器与设置界面共用：

* :func:`discover` —— 用户填的一个路径，可能本身就是一个库，也可能是
  「装着若干库的目录」（例如 ``PolyXRD-DataBase/polydb`` 下并排放着
  ``COD-Inorg-*.polyDB`` 与 ``COD-Full-*.polyDB``）。两种都吃。
* :func:`cif_base_dirs` —— polyDB 的 ``cif_rel`` 是**相对 COD 数据根**的
  路径（``1/00/00/1000003.cif``），而数据根在不同机器上落在不同盘符。
  这里按「显式配置 → 环境变量 → 库自述 → 库所在目录」的顺序给出候选根。

设计约束与 PolyXRD ``db_mounts`` 一致：
1. **只读**：所有探测只做 stat / 只读 sqlite 打开，绝不写用户的库。
2. **探测不缓存**：库可能被换盘、被删、被重建，界面每次打开都重新 stat。
3. **不猜格式**：判不出来就返回明确原因，不做"大概能用"的妥协。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional

#: 数据根环境变量（PolyXRD-DataBase README 约定的覆盖方式）
DATA_ROOT_ENV = "XRD_DATA_ROOT"

#: COD 家族子库名（sync-COD 布局：COD / PCOD / TCOD）
COD_FAMILY = ("COD", "PCOD", "TCOD")

#: polyDB 目录后缀（大小写不敏感比较，Windows 上常见 ``.polyDB`` / ``.polydb``）
POLYDB_SUFFIX = ".polydb"
#: xinDB 文件后缀
XINDB_SUFFIX = ".xindb"


def dedupe(items: Iterable[object]) -> list:
    """去重并保持顺序（Windows 下路径大小写不敏感，按 normcase 判重）。"""
    seen: set[str] = set()
    out: list = []
    for item in items:
        if item is None:
            continue
        key = os.path.normcase(str(item))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _children(path: Path) -> list[Path]:
    try:
        return sorted(path.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []


def discover(kind: str, text: str) -> list[Path]:
    """把一个用户填写的路径展开成「具体的库」。

    Args:
        kind: ``"polydb"``（库 = 目录）或 ``"xindb"``（库 = 文件）。
        text: 用户填写的路径；可以是库本体，也可以是装着若干库的目录。

    Returns:
        具体的库路径列表（可能为空：路径不存在 / 格不对）。
        **不做可用性判断**，是否可用由各自的 probe 决定。
    """
    text = str(text or "").strip()
    if not text:
        return []
    path = Path(text)
    suffix = POLYDB_SUFFIX if kind == "polydb" else XINDB_SUFFIX
    if kind == "polydb":
        if path.is_dir() and path.name.lower().endswith(suffix):
            return [path]
        if path.is_dir():
            # 「装着若干 .polyDB 的目录」：向下扫一层即可
            # （PolyXRD 的发布包解压后就是这种布局）
            found = [p for p in _children(path)
                     if p.is_dir() and p.name.lower().endswith(suffix)]
            if found:
                return found
            # 目录名没带后缀但内容像库（meta.json + index.sqlite）：仍交给 probe 判
            return [path]
        return [path]

    if path.is_file():
        return [path]
    if path.is_dir():
        found = [p for p in _children(path)
                 if p.is_file() and p.name.lower().endswith(suffix)]
        if found:
            return found
        # 兼容旧命名：目录里躺着 *.db / *.sqlite 的 xinDB（由 probe 判 v3 结构）
        legacy = [p for p in _children(path)
                  if p.is_file() and p.suffix.lower() in (".db", ".sqlite")]
        return legacy
    return [path]


def all_libraries(kind: str, texts: Iterable[str]) -> list[Path]:
    """把多条配置项展开并去重成最终库列表。"""
    out: list[Path] = []
    for text in texts or ():
        out.extend(discover(kind, text))
    return dedupe(out)


# ----------------------------------------------------------------------
# CIF 相对路径解析
# ----------------------------------------------------------------------
def _read_meta(polydb_dir: Path) -> dict:
    try:
        with open(polydb_dir / "meta.json", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def cif_base_dirs(polydb_dir: Path, configured_root: str = "",
                  meta: Optional[dict] = None) -> list[Path]:
    """给出解析 ``cif_rel`` 的候选根目录（存在才返回，顺序即优先级）。

    优先级（高 → 低）：
    1. 设置里显式配置的「数据根目录」；
    2. 环境变量 ``XRD_DATA_ROOT``（PolyXRD-DataBase 约定的换盘方式）；
    3. 库自述 ``meta.source.root``（建库机器上的路径，可能已过期，仅作兜底）；
    4. polyDB 目录本身与其父目录。

    每个根再展开 COD 家族子目录（``COD`` / ``PCOD`` / ``TCOD``）、
    ``meta.source.lib`` 以及 ``inorg_cif/<lib>`` —— 因为 ``sync-COD`` 布局下
    实际 CIF 位于 ``<root>/COD/1/00/00/*.cif``，而库自述的 root 常常是
    建库时的 ``PolyXRD-DataBase/COD``。
    """
    meta = meta if meta is not None else _read_meta(polydb_dir)
    source = meta.get("source") or {}
    source_root = str(source.get("root") or "").strip()
    source_lib = str(source.get("lib") or "").strip()

    bases: list[Path] = []
    for text in (configured_root, os.environ.get(DATA_ROOT_ENV, ""), source_root):
        text = str(text or "").strip()
        if text:
            bases.append(Path(text))
    bases.append(polydb_dir)
    bases.append(polydb_dir.parent)

    out: list[Path] = []
    for base in bases:
        variants = [base]
        for lib in COD_FAMILY:
            variants.append(base / lib)
            variants.append(base / "inorg_cif" / lib)
        if source_lib:
            variants.append(base / source_lib)
            variants.append(base / "inorg_cif" / source_lib)
        out.extend(variants)
    # 只保留真实存在的目录，避免每次解析都白跑 stat
    return [p for p in dedupe(out) if p.is_dir()]


def resolve_relative(cif_rel: str, base_dirs: Iterable[Path]) -> Optional[Path]:
    """按候选根解析一个相对 CIF 路径；找到第一个存在的文件即返回。"""
    rel = str(cif_rel or "").strip().replace("\\", "/")
    if not rel:
        return None
    raw = Path(rel)
    if raw.is_absolute():
        return raw if raw.is_file() else None
    for base in base_dirs:
        full = base / rel
        try:
            if full.is_file():
                return full
        except OSError:
            continue
    return None


def read_cif_text(path: Path) -> str:
    """读取 CIF 文本（容错编码）；不像 CIF 时返回空串。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if "data_" in text else ""


__all__ = [
    "COD_FAMILY",
    "DATA_ROOT_ENV",
    "POLYDB_SUFFIX",
    "XINDB_SUFFIX",
    "all_libraries",
    "cif_base_dirs",
    "dedupe",
    "discover",
    "read_cif_text",
    "resolve_relative",
]
