"""COD 本地库适配器：查询 SQLite 检索索引（兼容 PolyXRD 全库索引 cod_index.sqlite）。

索引表 ``cod_entries``（cod_id, file, mineral_name, formula, formula_red,
elements, space_group, space_group_number, a..gamma, volume, cif_gz …）。
CIF 内容优先取 ``cif_gz``（gzip blob），否则按 ``file`` 相对 ``cod_root`` 解析。
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional

from getcif.adapters.base import AdapterError, BaseAdapter, decompress_cif_blob
from getcif.core import config
from getcif.core.formula import normalize_cod_formula, spaced_hm_symbol
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula

#: 晶系 → 空间群编号范围（H-M 国际表 1..230）
_SYSTEM_SG_RANGES: dict[str, tuple[int, int]] = {
    "triclinic": (1, 2),
    "monoclinic": (3, 15),
    "orthorhombic": (16, 74),
    "tetragonal": (75, 142),
    "trigonal": (143, 167),
    "hexagonal": (168, 194),
    "cubic": (195, 230),
}

#: 晶系各语言关键词 → 规范英文名（用户可输入中文/英文/日文）
_SYSTEM_ALIASES: dict[str, str] = {
    "三斜": "triclinic", "triclinic": "triclinic", "三斜晶系": "triclinic",
    "単斜": "monoclinic", "单斜": "monoclinic", "monoclinic": "monoclinic",
    "斜方": "orthorhombic", "正交": "orthorhombic", "orthorhombic": "orthorhombic",
    "四方": "tetragonal", "正方": "tetragonal", "tetragonal": "tetragonal",
    "三方": "trigonal", "菱方": "trigonal", "trigonal": "trigonal",
    "六方": "hexagonal", "六角": "hexagonal", "hexagonal": "hexagonal",
    "立方": "cubic", "等轴": "cubic", "cubic": "cubic",
}


def normalize_system(text: str) -> str:
    key = str(text or "").strip().lower()
    return _SYSTEM_ALIASES.get(key, "")


class CodLocalAdapter(BaseAdapter):
    """COD 本地索引检索（离线优先，只读）。"""

    name = "cod_local"
    display_key = "COD 本地库"

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)
        self._db_error = ""

    # ---- 可用性 ----
    def db_path(self) -> Optional[Path]:
        text = config.cod_local_db()
        if not text:
            return None
        path = Path(text)
        return path if path.is_file() else None

    def is_available(self) -> bool:
        return config.source_enabled("local") and self.db_path() is not None

    def availability_reason(self) -> str:
        if not config.source_enabled("local"):
            return "已在设置中关闭"
        if not config.cod_local_db():
            return "未配置检索索引路径"
        if self.db_path() is None:
            return "索引文件不存在"
        return ""

    # ---- 检索 ----
    def search(self, query: SearchQuery) -> list[Candidate]:
        path = self.db_path()
        if path is None:
            raise AdapterError(self.availability_reason() or "本地库不可用")
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise AdapterError(f"本地索引打开失败：{exc}") from exc
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
            from getcif.core.formula import split_elements

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
                clauses.append("space_group_number = ?")
                args.append(int(text))
            else:
                spaced = spaced_hm_symbol(text)
                clauses.append("(space_group = ? OR space_group = ? OR space_group = ?)")
                args += [text, spaced, text.replace(" ", "")]
        system = normalize_system(query.crystal_system)
        if system:
            lo, hi = _SYSTEM_SG_RANGES[system]
            clauses.append("space_group_number BETWEEN ? AND ?")
            args += [lo, hi]

        for key, column in (("a", "a"), ("b", "b"), ("c", "c")):
            value = getattr(query, key)
            if value is not None:
                clauses.append(f"{column} BETWEEN ? AND ?")
                args += [value - 0.1, value + 0.1]
        for key, column in (("alpha", "alpha"), ("beta", "beta"), ("gamma", "gamma")):
            value = getattr(query, key)
            if value is not None:
                clauses.append(f"{column} BETWEEN ? AND ?")
                args += [value - 0.5, value + 0.5]

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (f"SELECT * FROM cod_entries {where} "
               f"ORDER BY formula_red, cod_id LIMIT ?")
        args.append(max(1, query.limit))
        try:
            return list(conn.execute(sql, args))
        except sqlite3.Error as exc:
            raise AdapterError(f"本地检索失败：{exc}") from exc

    def _row_to_candidate(self, row: dict) -> Candidate:
        cod_id = int(row.get("cod_id") or 0)
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
        sg_number = int(row.get("space_group_number") or 0)
        extra = {"_local_row": row}
        provenance = f"COD {cod_id}（本地）"
        if mineral:
            provenance += f" · {mineral}"
        return Candidate(
            source=self.name,
            source_id=str(cod_id),
            formula=formula,
            mineral_name=mineral,
            space_group=str(row.get("space_group") or "") or (str(sg_number) if sg_number else ""),
            crystal_system="",
            lattice=lattice,
            elements=elements,
            provenance=provenance,
            extra=extra,
        )

    # ---- CIF 下载（本地取回）----
    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        row = candidate.extra.get("_local_row")
        if row is None:
            return None
        # 1) cif_gz blob
        blob = row.get("cif_gz")
        if blob:
            try:
                text = decompress_cif_blob(bytes(blob))
                if "data_" in text:
                    candidate.cif_content = text
                    return text
            except Exception:  # noqa: BLE001
                pass
        # 2) file 路径（相对 cod_root / 索引目录）
        file_path = str(row.get("file") or "").strip()
        if file_path:
            bases = [Path(config.cod_local_root())] if config.cod_local_root() else []
            db = self.db_path()
            if db is not None:
                bases += [db.parent, db.parent.parent]
            p = Path(file_path)
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
