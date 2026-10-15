"""适配器基类与 HTTP 工具（stdlib urllib，零第三方依赖）。"""
from __future__ import annotations

import gzip
import io
import logging
import urllib.error
import urllib.parse
import urllib.request
import zlib
import ssl
from typing import Optional

from getcif.core.schema import Candidate, SearchQuery

logger = logging.getLogger(__name__)

#: 浏览器风格 UA（COD 等站点会掐断非浏览器 UA 的连接）
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 PolyXRD-GetCIF/1.0")


class AdapterError(Exception):
    """适配器错误（携带用户可读原因）。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class BaseAdapter:
    """数据源适配器基类：可用性检查 + 检索 + CIF 下载。"""

    name = "base"
    display_key = ""  # i18n key

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = int(timeout)
        self.last_total_count: Optional[int] = None
        #: 可选 TLS 上下文（证书过期的站点置 CERT_NONE，如 atomly）
        self.ssl_context: Optional[ssl.SSLContext] = None

    def _urlopen(self, request: urllib.request.Request):
        return urllib.request.urlopen(request, timeout=self.timeout,
                                      context=self.ssl_context)

    # ---- 子类接口 ----
    def is_available(self) -> bool:
        raise NotImplementedError

    def availability_reason(self) -> str:
        return ""

    def search(self, query: SearchQuery) -> list[Candidate]:
        raise NotImplementedError

    def download_cif(self, candidate: Candidate) -> Optional[str]:
        return candidate.cif_content or None

    # ---- HTTP 工具 ----
    def _http_get(self, url: str, headers: Optional[dict] = None) -> str:
        """GET 文本（自动解压 gzip/deflate）。失败抛 AdapterError。"""
        request = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
            **(headers or {}),
        })
        try:
            with self._urlopen(request) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                encoding = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in encoding or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                elif "deflate" in encoding:
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            raise AdapterError(f"HTTP {exc.code}: {url}") from exc
        except urllib.error.URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            if "timed out" in reason.lower():
                raise AdapterError(f"请求超时（{self.timeout}s）：{url}") from exc
            raise AdapterError(f"网络不可用：{reason}") from exc
        except OSError as exc:
            raise AdapterError(f"网络连接错误：{exc}") from exc

    def _http_post_form(self, url: str, fields: dict[str, str],
                        headers: Optional[dict] = None) -> str:
        """POST 表单编码文本。失败抛 AdapterError。"""
        data = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            **(headers or {}),
        })
        try:
            with self._urlopen(request) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                raw = resp.read()
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            # 尝试读取错误体（有的 API 用错误体传业务信息）
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = ""
            raise AdapterError(f"HTTP {exc.code}: {body[:200] or url}") from exc
        except urllib.error.URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            if "timed out" in reason.lower():
                raise AdapterError(f"请求超时（{self.timeout}s）：{url}") from exc
            raise AdapterError(f"网络不可用：{reason}") from exc
        except OSError as exc:
            raise AdapterError(f"网络连接错误：{exc}") from exc

    def _http_post_json(self, url: str, payload: dict,
                        headers: Optional[dict] = None) -> dict:
        """POST JSON 并解析 JSON 响应。失败抛 AdapterError。"""
        import json

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            **(headers or {}),
        })
        try:
            with self._urlopen(request) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                raw = resp.read()
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode(charset, errors="replace"))
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = ""
            raise AdapterError(f"HTTP {exc.code}: {body[:200] or url}") from exc
        except urllib.error.URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            if "timed out" in reason.lower():
                raise AdapterError(f"请求超时（{self.timeout}s）：{url}") from exc
            raise AdapterError(f"网络不可用：{reason}") from exc
        except (OSError, ValueError) as exc:
            raise AdapterError(f"请求/解析失败：{exc}") from exc

    def _read_url_bytes(self, url: str, headers: Optional[dict] = None) -> bytes:
        """GET 二进制（下载文件用）。失败抛 AdapterError。"""
        request = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT, **(headers or {}),
        })
        try:
            with self._urlopen(request) as resp:
                raw = resp.read()
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as exc:
            raise AdapterError(f"HTTP {exc.code}: {url}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise AdapterError(f"下载失败：{exc}") from exc


def decompress_cif_blob(blob: bytes) -> str:
    """SQLite 里的 CIF blob：gzip / zlib / zlib 头变体 / 明文，自适应解码。"""
    if not blob:
        return ""
    if blob[:2] == b"\x1f\x8b":
        return gzip.decompress(blob).decode("utf-8", errors="replace")
    if blob[:1] == b"\x78":
        try:
            return zlib.decompress(blob).decode("utf-8", errors="replace")
        except zlib.error:
            try:
                return zlib.decompress(blob, -zlib.MAX_WBITS).decode("utf-8", errors="replace")
            except zlib.error:
                pass
    return blob.decode("utf-8", errors="replace")


__all__ = [
    "AdapterError",
    "BaseAdapter",
    "decompress_cif_blob",
    "io",
]
