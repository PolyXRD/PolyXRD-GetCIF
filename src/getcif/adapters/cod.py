"""COD（Crystallography Open Database）联网检索适配器。

参数体系移植自 PolyXRD 的 ``polyxrd.services.cod_searcher``（2026-10 现行
``result.php`` 界面），但**自包含、不依赖 polyxrd**：

* 检索端点 ``/cod/result.php``；矿物名走文献文本检索 ``text1``；
* 空间群纯数字走 ``space_group_number``，符号走 ``spacegroup``（空格分隔）；
* 晶胞只接受区间参数（amin/amax/...），单值 ± 容差展开；
* 化学式要求元素按字母序、空格分隔（``O2 Si``）。
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Optional

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.core import config
from getcif.core.formula import normalize_cod_formula, spaced_hm_symbol
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula

COD_BASE_URL = "https://www.crystallography.net/cod"
COD_SEARCH_URL = f"{COD_BASE_URL}/result.php"

CELL_LENGTH_TOLERANCE = 0.1
CELL_ANGLE_TOLERANCE = 0.5

_TAG_RE = re.compile(r"<[^>]+>")
_FLOAT_LITERAL_RE = re.compile(r"^\d+(?:\.\d+)?$")


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", str(text))).strip()


def _to_float(text: object) -> Optional[float]:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def _split_length_angle(token: str) -> tuple[Optional[float], Optional[float]]:
    """拆分 COD 结果页「c 与 alpha 连写」的 token（同 polyxrd 逻辑）。"""
    token = str(token).strip()
    if not token:
        return None, None
    ws_parts = token.split()
    if len(ws_parts) == 2 and all(_FLOAT_LITERAL_RE.match(p) for p in ws_parts):
        return float(ws_parts[0]), float(ws_parts[1])
    best: Optional[tuple[float, float]] = None
    for split in range(1, len(token)):
        left, right = token[:split], token[split:]
        if not (_FLOAT_LITERAL_RE.match(left) and _FLOAT_LITERAL_RE.match(right)):
            continue
        length, angle = float(left), float(right)
        if 0.5 <= length <= 200.0 and 0.0 < angle <= 180.0:
            if best is None or angle > best[1]:
                best = (length, angle)
    if best is not None:
        return best
    value = _to_float(token)
    return (value, None) if value is not None else (None, None)


def _parse_cell_text(text: str) -> dict[str, float]:
    """解析晶胞列文本 ``a; b; c alpha; beta; gamma`` → dict（缺项不回填）。"""
    parts = [part.strip() for part in str(text).split(";")]
    if len(parts) != 5:
        return {}
    lattice: dict[str, float] = {}
    for key, part in zip(("a", "b"), parts[:2]):
        value = _to_float(part)
        if value is not None:
            lattice[key] = value
    c_value, alpha = _split_length_angle(parts[2])
    if c_value is not None:
        lattice["c"] = c_value
    if alpha is not None:
        lattice["alpha"] = alpha
    for key, part in zip(("beta", "gamma"), parts[3:5]):
        value = _to_float(part)
        if value is not None:
            lattice[key] = value
    return lattice


def _space_group_params(space_group: str) -> dict[str, str]:
    """空间群条件 → COD 参数（无 spglib 依赖，符号直传空格分隔形式）。"""
    text = str(space_group or "").strip()
    if not text:
        return {}
    if text.isdigit():
        return {"space_group_number": text}
    return {"spacegroup": spaced_hm_symbol(text)}


class CodAdapter(BaseAdapter):
    """COD 联网检索（默认启用，无需凭证）。"""

    name = "cod"
    display_key = "COD（联网）"

    def is_available(self) -> bool:
        return config.source_enabled("cod")

    def availability_reason(self) -> str:
        return "" if self.is_available() else "已在设置中关闭"

    def search(self, query: SearchQuery) -> list[Candidate]:
        params = self._build_params(query)
        if not params:
            raise AdapterError("COD 不支持该检索条件组合")
        url = f"{COD_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        html = self._http_get(url)
        candidates = self._parse_search_results(html)
        total = self._parse_total_count(html)
        self.last_total_count = total if total is not None else len(candidates)
        return candidates[: max(1, query.limit)]

    def _build_params(self, query: SearchQuery) -> dict[str, str]:
        params: dict[str, str] = {}
        if query.formula:
            params["formula"] = normalize_cod_formula(query.formula)
        if query.name:
            params["text1"] = str(query.name).strip()
        if query.space_group:
            params.update(_space_group_params(query.space_group))
        for key, value in (("a", query.a), ("b", query.b), ("c", query.c)):
            if value is None:
                continue
            params[f"{key}min"] = f"{value - CELL_LENGTH_TOLERANCE:.4f}"
            params[f"{key}max"] = f"{value + CELL_LENGTH_TOLERANCE:.4f}"
        for key, value in (("alp", query.alpha), ("bet", query.beta), ("gam", query.gamma)):
            if value is None:
                continue
            params[f"{key}min"] = f"{value - CELL_ANGLE_TOLERANCE:.4f}"
            params[f"{key}max"] = f"{value + CELL_ANGLE_TOLERANCE:.4f}"
        return params

    def _parse_search_results(self, html: str) -> list[Candidate]:
        """解析结果页表格（新布局：COD ID | Links | Formula | SG | Cell | Volume）。"""
        candidates: list[Candidate] = []
        seen: set[int] = set()
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
        cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
        for row_html in row_pattern.findall(html):
            cells = [_strip_tags(cell) for cell in cell_pattern.findall(row_html)]
            if len(cells) < 5:
                continue
            id_match = re.search(r"\b(\d{3,})\b", cells[0])
            if not id_match:
                continue
            cod_id = int(id_match.group(1))
            if cod_id in seen:
                continue
            seen.add(cod_id)
            formula = cells[2] if len(cells) > 2 else ""
            space_group = cells[3] if len(cells) > 3 else ""
            cell_dict = _parse_cell_text(cells[4]) if len(cells) > 4 else {}
            candidates.append(Candidate(
                source=self.name,
                source_id=str(cod_id),
                formula=formula,
                space_group=space_group,
                lattice=LatticeParams(**{k: v for k, v in cell_dict.items()}),
                elements=elements_from_formula(formula),
                cif_url=f"{COD_BASE_URL}/{cod_id}.cif",
                provenance=f"COD {cod_id}",
            ))

        # 兜底：旧布局/相对链接全文提取
        if not candidates:
            legacy = re.compile(
                r"href=[\"'](?:/cod/)?(\d{3,})\.(?:html|cif)[\"']", re.IGNORECASE
            )
            for cod_id_str in legacy.findall(html):
                try:
                    cod_id = int(cod_id_str)
                except ValueError:
                    continue
                if cod_id in seen:
                    continue
                seen.add(cod_id)
                candidates.append(Candidate(
                    source=self.name,
                    source_id=str(cod_id),
                    cif_url=f"{COD_BASE_URL}/{cod_id}.cif",
                    provenance=f"COD {cod_id}",
                ))
        return candidates

    @staticmethod
    def _parse_total_count(html: str) -> Optional[int]:
        match = re.search(r"there are (\d+) entries", html)
        if match:
            return int(match.group(1))
        if "no files matching" in html:
            return 0
        return None

    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        cod_id = re.sub(r"\D", "", str(candidate.source_id or ""))
        if not cod_id:
            return None
        url = candidate.cif_url or f"{COD_BASE_URL}/{cod_id}.cif"
        text = self._http_get(url)
        if text and "data_" in text:
            candidate.cif_content = text
            return text
        raise AdapterError(f"CIF 内容异常：{url}")
