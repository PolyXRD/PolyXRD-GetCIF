"""AMCSD（American Mineralogist Crystal Structure Database）联网检索适配器。

参数体系移植自 PolyXRD-CifCalc ``amcsd_adapter``（2026-10 现行表单，
Wayback 快照核实）：检索 **POST** 到 ``/AMS/result.php``，字段名为首字母
大写的 ``Mineral`` / ``Periodic`` / ``CellParam``（PHP 大小写敏感）；
CIF 下载走 ``/AMS/download_cif.php?id=...``。零结果时以小写旧参数名兜底重试。
"""
from __future__ import annotations

import re
from typing import Optional

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.core import config
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula

AMCSD_BASE = "https://rruff.geo.arizona.edu"
AMCSD_SEARCH_URL = f"{AMCSD_BASE}/AMS/result.php"
AMCSD_CIF_URL = f"{AMCSD_BASE}/AMS/download_cif.php"

_FORM_DEFAULTS = {"logic": "AND", "Viewing": "amclongform", "Download": "amc"}
_CELL_RE = re.compile(
    r"(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+"
    r"(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)"
)
_AMCSD_ID_TEXT = re.compile(r"_database_code_amcsd\s+([0-9]+)", re.IGNORECASE)
_AMCSD_ID_QUERY = re.compile(r"(?:^|[?&])id=(\d+)")
_FORMULA_TIGHT = re.compile(
    r"\b([A-Z][a-z]?(?:\d+(?:\.\d+)?)?(?:[A-Z][a-z]?(?:\d+(?:\.\d+)?)?)+)\b"
)


def _cell_expression(query: SearchQuery) -> str:
    """晶胞参数 → CellParam 表达式（``a=4.81to4.91 and b=...`` 区间语法）。"""
    parts: list[str] = []
    for key, value, tol in (
        ("a", query.a, 0.1), ("b", query.b, 0.1), ("c", query.c, 0.1),
        ("alpha", query.alpha, 0.5), ("beta", query.beta, 0.5), ("gamma", query.gamma, 0.5),
    ):
        if value is None:
            continue
        parts.append(f"{key}={value - tol:g}to{value + tol:g}")
    return " and ".join(parts)


def _clean_formula(text: str) -> str:
    """从结果行文本里抠化学式（如 ``Si O2`` / ``CaMg(CO3)2``）。"""
    match = _FORMULA_TIGHT.search(str(text or ""))
    return match.group(1) if match else ""


class AmcsdAdapter(BaseAdapter):
    """AMCSD 联网检索（无需凭证，用户在设置中开启）。"""

    name = "amcsd"
    display_key = "AMCSD（联网）"

    def is_available(self) -> bool:
        return config.source_enabled("amcsd")

    def availability_reason(self) -> str:
        return "" if self.is_available() else "已在设置中关闭（无需凭证，可随时开启）"

    def search(self, query: SearchQuery) -> list[Candidate]:
        fields = self._build_fields(query)
        if not fields:
            raise AdapterError("AMCSD 不支持该检索条件组合")
        html = self._http_post_form(AMCSD_SEARCH_URL, {**_FORM_DEFAULTS, **fields})
        candidates = self._parse_results(html)
        if not candidates and fields != self._build_legacy_fields(query):
            html = self._http_post_form(
                AMCSD_SEARCH_URL, {**_FORM_DEFAULTS, **self._build_legacy_fields(query)}
            )
            candidates = self._parse_results(html)
        self.last_total_count = len(candidates)
        return candidates[: max(1, query.limit)]

    def _build_fields(self, query: SearchQuery) -> dict[str, str]:
        fields: dict[str, str] = {}
        if query.name:
            fields["Mineral"] = query.name.strip()
        if query.elements:
            from getcif.core.formula import split_elements

            elements = split_elements(query.elements)
            if elements:
                fields["Periodic"] = f"({','.join(elements)}) -"
        cell = _cell_expression(query)
        if cell:
            fields["CellParam"] = cell
        if query.formula and "Periodic" not in fields:
            # AMCSD 无直接化学式字段；化学式退化到 Periodic 元素通道
            from getcif.core.formula import split_elements

            elements = split_elements(query.formula)
            if elements:
                fields["Periodic"] = f"({','.join(elements)}) -"
        return fields

    def _build_legacy_fields(self, query: SearchQuery) -> dict[str, str]:
        fields = self._build_fields(query)
        return {
            ("mineral" if k == "Mineral" else
             "chemistry" if k == "Periodic" else
             "cellparam" if k == "CellParam" else k): v
            for k, v in fields.items()
        }

    def _parse_results(self, html: str) -> list[Candidate]:
        candidates: list[Candidate] = []
        seen: set[str] = set()
        # 结果页每条记录含 download_cif.php?id=NNNN 链接；抓长表单记录块
        blocks = re.split(r"<tr[^>]*>", html, flags=re.IGNORECASE)
        for block in blocks:
            ids = _AMCSD_ID_QUERY.findall(block) or _AMCSD_ID_TEXT.findall(
                re.sub(r"<[^>]+>", " ", block)
            )
            if not ids:
                continue
            amcsd_id = ids[0]
            if amcsd_id in seen:
                continue
            seen.add(amcsd_id)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", block)).strip()
            cell_match = _CELL_RE.search(text)
            lattice = LatticeParams()
            if cell_match:
                values = [float(v) for v in cell_match.groups()]
                lattice = LatticeParams(*values[:6])
            formula = _clean_formula(text)
            mineral = ""
            mineral_match = re.search(r"(?:Mineral|mineral|Name)\s*:?\s*([A-Z][a-z]+(?:ite|ase|yl))", text)
            if mineral_match:
                mineral = mineral_match.group(1)
            candidates.append(Candidate(
                source=self.name,
                source_id=amcsd_id,
                formula=formula,
                mineral_name=mineral,
                lattice=lattice,
                elements=elements_from_formula(formula),
                cif_url=f"{AMCSD_CIF_URL}?id={amcsd_id}",
                provenance=f"AMCSD {amcsd_id}" + (f" · {mineral}" if mineral else ""),
            ))
        return candidates

    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        amcsd_id = re.sub(r"\D", "", str(candidate.source_id or ""))
        if not amcsd_id:
            return None
        text = self._http_get(f"{AMCSD_CIF_URL}?id={amcsd_id}")
        if "data_" in text:
            candidate.cif_content = text
            if not candidate.source_id:
                match = _AMCSD_ID_TEXT.search(text)
            return text
        raise AdapterError(f"AMCSD CIF 内容异常：id={amcsd_id}")
