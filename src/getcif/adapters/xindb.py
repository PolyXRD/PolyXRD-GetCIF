"""xinDB v3 库适配器（v1.3.0）：兼容 XinMatch 的列存参考数据库 ``.xinDB``。

xinDB v3 是 XinMatch 的外挂参考库格式（``xinmatch/core/db/schema_v3.py``）：
**单文件 SQLite**，``entries`` 表存物相标量元数据，``peak_chunks`` 表以
列存 BLOB 存峰数据（``top_d`` / ``top_i`` 预筛矩阵 + ``all_d`` / ``all_i``
CSR 全峰），``meta`` 表自描述（``schema_version=3``）。

本工具只检索标量元数据（化学式 / 元素 / 名称 / 空间群 / 晶系 / 晶胞），
**不读峰数据段**；xinDB 不含 CIF 原文，故不提供 CIF 下载（预览时会给出
明确提示，引导改用 COD 联网检索或其他来源）。

``entries`` 表列：entry_id, formula, space_group, crystal_system,
mineral_name, elements, elem_mask, a..gamma, volume, density, year,
author, journal, quality, n_peaks, peak_off, peak_n, tier。
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.core import config
from getcif.core.formula import normalize_cod_formula, spaced_hm_symbol, split_elements
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula
from getcif.adapters.cod_local import normalize_system

#: xinDB v3 的 schema 版本（``meta.schema_version``）
_SCHEMA_VERSION = 3
#: v3 必需的表（``schema_v3.REQUIRED_TABLES``）
_REQUIRED_TABLES = ("meta", "entries", "peak_chunks")


def probe_xindb(db_path: str | Path) -> tuple[bool, str]:
    """轻量判别：该文件是不是可用的 xinDB v3（只读 meta，不碰峰数据段）。

    Returns:
        ``(ok, reason)``；失败原因为机器可读短标记（``file_not_found`` /
        ``not_a_file`` / ``not_sqlite`` / ``missing_table:entries`` /
        ``unsupported_schema:...`` 等）。
    """
    p = Path(db_path)
    if not p.exists():
        return False, "file_not_found"
    if not p.is_file():
        return False, "not_a_file"
    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        return False, "open_failed:%s" % exc
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for table in _REQUIRED_TABLES:
            if table not in names:
                return False, "missing_table:" + table
        schema = 0
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if row is not None:
                schema = int(row[0])
        except (sqlite3.Error, TypeError, ValueError):
            schema = 0
        if schema and schema != _SCHEMA_VERSION:
            return False, "unsupported_schema:%s" % schema
    except sqlite3.Error as exc:
        return False, "open_failed:%s" % exc
    finally:
        conn.close()
    return True, ""


class XinDbAdapter(BaseAdapter):
    """xinDB v3 库检索（只读；库内不含 CIF 原文，不提供下载）。"""

    name = "xindb"
    display_key = "xinDB 库"

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)

    # ---- 可用性 ----
    def db_path(self) -> Optional[Path]:
        text = config.xindb_path()
        if not text:
            return None
        path = Path(text)
        return path if path.is_file() else None

    def is_available(self) -> bool:
        return config.source_enabled("xindb") and self.db_path() is not None

    def availability_reason(self) -> str:
        if not config.source_enabled("xindb"):
            return "已在设置中关闭"
        if not config.xindb_path():
            return "未配置 xinDB 库文件"
        ok, reason = probe_xindb(config.xindb_path())
        if not ok:
            return "不是可用的 xinDB 库（%s）" % (reason or "未知原因")
        return ""

    # ---- 检索 ----
    def search(self, query: SearchQuery) -> list[Candidate]:
        text = config.xindb_path()
        if not text:
            raise AdapterError("未配置 xinDB 库文件")
        ok, reason = probe_xindb(text)
        if not ok:
            raise AdapterError("xinDB 库不可用（%s）" % (reason or "未知原因"))
        try:
            conn = sqlite3.connect(f"file:{text}?mode=ro", uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise AdapterError(f"xinDB 打开失败：{exc}") from exc
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
            # xinDB 无 formula_red 列：按去空格等价 + 子串兜底
            clauses.append("(REPLACE(formula, ' ', '') = ? OR formula LIKE ?)")
            args += [compact, f"%{compact}%"]
        if query.elements:
            for element in split_elements(query.elements)[:8]:
                clauses.append(
                    "((',' || REPLACE(elements, ' ', ',')) || ',') LIKE ?"
                )
                args.append(f"%,{element},%")
        if query.name:
            clauses.append("mineral_name LIKE ?")
            args.append(f"%{query.name.strip()}%")
        if query.space_group:
            text = query.space_group.strip()
            if text.isdigit():
                # xinDB 无 sg_number 列：数字编号按常见 H-M 尾部数字无法反查，
                # 退化为 space_group 文本包含匹配（如 "154" 不适用，仅兜底）。
                clauses.append("space_group LIKE ?")
                args.append(f"%{text}%")
            else:
                spaced = spaced_hm_symbol(text)
                clauses.append("(space_group = ? OR space_group = ? OR space_group = ?)")
                args += [text, spaced, text.replace(" ", "")]
        system = normalize_system(query.crystal_system)
        if system:
            clauses.append("crystal_system = ?")
            args.append(system)

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
        sql = (f"SELECT entry_id, formula, space_group, crystal_system, mineral_name, "
               f"elements, a, b, c, alpha, beta, gamma, volume, density "
               f"FROM entries {where} ORDER BY formula, entry_id LIMIT ?")
        args.append(max(1, query.limit))
        try:
            return list(conn.execute(sql, args))
        except sqlite3.Error as exc:
            raise AdapterError(f"xinDB 检索失败：{exc}") from exc

    def _row_to_candidate(self, row: dict) -> Candidate:
        entry_id = str(row.get("entry_id") or "").strip()
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
        mineral = str(row.get("mineral_name") or "").strip()
        provenance = f"xinDB {entry_id}"
        if mineral:
            provenance += f" · {mineral}"
        return Candidate(
            source=self.name,
            source_id=entry_id,
            formula=formula,
            mineral_name=mineral,
            space_group=str(row.get("space_group") or ""),
            crystal_system=str(row.get("crystal_system") or ""),
            lattice=lattice,
            elements=elements,
            provenance=provenance,
            extra={"_no_cif": True},
        )

    # ---- CIF 下载：xinDB 不含 CIF 原文 ----
    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        raise AdapterError("xinDB 库仅含检索索引与峰数据，不包含 CIF 原文；"
                           "请通过 COD 联网检索或其他来源获取该 CIF")


__all__ = ["XinDbAdapter", "probe_xindb"]
