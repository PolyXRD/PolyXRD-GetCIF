"""polyDB 外挂库适配器（v1.3.0）：兼容 PolyXRD v4 的 polyDB v1 目录容器。

polyDB 是 PolyXRD 自有的外挂物相库格式（规范见 PolyXRD
``docs/外挂库格式规范-polyDB-v1.md``）：**目录容器** —— ``meta.json`` +
``index.sqlite``（``entries`` 表）+ 列存二进制数组段（峰 / 位点 / 元素位图）。

本工具是 CIF 检索器，只需要 ``index.sqlite`` 的标量字段与 ``cif_rel``
（原始 CIF 相对路径），因此**不加载数组段、不需要 numpy**，标准版同样可用。

``entries`` 表列（``tools/build_polydb.py``）：eid, formula, formula_red,
mineral, space_group, sg_number, elements, a..gamma, volume, density, z,
n_peaks, cif_rel, row_idx。CIF 内容按 ``cif_rel`` 相对「COD 数据根目录」
（与 cod_index.sqlite 的 ``file`` 列同一约定）解析。
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.core import config
from getcif.core.formula import normalize_cod_formula, spaced_hm_symbol, split_elements
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula
from getcif.adapters.cod_local import _SYSTEM_SG_RANGES, normalize_system


def probe_polydb(db_path: str | Path) -> tuple[bool, str]:
    """轻量判别：该目录是不是可用的 polyDB（不读数组段）。

    Returns:
        ``(ok, reason)``；失败原因与 PolyXRD ``polydb.probe`` 对齐
        （``file_not_found`` / ``not_a_directory`` / ``missing:meta.json`` /
        ``bad_meta`` / ``bad_format:...`` / ``missing:index.sqlite`` /
        ``missing_table:entries``）。
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
    if meta.get("format") != "polyDB":
        return False, "bad_format:%s" % meta.get("format")
    if not (p / "index.sqlite").is_file():
        return False, "missing:index.sqlite"
    try:
        conn = sqlite3.connect(f"file:{p / 'index.sqlite'}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, "open_failed:%s" % exc
    if row is None:
        return False, "missing_table:entries"
    return True, ""


class PolyDbAdapter(BaseAdapter):
    """polyDB 外挂库检索（只读；CIF 经 cif_rel 相对数据根目录解析）。"""

    name = "polydb"
    display_key = "polyDB 外挂库"

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)
        self._probe_cache: Optional[tuple[bool, str]] = None

    # ---- 可用性 ----
    def db_dir(self) -> Optional[Path]:
        text = config.polydb_path()
        if not text:
            return None
        path = Path(text)
        return path if path.is_dir() else None

    def is_available(self) -> bool:
        return config.source_enabled("polydb") and self.db_dir() is not None

    def availability_reason(self) -> str:
        if not config.source_enabled("polydb"):
            return "已在设置中关闭"
        if not config.polydb_path():
            return "未配置 polyDB 目录"
        ok, reason = probe_polydb(config.polydb_path())
        if not ok:
            return "不是可用的 polyDB 目录（%s）" % (reason or "未知原因")
        return ""

    # ---- 检索 ----
    def search(self, query: SearchQuery) -> list[Candidate]:
        text = config.polydb_path()
        if not text:
            raise AdapterError("未配置 polyDB 目录")
        ok, reason = probe_polydb(text)
        if not ok:
            raise AdapterError("polyDB 目录不可用（%s）" % (reason or "未知原因"))
        db_dir = Path(text)
        try:
            conn = sqlite3.connect(f"file:{db_dir / 'index.sqlite'}?mode=ro",
                                   uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise AdapterError(f"polyDB 索引打开失败：{exc}") from exc
        try:
            rows = self._query(conn, query)
            return [self._row_to_candidate(dict(row)) for row in rows]
        finally:
            conn.close()

    def _query(self, conn: sqlite3.Connection, query: SearchQuery) -> list[sqlite3.Row]:
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
        try:
            return list(conn.execute(sql, args))
        except sqlite3.Error as exc:
            raise AdapterError(f"polyDB 检索失败：{exc}") from exc

    def _row_to_candidate(self, row: dict) -> Candidate:
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
        sg_number = int(row.get("sg_number") or 0)
        provenance = f"polyDB {eid}"
        if mineral:
            provenance += f" · {mineral}"
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
            extra={"_cif_rel": str(row.get("cif_rel") or "")},
        )

    # ---- CIF 下载（按 cif_rel 解析原始文件）----
    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        cif_rel = str(candidate.extra.get("_cif_rel") or "").strip()
        if not cif_rel:
            return None
        db_dir = self.db_dir()
        bases = [Path(config.cod_local_root())] if config.cod_local_root() else []
        if db_dir is not None:
            bases += [db_dir, db_dir.parent]
        p = Path(cif_rel)
        for base in bases:
            full = p if p.is_absolute() else base / p
            try:
                if full.is_file():
                    text = full.read_text(encoding="utf-8", errors="replace")
                    if "data_" in text:
                        candidate.cif_content = text
                        return text
            except OSError:
                continue
        return None


__all__ = ["PolyDbAdapter", "probe_polydb"]
