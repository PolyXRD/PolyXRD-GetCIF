"""Materials Project 联网检索适配器（API key 门控）。

直连 MP 官方 REST API（``api.materialsproject.org``，X-API-KEY 鉴权）：

* ``GET /materials/summary/?formula=SiO2&_limit=N&_fields=...``
* ``GET /materials/summary/?elements=Ti-O&_limit=N&_fields=...``

响应 ``data[].structure`` 含 lattice（a/b/c/alpha/beta/gamma + matrix）与
sites（abc 分数坐标 + species），由 :mod:`getcif.cifparse` 的
``cif_from_structure`` 生成 CIF 文本供预览/保存。
"""
from __future__ import annotations

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.core import config
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula
from getcif.core.formula import split_elements

MP_API_BASE = "https://api.materialsproject.org"
_FIELDS = "material_id,formula_pretty,formula_anonymous,symmetry,synthesis_type"

_SYSTEM_MAP = {
    "triclinic": "triclinic", "monoclinic": "monoclinic",
    "orthorhombic": "orthorhombic", "tetragonal": "tetragonal",
    "trigonal": "trigonal", "hexagonal": "hexagonal", "cubic": "cubic",
}


class MpAdapter(BaseAdapter):
    """Materials Project 在线检索（API key 门控，用户配置后开启）。"""

    name = "mp"
    display_key = "MP（联网）"

    def is_available(self) -> bool:
        return config.source_enabled("mp") and bool(config.mp_api_key())

    def availability_reason(self) -> str:
        if not config.source_enabled("mp"):
            return "已在设置中关闭"
        if not config.mp_api_key():
            return "未配置 API Key（materialsproject.org 免费注册获取）"
        return ""

    def _auth_headers(self) -> dict[str, str]:
        return {"X-API-KEY": config.mp_api_key()}

    def search(self, query: SearchQuery) -> list[Candidate]:
        if not query.formula and not query.elements:
            raise AdapterError("MP 仅支持化学式 / 元素检索")
        limit = min(50, max(1, query.limit))
        params: list[str] = []
        if query.formula:
            params.append(f"formula={query.formula.strip()}")
        else:
            elements = split_elements(query.elements)
            params.append("elements=" + "-".join(elements))
        params.append(f"_limit={limit}")
        params.append(f"_fields={_FIELDS}")
        url = f"{MP_API_BASE}/materials/summary/?{'&'.join(params)}"
        response = self._http_get(url, headers=self._auth_headers())
        import json

        try:
            payload = json.loads(response)
        except ValueError as exc:
            raise AdapterError(f"MP 响应解析失败：{exc}") from exc
        if not isinstance(payload, dict) or "data" not in payload:
            raise AdapterError("MP 响应格式异常（检查 API Key 是否有效）")

        candidates: list[Candidate] = []
        for item in payload.get("data") or []:
            material_id = str(item.get("material_id") or "").strip()
            if not material_id:
                continue
            symmetry = item.get("symmetry") or {}
            system = str(symmetry.get("crystal_system") or "")
            candidates.append(Candidate(
                source=self.name,
                source_id=material_id,
                formula=str(item.get("formula_pretty") or ""),
                space_group=str(symmetry.get("symbol") or ""),
                crystal_system=system,
                lattice=self._lattice_of(item.get("structure")),
                elements=elements_from_formula(str(item.get("formula_pretty") or "")),
                provenance=f"MP {material_id}",
                extra={"_structure": item.get("structure")},
            ))
        self.last_total_count = len(candidates)
        return candidates

    @staticmethod
    def _lattice_of(structure: dict | None) -> LatticeParams:
        lattice = (structure or {}).get("lattice") or {}
        return LatticeParams(
            a=float(lattice.get("a") or 0), b=float(lattice.get("b") or 0),
            c=float(lattice.get("c") or 0),
            alpha=float(lattice.get("alpha") or 0), beta=float(lattice.get("beta") or 0),
            gamma=float(lattice.get("gamma") or 0),
            volume=float(lattice.get("volume") or 0),
        )

    def download_cif(self, candidate: Candidate) -> Optional[str]:
        """MP 结果的 CIF 由检索时携带的 structure 数据合成（无需二次请求）。"""
        if candidate.cif_content:
            return candidate.cif_content
        structure = candidate.extra.get("_structure")
        if not structure:
            raise AdapterError("该 MP 条目缺少结构数据，无法生成 CIF")
        from getcif.cifparse import cif_from_structure

        candidate.cif_content = cif_from_structure(structure, candidate.source_id)
        return candidate.cif_content
