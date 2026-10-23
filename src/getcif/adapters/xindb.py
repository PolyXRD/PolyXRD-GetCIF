"""xinDB v3 库适配器（v1.4.0）：兼容 XinMatch 列存参考库 ``.xinDB``，支持多库挂载。

xinDB v3 是 XinMatch 的外挂参考库格式（``xinmatch/core/db/schema_v3.py``）：
**单文件 SQLite**，``entries`` 表存物相标量元数据，``peak_chunks`` 表以列存
BLOB 存峰数据（``top_d`` / ``top_i`` 预筛矩阵 + ``all_d`` / ``all_i`` CSR 全峰），
``meta`` 表自描述（``schema_version=3``）。

本工具只检索标量元数据（化学式 / 元素 / 名称 / 空间群 / 晶系 / 晶胞），
**不读峰数据段**；xinDB 不含 CIF 原文，故不提供 CIF 下载（预览时给出明确提示，
引导改用 COD 联网检索或其他来源）。

``entries`` 表列：entry_id, formula, space_group, crystal_system,
mineral_name, elements, elem_mask, a..gamma, volume, density, year,
author, journal, quality, n_peaks, peak_off, peak_n, tier。

**多库（v1.4.0）**：XinMatch v2.0.0 把 3COD 拆成 COD/PCOD/TCOD 三份库并支持
列表式挂载，``meta`` 新增 ``library_kind`` / ``data_date`` / ``top_k`` 等自述键。
本适配器把配置里的每条路径展开成具体的 ``.xinDB``（文件本体，或装着若干
``.xinDB`` 的目录），逐个检索后合并，候选的 ``entry_id`` 已带库前缀
（``96-*`` 等）不会互相冲突。
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.adapters.locallib import all_libraries
from getcif.core import config
from getcif.core.formula import normalize_cod_formula, spaced_hm_symbol, split_elements
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula
from getcif.adapters.cod_local import normalize_system

#: xinDB v3 的 schema 版本（``meta.schema_version``）
SCHEMA_VERSION = 3
#: v3 必需的表（``schema_v3.REQUIRED_TABLES``）
_REQUIRED_TABLES = ("meta", "entries", "peak_chunks")
#: 旧版 XinMatch 库（v1/v2 schema）的特征表
_LEGACY_TABLES = ("peaks",)


@dataclass
class XinDbLibrary:
    """一个已挂载的 xinDB（= 设置界面上的一行）。"""

    path: Path
    ok: bool = False
    reason: str = ""
    schema_version: int = 0
    entry_count: int = 0
    library_kind: str = ""
    data_date: str = ""
    build_time: str = ""
    build_tool: str = ""
    top_k: int = 0
    peak_convention: str = ""
    size_bytes: int = 0

    @property
    def label(self) -> str:
        """展示名：``library_kind``（``COD-Inorg`` 等）优先，否则文件名。"""
        return self.library_kind or self.path.stem

    def summary(self) -> str:
        if not self.ok:
            return "不可用：%s" % (self.reason or "未知原因")
        parts: list[str] = []
        if self.entry_count:
            parts.append(f"{self.entry_count:,} 相")
        if self.size_bytes:
            parts.append(f"{self.size_bytes / 1048576:.0f} MB")
        if self.data_date:
            parts.append("数据 " + self.data_date)
        return " · ".join(parts)

    def detail(self) -> str:
        lines = [f"路径：{self.path}"]
        if self.ok:
            lines.append(f"库标识：{self.library_kind or '-'}　schema v{self.schema_version}")
            lines.append(f"物相：{self.entry_count:,}　每相保留 K={self.top_k or '-'}")
            if self.data_date:
                lines.append(f"快照日期：{self.data_date}")
            if self.build_time:
                lines.append(f"建库时间：{self.build_time}"
                             + (f"（{self.build_tool}）" if self.build_tool else ""))
            if self.peak_convention:
                lines.append(f"峰口径：{self.peak_convention}")
            lines.append("注意：xinDB 不含 CIF 原文，仅用于检索定位。")
        else:
            lines.append("状态：" + self.summary())
        return "\n".join(lines)


def probe_xindb(db_path: str | Path) -> tuple[bool, str]:
    """轻量判别：该文件是不是可用的 xinDB v3（只读 meta，不碰峰数据段）。

    Returns:
        ``(ok, reason)``；失败原因为机器可读短标记（``file_not_found`` /
        ``not_a_file`` / ``not_sqlite`` / ``legacy_schema:xinmatch-v1`` /
        ``missing_table:...`` / ``unsupported_schema:...`` 等）。

    与 XinMatch ``reader_v3`` 的差异：``meta.schema_version`` 缺失时不判死
    （早期构建有漏写的情况），只看表结构与可读性；写了就必须是 3。
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
                if table == "peak_chunks" and any(t in names for t in _LEGACY_TABLES):
                    return False, "legacy_schema:xinmatch-v1"
                return False, "missing_table:" + table
        schema = 0
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if row is not None:
                schema = int(row[0])
        except (sqlite3.Error, TypeError, ValueError):
            schema = 0
        if schema and schema != SCHEMA_VERSION:
            return False, "unsupported_schema:%s" % schema
    except sqlite3.Error as exc:
        return False, "open_failed:%s" % exc
    finally:
        conn.close()
    return True, ""


def describe_library(db_path: str | Path) -> XinDbLibrary:
    """探测并读出库概况（界面展示用；失败也返回对象，``ok=False``）。"""
    p = Path(db_path)
    lib = XinDbLibrary(path=p)
    try:
        lib.size_bytes = p.stat().st_size
    except OSError:
        pass
    ok, reason = probe_xindb(p)
    lib.ok, lib.reason = ok, reason
    if not ok:
        return lib
    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
        try:
            meta = {str(k): str(v) for k, v in conn.execute("SELECT key, value FROM meta")}
        finally:
            conn.close()
    except sqlite3.Error:
        meta = {}
    try:
        lib.schema_version = int(meta.get("schema_version") or SCHEMA_VERSION)
    except ValueError:
        lib.schema_version = SCHEMA_VERSION
    try:
        lib.entry_count = int(meta.get("entry_count") or 0)
    except ValueError:
        pass
    try:
        lib.top_k = int(meta.get("top_k") or 0)
    except ValueError:
        pass
    lib.library_kind = meta.get("library_kind", "")
    lib.data_date = meta.get("data_date", "")
    lib.build_time = meta.get("build_time", "")
    lib.build_tool = meta.get("build_tool", "")
    lib.peak_convention = meta.get("peak_convention", "")
    return lib


class XinDbAdapter(BaseAdapter):
    """xinDB v3 库检索（只读；库内不含 CIF 原文，不提供下载）。"""

    name = "xindb"
    display_key = "xinDB 库"

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)

    # ---- 可用性 ----
    def configured_paths(self) -> list[str]:
        return config.xindb_paths()

    def libraries(self) -> list[XinDbLibrary]:
        return [describe_library(p)
                for p in all_libraries("xindb", self.configured_paths())]

    def usable_libraries(self) -> list[XinDbLibrary]:
        return [lib for lib in self.libraries() if lib.ok]

    def is_available(self) -> bool:
        return config.source_enabled("xindb") and bool(self.usable_libraries())

    def availability_reason(self) -> str:
        if not config.source_enabled("xindb"):
            return "已在设置中关闭"
        if not self.configured_paths():
            return "未配置 xinDB 库文件"
        libs = self.libraries()
        if not libs:
            return "配置的路径不存在"
        usable = [lib for lib in libs if lib.ok]
        if not usable:
            return "没有可用的 xinDB 库（%s）" % (libs[0].reason or "未知原因")
        if len(usable) < len(libs):
            return "已挂载 %d 个库（%d 个不可用）" % (len(usable), len(libs) - len(usable))
        return ""

    # ---- 检索 ----
    def search(self, query: SearchQuery) -> list[Candidate]:
        if not config.source_enabled("xindb"):
            raise AdapterError("已在设置中关闭 xinDB")
        if not self.configured_paths():
            raise AdapterError("未配置 xinDB 库文件")
        libs = [lib for lib in self.libraries() if lib.ok]
        if not libs:
            raise AdapterError("xinDB 库不可用：%s" % self.availability_reason())

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

    def _query_library(self, lib: XinDbLibrary, query: SearchQuery) -> list[dict]:
        try:
            conn = sqlite3.connect(f"file:{lib.path}?mode=ro", uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise AdapterError(f"库打开失败：{exc}") from exc
        try:
            sql, args = self._build_sql(query)
            return [dict(row) for row in conn.execute(sql, args)]
        except sqlite3.Error as exc:
            raise AdapterError(f"检索失败：{exc}") from exc
        finally:
            conn.close()

    def _build_sql(self, query: SearchQuery) -> tuple[str, list]:
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
                # xinDB 无 sg_number 列：编号无法精确反查 H-M 符号，
                # 退化为文本包含匹配（仅对 "P 21/c" 这类含数字的写法有效）
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
        return sql, args

    def _row_to_candidate(self, row: dict, lib: XinDbLibrary) -> Candidate:
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
        if mineral in ("?", "None"):
            mineral = ""
        space_group = str(row.get("space_group") or "").strip()
        if space_group in ("?", "None"):
            space_group = ""
        provenance = f"xinDB {entry_id}"
        if mineral:
            provenance += f" · {mineral}"
        provenance += f" · {lib.label}"
        return Candidate(
            source=self.name,
            source_id=entry_id,
            formula=formula,
            mineral_name=mineral,
            space_group=space_group,
            crystal_system=str(row.get("crystal_system") or ""),
            lattice=lattice,
            elements=elements,
            provenance=provenance,
            extra={"_no_cif": True, "_lib_label": lib.label,
                   "_lib_path": str(lib.path)},
        )

    # ---- CIF 下载：xinDB 不含 CIF 原文 ----
    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        raise AdapterError("xinDB 库仅含检索索引与峰数据，不包含 CIF 原文；"
                           "请通过 COD 联网检索或其他来源获取该 CIF")


__all__ = [
    "SCHEMA_VERSION",
    "XinDbAdapter",
    "XinDbLibrary",
    "describe_library",
    "probe_xindb",
]
