"""Route module lazy exports."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "translation_router": ("translation", "router"),
    "admin_router": ("admin", "router"),
    "config_router": ("config", "router"),
    "files_router": ("files", "router"),
    "web_router": ("web", "router"),
    "users_router": ("users", "router"),
    "audit_router": ("audit", "router"),
    "auth_router": ("auth", "router"),
    "init_auth_services": ("auth", "init_auth_services"),
    "groups_router": ("groups", "router"),
    "resources_router": ("resources", "router"),
    "init_resource_routes": ("resources", "init_resource_routes"),
    "history_router": ("history", "router"),
    "init_history_routes": ("history", "init_history_routes"),
    "quota_router": ("quota", "router"),
    "init_quota_routes": ("quota", "init_quota_routes"),
    "cleanup_router": ("cleanup", "router"),
    "init_cleanup_routes": ("cleanup", "init_cleanup_routes"),
    "init_auto_cleanup_scheduler": ("cleanup", "init_auto_cleanup_scheduler"),
    "config_management_router": ("config_management", "router"),
    "logs_router": ("logs", "logs_router"),
    "locales_router": ("locales", "router"),
    "init_locales_routes": ("locales", "init_locales_routes"),
    "sessions_router": ("sessions", "router"),
    "v1_manga_router": ("v1_manga", "router"),
    "v1_translate_router": ("v1_translate", "router"),
    "v1_scraper_router": ("v1_scraper", "router"),
    "v1_parser_router": ("v1_parser", "router"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'manga_translator.server.routes' has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(f"manga_translator.server.routes.{module_name}")

    try:
        value = getattr(module, attr_name)
    except AttributeError:
        if name in {"cleanup_router", "init_cleanup_routes", "init_auto_cleanup_scheduler"}:
            value = None
        else:
            raise

    globals()[name] = value
    return value
