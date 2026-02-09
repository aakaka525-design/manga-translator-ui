"""Storage-state helpers for scraper v1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


MAX_STATE_FILE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class CookieInfo:
    name: str
    value: str
    expires: Optional[float]


def normalize_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip()
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path
    return f"{scheme}://{netloc}".rstrip("/")


def _match_domain(cookie_domain: str, host: str) -> bool:
    if not cookie_domain or not host:
        return False
    cookie_domain = cookie_domain.lstrip(".").lower()
    host = host.lower()
    return host == cookie_domain or host.endswith(f".{cookie_domain}")


def load_state_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("state payload must be an object")
    return data


def collect_cookies(payload: dict[str, Any], host: str | None = None) -> list[CookieInfo]:
    cookies_raw = payload.get("cookies") if isinstance(payload, dict) else []
    if not isinstance(cookies_raw, list):
        return []

    cookies: list[CookieInfo] = []
    for item in cookies_raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        domain = str(item.get("domain") or "")
        if host and domain and not _match_domain(domain, host):
            continue
        expires = item.get("expires")
        if expires is None:
            expires = item.get("expiry")
        try:
            exp_value = float(str(expires)) if expires is not None else None
        except (TypeError, ValueError):
            exp_value = None
        cookies.append(CookieInfo(name=str(name), value=str(value), expires=exp_value))
    return cookies


def cookies_to_header(cookies: list[CookieInfo]) -> str:
    if not cookies:
        return ""
    return "; ".join(f"{cookie.name}={cookie.value}" for cookie in cookies)


def get_state_info(base_url: str, storage_state_path: str | None) -> dict[str, Any]:
    path_value = (storage_state_path or "").strip()
    if not path_value:
        return {
            "status": "missing",
            "message": "未填写状态文件",
        }

    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {
            "status": "not_found",
            "message": "状态文件不存在",
        }

    try:
        payload = load_state_payload(path)
    except Exception:
        return {
            "status": "invalid",
            "message": "状态文件无法解析",
        }

    host = (urlparse(normalize_base_url(base_url)).hostname or "").lower()
    cookies = collect_cookies(payload, host or None)
    if not cookies:
        fallback_cookies = collect_cookies(payload, None)
        if not fallback_cookies:
            return {
                "status": "no_cookie",
                "message": "状态文件中没有可用 cookie",
            }
        return {
            "status": "no_domain",
            "message": "没有匹配域名的 cookie",
        }

    expires_values = [cookie.expires for cookie in cookies if cookie.expires is not None and cookie.expires > 0]
    cookie_name = cookies[0].name if cookies else None
    if not expires_values:
        return {
            "status": "session",
            "cookie_name": cookie_name,
            "message": "Cookie 无过期时间（会话）",
        }

    expires_at = max(expires_values)
    now = datetime.now(timezone.utc).timestamp()
    remaining = int(expires_at - now)
    expires_text = datetime.fromtimestamp(expires_at, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    if remaining <= 0:
        return {
            "status": "expired",
            "cookie_name": cookie_name,
            "expires_at": expires_at,
            "expires_at_text": expires_text,
            "expires_in_sec": remaining,
            "message": "Cookie 已过期",
        }

    return {
        "status": "valid",
        "cookie_name": cookie_name,
        "expires_at": expires_at,
        "expires_at_text": expires_text,
        "expires_in_sec": remaining,
        "message": "Cookie 有效",
    }


def default_state_path(base_url: str, root_dir: Path) -> Path:
    host = (urlparse(normalize_base_url(base_url)).hostname or "site").replace(".", "_")
    return root_dir / f"{host}_state.json"


def save_state_payload(base_url: str, payload: bytes, root_dir: Path) -> Path:
    if len(payload) > MAX_STATE_FILE_BYTES:
        raise ValueError("file_too_large")

    try:
        parsed = json.loads(payload.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("json_invalid") from exc

    if not isinstance(parsed, dict):
        raise ValueError("json_invalid")

    host = (urlparse(normalize_base_url(base_url)).hostname or "").lower()
    cookies = collect_cookies(parsed, host or None)
    if not cookies:
        raise ValueError("cookie_missing")

    root_dir.mkdir(parents=True, exist_ok=True)
    out_path = default_state_path(base_url, root_dir)
    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
