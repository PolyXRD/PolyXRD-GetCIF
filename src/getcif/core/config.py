"""应用设置：持久化到 ``<appdata>/PolyXRD/GetCIF/settings.toml``。

自带极简 TOML 读写（仅支持本工具用到的 [section] + 标量值），
避免引入 tomllib（Py3.11+）/ tomli 依赖，便于打包单 exe。
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

APP_VENDOR = "PolyXRD"
APP_DIR_NAME = "GetCIF"
SETTINGS_FILE = "settings.toml"

_lock = threading.Lock()
_cache: Optional[dict] = None


def app_config_dir() -> Path:
    """用户配置目录（``%APPDATA%/PolyXRD/GetCIF``，非 Windows 回退 ~/.polyxrd）。

    可用环境变量 ``POLYXRD_GETCIF_CONFIG_DIR`` 覆盖（测试 / 便携场景），
    自检脚本借此隔离临时配置，避免写入用户真实设置。
    """
    override = os.environ.get("POLYXRD_GETCIF_CONFIG_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path
    base = os.environ.get("APPDATA")
    if base:
        path = Path(base) / APP_VENDOR / APP_DIR_NAME
    else:
        path = Path.home() / ".polyxrd" / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return app_config_dir() / SETTINGS_FILE


def downloads_dir() -> Path:
    path = app_config_dir() / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = app_config_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ----------------------------------------------------------------------
# 极简 TOML（本工具仅用 [section] + str/int/float/bool 标量）
# ----------------------------------------------------------------------
def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def dumps(data: dict) -> str:
    lines: list[str] = []
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
            else:
                lines.append(f'{key} = "{_escape(str(value))}"')
        lines.append("")
    return "\n".join(lines)


def loads(text: str) -> dict:
    result: dict[str, dict[str, Any]] = {}
    section: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            section = result.setdefault(name, {})
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # 去掉行尾注释（仅当值是裸标量时）
        if value and value[0] not in "\"'":
            value = value.split("#", 1)[0].strip()
        if value.lower() in ("true", "false"):
            section[key] = value.lower() == "true"
            continue
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            inner = value[1:-1]
            section[key] = (
                inner.replace("\\\\", "\x00").replace('\\"', '"')
                .replace("\\n", "\n").replace("\x00", "\\")
            )
            continue
        try:
            section[key] = int(value)
        except ValueError:
            try:
                section[key] = float(value)
            except ValueError:
                section[key] = value
    return result


def load() -> dict:
    """读取全部设置（带缓存）。"""
    global _cache
    if _cache is not None:
        return _cache
    path = settings_path()
    data: dict = {}
    try:
        if path.exists():
            data = loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("设置读取失败（按默认处理）：%s | %s", path, exc)
    _cache = data if isinstance(data, dict) else {}
    return _cache


def save(section: str, values: dict) -> None:
    """合并写入一个节（保留其余节；失败仅告警）。"""
    global _cache
    with _lock:
        data = load()
        merged = dict(data.get(section) or {})
        merged.update(values)
        data[section] = merged
        path = settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dumps(data), encoding="utf-8")
            _cache = data
        except OSError as exc:
            logger.warning("设置写入失败：%s | %s", path, exc)


def get(section: str, key: str, default: Any = None) -> Any:
    return (load().get(section) or {}).get(key, default)


# ----------------------------------------------------------------------
# 高层便捷读写
# ----------------------------------------------------------------------
def load_language() -> str:
    lang = str(get("ui", "language", "zh"))
    return lang if lang in ("zh", "en", "ja") else "zh"


def save_language(lang: str) -> None:
    if lang in ("zh", "en", "ja"):
        save("ui", {"language": lang})


def load_last_save_dir() -> str:
    return str(get("ui", "last_save_dir", "") or "")


def save_last_save_dir(directory: str) -> None:
    if directory:
        save("ui", {"last_save_dir": str(directory)})


# ---- 数据源开关与凭证 ----
DEFAULTS = {
    "sources": {
        "cod_enabled": True,        # COD 联网：默认开启
        "local_enabled": True,      # 本地数据库：默认开启（配置路径后生效）
        "amcsd_enabled": False,     # 以下联网源在用户配置完成后开启
        "mp_enabled": False,
        "atomly_enabled": False,
        "polydb_enabled": True,     # polyDB 外挂库：默认开启（配置目录后生效）
        "xindb_enabled": True,      # xinDB 库：默认开启（配置文件后生效）
    },
    "net": {"timeout": 30},
}


def source_enabled(name: str) -> bool:
    """数据源是否启用（cod 默认 True；其余默认 False，配置完成后开启）。"""
    default = bool(DEFAULTS["sources"].get(f"{name}_enabled", False))
    return bool(get("sources", f"{name}_enabled", default))


def set_source_enabled(name: str, enabled: bool) -> None:
    save("sources", {f"{name}_enabled": bool(enabled)})


def net_timeout() -> int:
    try:
        return max(5, int(get("net", "timeout", 30)))
    except (TypeError, ValueError):
        return 30


def set_net_timeout(seconds: int) -> None:
    save("net", {"timeout": int(seconds)})


def mp_api_key() -> str:
    return str(get("credentials", "mp_api_key", "") or "").strip()


def atomly_token() -> str:
    return str(get("credentials", "atomly_token", "") or "").strip()


def cod_local_db() -> str:
    return str(get("local", "db_path", "") or "").strip()


def cod_local_root() -> str:
    return str(get("local", "cod_root", "") or "").strip()


def polydb_path() -> str:
    """polyDB 外挂库目录（PolyXRD v4 目录容器：meta.json + index.sqlite + 数组段）。

    兼容 v1.4.0 之前的单库配置；多库场景请用 :func:`polydb_paths`。
    """
    return str(get("local", "polydb_path", "") or "").strip()


def xindb_path() -> str:
    """xinDB v3 库文件（XinMatch 列存参考库，单文件 .xinDB）。

    兼容 v1.4.0 之前的单库配置；多库场景请用 :func:`xindb_paths`。
    """
    return str(get("local", "xindb_path", "") or "").strip()


# ----------------------------------------------------------------------
# 本地库列表（v1.4.0：列表式多库挂载）
#
# PolyXRD v4.0.0 / XinMatch v2.0.0 都把外挂库改成"想挂几个挂几个"，本工具
# 跟随同一模型。持久化用 ``<kind>_paths``（**换行分隔**的字符串）：
# 自带 TOML 只支持 [section] + 标量，而 ``_escape``/``loads`` 已经处理 ``\n``
# 转义，所以无需为列表改造读写器，也不会引入 tomllib 依赖（打包体积不变）。
#
# 老配置里的 ``polydb_path`` / ``xindb_path`` 仍然有效：读取时自动并入列表
# （排在最前），写入时同步成列表首项 —— 升级后用户的库不会"丢"。
# ----------------------------------------------------------------------
_SUPPORTED_LIB_KINDS = ("polydb", "xindb")


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").replace("\r", "\n").split("\n")
            if line.strip()]


def lib_paths(kind: str) -> list[str]:
    """读取某一类本地库的全部路径（去重、保序；老单路径自动并入）。"""
    if kind not in _SUPPORTED_LIB_KINDS:
        return []
    items = _split_lines(str(get("local", f"{kind}_paths", "") or ""))
    legacy = str(get("local", f"{kind}_path", "") or "").strip()
    if legacy and legacy not in items:
        items.insert(0, legacy)
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def save_lib_paths(kind: str, paths: list[str]) -> None:
    """写入某一类本地库的路径列表（同时同步老的单路径键为列表首项）。"""
    if kind not in _SUPPORTED_LIB_KINDS:
        return
    items = [str(p).strip() for p in (paths or []) if str(p).strip()]
    save("local", {
        f"{kind}_paths": "\n".join(items),
        f"{kind}_path": items[0] if items else "",
    })


def polydb_paths() -> list[str]:
    """polyDB 外挂库目录列表（每项可以是库本体，也可以是装着若干 .polyDB 的父目录）。"""
    return lib_paths("polydb")


def xindb_paths() -> list[str]:
    """xinDB 库文件列表（每项可以是 .xinDB 本体，也可以是装着若干 .xinDB 的目录）。"""
    return lib_paths("xindb")


def save_polydb_paths(paths: list[str]) -> None:
    save_lib_paths("polydb", paths)


def save_xindb_paths(paths: list[str]) -> None:
    save_lib_paths("xindb", paths)
