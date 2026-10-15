"""Atomly（atomly.net，中科院物理所 / 松山湖材料实验室）联网检索适配器（token 门控）。

端点契约（2026-10 依 atomly 前端逆向，与 PolyXRD-CifCalc atomly_adapter 一致）：

* ``POST /api/matdata/search_by_formula/``   ``{"include": "SiO2"}``
* ``POST /api/matdata/search_by_elements/``  ``{"include": "Si,O"}``
* ``POST /api/matdata/get_struct_detail/``   ``{"struct_id": "12345"}``
  → ``output_structs.output_struct_conventional`` 为 CIF 文本。

鉴权：请求头 ``Authorization: token <userToken>``（浏览器 localStorage 取得）。
站点证书过期问题：默认 ``verify=False`` 等价的宽松策略（urllib 默认不校验
自签名链问题不存在，但站点若 TLS 握手失败需用户自行处理）。
"""
from __future__ import annotations

import re

from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.core import config
from getcif.core.schema import Candidate, LatticeParams, SearchQuery, elements_from_formula
from getcif.core.formula import split_elements

ATOMLY_BASE = "https://atomly.net"
SEARCH_BY_FORMULA = f"{ATOMLY_BASE}/api/matdata/search_by_formula/"
SEARCH_BY_ELEMENTS = f"{ATOMLY_BASE}/api/matdata/search_by_elements/"
GET_STRUCT_DETAIL = f"{ATOMLY_BASE}/api/matdata/get_struct_detail/"

#: 检索行字段位置（依前端解析代码推断）
_ROW_STRUCT_ID = 0
_ROW_FORMULA = 1
_ROW_SPACE_GROUP = 2
_ROW_EABOVE_HULL = 4
_ROW_NSITES = 6
_ROW_CRYSTAL_SYSTEM = 8

_AUTH_FAILURE_MARKERS = ("need login", "invalid token", "token has expired", "not authenticated")
_TAG_RE = re.compile(r"<[^>]+>")

#: 证书过期 → 跳过校验（与 CifCalc 行为一致）
import ssl

_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


class AtomlyAdapter(BaseAdapter):
    """Atomly 在线检索（token 门控，用户配置后开启）。"""

    name = "atomly"
    display_key = "Atomly（联网）"

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)
        self.ssl_context = _SSL_CONTEXT

    def is_available(self) -> bool:
        return config.source_enabled("atomly") and bool(config.atomly_token())

    def availability_reason(self) -> str:
        if not config.source_enabled("atomly"):
            return "已在设置中关闭"
        if not config.atomly_token():
            return "未配置 Token（atomly.net 登录后从浏览器 localStorage 取 userToken）"
        return ""

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"token {config.atomly_token()}"}

    def search(self, query: SearchQuery) -> list[Candidate]:
        if query.formula:
            url, payload = SEARCH_BY_FORMULA, {"include": query.formula.strip()}
        elif query.elements:
            elements = split_elements(query.elements)
            if not elements:
                raise AdapterError("元素条件解析失败")
            url, payload = SEARCH_BY_ELEMENTS, {"include": ",".join(elements)}
        else:
            raise AdapterError("Atomly 仅支持化学式 / 元素检索")

        data = self._http_post_json(url, payload, headers=self._auth_headers())
        if isinstance(data, dict) and any(
            marker in str(data).lower() for marker in _AUTH_FAILURE_MARKERS
        ):
            raise AdapterError("登录态失效：请更新 Atomly Token")
        rows = data.get("output_structs") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise AdapterError("Atomly 响应格式异常")

        candidates: list[Candidate] = []
        for row in rows[: max(1, query.limit)]:
            if not isinstance(row, list) or len(row) <= _ROW_CRYSTAL_SYSTEM:
                continue
            struct_id = str(row[_ROW_STRUCT_ID] or "").strip()
            if not struct_id:
                continue
            formula = _TAG_RE.sub("", str(row[_ROW_FORMULA] or ""))
            candidates.append(Candidate(
                source=self.name,
                source_id=struct_id,
                formula=formula,
                space_group=str(row[_ROW_SPACE_GROUP] or ""),
                crystal_system=str(row[_ROW_CRYSTAL_SYSTEM] or ""),
                elements=elements_from_formula(formula),
                provenance=f"Atomly {struct_id}",
                extra={"_e_above_hull": row[_ROW_EABOVE_HULL] if len(row) > _ROW_EABOVE_HULL else None},
            ))
        self.last_total_count = len(candidates)
        return candidates

    def download_cif(self, candidate: Candidate) -> Optional[str]:
        if candidate.cif_content:
            return candidate.cif_content
        struct_id = str(candidate.source_id or "").strip()
        if not struct_id:
            return None
        data = self._http_post_json(
            GET_STRUCT_DETAIL, {"struct_id": struct_id}, headers=self._auth_headers()
        )
        structs = (data or {}).get("output_structs") or {}
        cif_text = (structs.get("output_struct_conventional")
                    or structs.get("output_struct_primitive") or "")
        if "data_" in str(cif_text):
            candidate.cif_content = str(cif_text)
            return candidate.cif_content
        raise AdapterError(f"Atomly 未返回 CIF 内容：id={struct_id}")
