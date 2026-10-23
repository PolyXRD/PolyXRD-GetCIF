"""polyDB 外挂库适配器（v1.4.0）：兼容 PolyXRD v4 的 polyDB v1，支持多库挂载。

polyDB 是 PolyXRD 自有的外挂物相库格式（规范见 PolyXRD
``docs/外挂库格式规范-polyDB-v1.md``）：**目录容器** —— ``meta.json`` +
``index.sqlite``（``entries`` 表）+ 列存二进制数组段（峰 / 位点 / 元素位图）。

本工具是 CIF 检索器，只需要 ``index.sqlite`` 的标量字段与 ``cif_rel``
（原始 CIF 相对路径），因此**不加载数组段、不需要 numpy**，标准版同样可用。

``entries`` 表列（``tools/build_polydb.py`` 20261021 版）：eid, formula,
formula_red, mineral, space_group, sg_number, elements, a..gamma, volume,
density, z, n_peaks, tier, dup_group, cif_rel, src_mtime, row_idx（另有 FTS5
``entries_fts``）。本适配器只取标量列 —— 新增列（``tier`` / ``dup_group`` /
``src_mtime``）不参与检索，对早期 v1 库同样可用。

**多库（v1.4.0）**：PolyXRD v4.0.0 起外挂库改为列表式挂载，同一格式可挂多份
（COD-Inorg 与 COD-Full 是两份互不包含的库）。本适配器把配置里的每条路径展开
成具体的 ``.polyDB`` 目录（库本体，或装着若干 ``.polyDB`` 的父目录），逐个检索
后合并；每条候选记住自己所属的库，取 CIF 时按**该库**的 ``meta.json`` 解析数据
根，不会串库。
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.adapters.locallib import (
    all_libraries,
    cif_base_dirs as _cif_base_dirs,
    read_cif_text,
    resolve_relative,
)
from getcif.core import config
from getcif.core.formula import normalize_cod_formula, spaced_hm_symbol, split_elements
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula
from getcif.adapters.cod_local import _SYSTEM_SG_RANGES, normalize_system

#: 上游支持的 schema 版本（PolyXRD ``services/polydb.probe`` 要求 == 1）
SUPPORTED_SCHEMA = 1

#: 数组段（缺失不影响「元数据检索」，只在界面提示"库不完整"）
_ARRAY_SECTIONS = ("peaks_d.f32", "peaks_i.u16", "bins.u8", "elem.u8",
                   "sites.bin", "sites_off.i64")


@dataclass
class PolyDbLibrary:
    """一个已挂载的 polyDB（= 设置界面上的一行）。"""

    path: Path
    ok: bool = False
    reason: str = ""
    variant: str = ""
    phases: int = 0
    peaks: int = 0
    sites: int = 0
    k: int = 0
    total_bytes: int = 0
    build_time: str = ""
    source_lib: str = ""
    source_root: str = ""
    missing_sections: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """展示名：变体优先（``cod-inorg`` / ``cod-full``），否则目录名。"""
        return self.variant or self.path.name

    def summary(self) -> str:
        """一行概况（界面列表右侧 / 工具提示用）。"""
        if not self.ok:
            return "不可用：%s" % (self.reason or "未知原因")
        parts: list[str] = []
        if self.phases:
            parts.append(f"{self.phases:,} 相")
        if self.peaks:
            parts.append(f"{self.peaks:,} 峰")
        if self.total_bytes:
            parts.append(f"{self.total_bytes / 1048576:.0f} MB")
        if self.build_time:
            parts.append("构建 " + self.build_time[:10])
        return " · ".join(parts)

    def detail(self) -> str:
        """多行明细（工具提示用）。"""
        lines = [f"路径：{self.path}"]
        if self.ok:
            lines.append(f"变体：{self.variant or '-'}　数据库：{self.source_lib or '-'}")
            lines.append(
                f"物相：{self.phases:,}　峰：{self.peaks:,}　每相保留 K={self.k}"
            )
            if self.build_time:
                lines.append(f"建库时间：{self.build_time}")
            if self.source_root:
                lines.append(f"建库数据根：{self.source_root}")
            if self.missing_sections:
                lines.append("缺少数组段（仅元数据检索可用）："
                             + ", ".join(self.missing_sections))
        else:
            lines.append("状态：" + self.summary())
        return "\n".join(lines)


def probe_polydb(db_path: str | Path) -> tuple[bool, str]:
    """轻量判别：该目录是不是可用的 polyDB（不读数组段）。

    Returns:
        ``(ok, reason)``；失败原因与 PolyXRD ``polydb.probe`` 对齐
        （``file_not_found`` / ``not_a_directory`` / ``missing:meta.json`` /
        ``bad_meta`` / ``bad_format:...`` / ``unsupported_schema:...`` /
        ``missing:index.sqlite`` / ``missing_table:entries``）。

    与上游的两点差异都朝向**更宽容**（本工具只用标量元数据）：
    * 不强制要求数组段存在；
    * ``meta.sections`` 写了 ``bytes`` 才校验大小（写了就必须对得上，
      用来挡住拷贝中断的半成品）。
    """
    p = Path(db_path)
    if not p.exists():
        return False, "file_not_found"
    if not p.is_dir():
        return False, "not_a_directory"
    if not (p / "meta.json").is_file():
        return False, "missing:meta.json"
    try:
        with open(p / "meta.json", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return False, "bad_meta"
    if not isinstance(meta, dict):
        return False, "bad_meta"
    if meta.get("format") != "polyDB":
        return False, "bad_format:%s" % meta.get("format")
    try:
        schema = int(meta.get("schema_version", SUPPORTED_SCHEMA))
    except (TypeError, ValueError):
        return False, "bad_meta"
    if schema != SUPPORTED_SCHEMA:
        return False, "unsupported_schema:%s" % schema
    if not (p / "index.sqlite").is_file():
        return False, "missing:index.sqlite"
    try:
        conn = sqlite3.connect(f"file:{p / 'index.sqlite'}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
            ).fetchone()
            if row is None:
                return False, "missing_table:entries"
            cols = {r[1] for r in conn.execute("PRAGMA table_info(entries)")}
            if "cif_rel" not in cols:
                # 没有 cif_rel 就取不回 CIF，本工具的用途不成立
                return False, "missing_column:cif_rel"
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, "open_failed:%s" % exc
    sections = meta.get("sections") or {}
    if isinstance(sections, dict):
        for name, sec in sections.items():
            if not isinstance(sec, dict) or "bytes" not in sec:
                continue
            f = p / name
            if not f.exists():
                return False, "missing:" + name
            try:
                if int(sec.get("bytes", -1)) != f.stat().st_size:
                    return False, "size_mismatch:" + name
            except (OSError, TypeError, ValueError):
                return False, "bad_meta"
    return True, ""


def describe_library(polydb_dir: str | Path) -> PolyDbLibrary:
    """探测并读出库概况（界面展示 / 体检用；失败也返回对象，``ok=False``）。"""
    p = Path(polydb_dir)
    lib = PolyDbLibrary(path=p)
    ok, reason = probe_polydb(p)
    lib.ok, lib.reason = ok, reason
    if not ok:
        return lib
    try:
        with open(p / "meta.json", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    lib.variant = str(meta.get("variant") or "")
    counts = meta.get("counts") or {}
    if isinstance(counts, dict):
        for key, attr in (("phases", "phases"), ("peaks", "peaks"),
                          ("sites", "sites"), ("k", "k")):
            try:
                setattr(lib, attr, int(counts.get(key) or 0))
            except (TypeError, ValueError):
                pass
    try:
        lib.total_bytes = int(meta.get("total_bytes") or 0)
    except (TypeError, ValueError):
        pass
    build = meta.get("build") or {}
    if isinstance(build, dict):
        lib.build_time = str(build.get("started_at") or "")
    source = meta.get("source") or {}
    if isinstance(source, dict):
        lib.source_lib = str(source.get("lib") or "")
        lib.source_root = str(source.get("root") or "")
    sections = meta.get("sections") or {}
    lib.missing_sections = [name for name in _ARRAY_SECTIONS
                            if not isinstance(sections, dict)
                            or name not in sections or not (p / name).exists()]
    return lib


class PolyDbAdapter(BaseAdapter):
    """polyDB 外挂库检索（只读；CIF 经 cif_rel 相对数据根目录解析）。"""

    name = "polydb"
    display_key = "polyDB 外挂库"

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)

    # ---- 可用性 ----
    def configured_paths(self) -> list[str]:
        return config.polydb_paths()

    def libraries(self) -> list[PolyDbLibrary]:
        """当前配置展开后的全部 polyDB（含不可用的，界面要显示原因）。"""
        return [describe_library(p)
                for p in all_libraries("polydb", self.configured_paths())]

    def usable_libraries(self) -> list[PolyDbLibrary]:
        return [lib for lib in self.libraries() if lib.ok]

    def is_available(self) -> bool:
        return config.source_enabled("polydb") and bool(self.usable_libraries())

    def availability_reason(self) -> str:
        if not config.source_enabled("polydb"):
            return "已在设置中关闭"
        if not self.configured_paths():
            return "未配置 polyDB 目录"
        libs = self.libraries()
        if not libs:
            return "配置的路径不存在"
        usable = [lib for lib in libs if lib.ok]
        if not usable:
            return "没有可用的 polyDB（%s）" % (libs[0].reason or "未知原因")
        if len(usable) < len(libs):
            return "已挂载 %d 个库（%d 个不可用）" % (len(usable), len(libs) - len(usable))
        return ""

    # ---- 检索 ----
    def search(self, query: SearchQuery) -> list[Candidate]:
        if not config.source_enabled("polydb"):
            raise AdapterError("已在设置中关闭 polyDB")
        if not self.configured_paths():
            raise AdapterError("未配置 polyDB 目录")
        libs = [lib for lib in self.libraries() if lib.ok]
        if not libs:
            raise AdapterError("polyDB 目录不可用：%s" % self.availability_reason())

        results: list[Candidate] = []
        seen: set[str] = set()
        errors: list[str] = []
        for lib in libs:
            try:
                rows = self._query_library(lib, query)
            except AdapterError as exc:
                errors.append(f"{lib.label}: {exc.reason}")
                continue
            for row in rows:
                candidate = self._row_to_candidate(row, lib)
                if candidate.candidate_id in seen:
                    continue
                seen.add(candidate.candidate_id)
                results.append(candidate)
        if errors and not results:
            raise AdapterError("；".join(errors[:3]))
        # 多库合并后重排，避免"哪个库先挂就排前面"造成的顺序抖动
        results.sort(key=lambda c: (c.formula, c.source_id))
        return results

    def _query_library(self, lib: PolyDbLibrary, query: SearchQuery) -> list[dict]:
        try:
            conn = sqlite3.connect(f"file:{lib.path / 'index.sqlite'}?mode=ro",
                                   uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise AdapterError(f"索引打开失败：{exc}") from exc
        try:
            sql, args = self._build_sql(query)
            return [dict(row) for row in conn.execute(sql, args)]
        except sqlite3.Error as exc:
            raise AdapterError(f"检索失败：{exc}") from exc
        finally:
            conn.close()

    def _build_sql(self, query: SearchQuery) -> tuple[str, list]:
        """构造单库查询（所有条件 AND；数值范围沿用 v1.3 的容差口径）。"""
        clauses: list[str] = []
        args: list[object] = []

        if query.formula:
            norm = normalize_cod_formula(query.formula)  # "O2 Si"
            compact = norm.replace(" ", "")
            clauses.append("(formula_red = ? OR REPLACE(formula_red, ' ', '') = ? "
                           "OR REPLACE(formula, ' ', '') = ?)")
            args += [norm, compact, compact]
        if query.elements:
            for element in split_elements(query.elements)[:8]:
                clauses.append(
                    "((',' || REPLACE(elements, ' ', ',')) || ',') LIKE ?"
                )
                args.append(f"%,{element},%")
        if query.name:
            clauses.append("mineral LIKE ?")
            args.append(f"%{query.name.strip()}%")
        if query.space_group:
            text = query.space_group.strip()
            if text.isdigit():
                clauses.append("sg_number = ?")
                args.append(int(text))
            else:
                spaced = spaced_hm_symbol(text)
                clauses.append("(space_group = ? OR space_group = ? OR space_group = ?)")
                args += [text, spaced, text.replace(" ", "")]
        system = normalize_system(query.crystal_system)
        if system:
            lo, hi = _SYSTEM_SG_RANGES[system]
            clauses.append("sg_number BETWEEN ? AND ?")
            args += [lo, hi]

        for key in ("a", "b", "c"):
            value = getattr(query, key)
            if value is not None:
                clauses.append(f"{key} BETWEEN ? AND ?")
                args += [value - 0.1, value + 0.1]
        for key in ("alpha", "beta", "gamma"):
            value = getattr(query, key)
            if value is not None:
                clauses.append(f"{key} BETWEEN ? AND ?")
                args += [value - 0.5, value + 0.5]

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (f"SELECT eid, formula, formula_red, mineral, space_group, sg_number, "
               f"elements, a, b, c, alpha, beta, gamma, volume, density, cif_rel "
               f"FROM entries {where} ORDER BY formula_red, eid LIMIT ?")
        args.append(max(1, query.limit))
        return sql, args

    def _row_to_candidate(self, row: dict, lib: PolyDbLibrary) -> Candidate:
        eid = int(row.get("eid") or 0)
        formula = str(row.get("formula") or "").strip()
        lattice = LatticeParams(
            a=float(row.get("a") or 0), b=float(row.get("b") or 0),
            c=float(row.get("c") or 0),
            alpha=float(row.get("alpha") or 0), beta=float(row.get("beta") or 0),
            gamma=float(row.get("gamma") or 0),
            volume=float(row.get("volume") or 0),
        )
        elements_text = str(row.get("elements") or "")
        elements = {e for e in re.split(r"[,\s]+", elements_text) if e}
        if not elements:
            elements = elements_from_formula(formula)
        mineral = str(row.get("mineral") or "").strip()
        if mineral in ("?", "None"):
            mineral = ""
        sg_number = int(row.get("sg_number") or 0)
        provenance = f"polyDB {eid}"
        if mineral:
            provenance += f" · {mineral}"
        provenance += f" · {lib.label}"
        return Candidate(
            source=self.name,
            source_id=str(eid),
            formula=formula,
            mineral_name=mineral,
            space_group=str(row.get("space_group") or "") or (str(sg_number) if sg_number else ""),
            crystal_system="",
            lattice=lattice,
            elements=elements,
            provenance=provenance,
            extra={
                "_cif_rel": str(row.get("cif_rel") or ""),
                "_lib_path": str(lib.path),
                "_lib_label": lib.label,
            },
        )

    # ---- CIF 下载（按 cif_rel 解析原始文件）----
    def cif_base_dirs(self, lib_path: str = "") -> list[Path]:
        """解析 cif_rel 的候选数据根（取回与界面诊断共用）。"""
        text = str(lib_path or "").strip()
        if not text:
            libs = self.usable_libraries()
            text = str(libs[0].path) if libs else ""
        if not text:
            return []
        return _cif_base_dirs(Path(text), config.cod_local_root())

    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        cif_rel = str(candidate.extra.get("_cif_rel") or "").strip()
        if not cif_rel:
            return None
        bases = self.cif_base_dirs(str(candidate.extra.get("_lib_path") or ""))
        found = resolve_relative(cif_rel, bases)
        if found is not None:
            text = read_cif_text(found)
            if text:
                candidate.cif_content = text
                return text
        # 取不回时给出可操作提示：数据根没配好是最常见原因
        if bases:
            hint = "（已查找 %d 个候选根，首个为 %s）" % (len(bases), bases[0])
        else:
            hint = ("（没有任何候选数据根：请在设置里指定「数据根目录」，"
                    "或设置环境变量 XRD_DATA_ROOT）")
        raise AdapterError(f"相对路径 {cif_rel} 未能解析到 CIF 文件{hint}")


__all__ = [
    "PolyDbAdapter",
    "PolyDbLibrary",
    "SUPPORTED_SCHEMA",
    "describe_library",
    "probe_polydb",
]
