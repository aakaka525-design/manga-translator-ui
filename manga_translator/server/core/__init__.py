"""Core package lazy exports.

Avoid eager importing heavyweight modules during lightweight imports/tests.
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "account_service",
    "audit_service",
    "auth",
    "cleanup_scheduler",
    "cleanup_service",
    "config_management_service",
    "config_manager",
    "env_service",
    "group_management_service",
    "group_service",
    "history_service",
    "library_service",
    "log_management_service",
    "logging_manager",
    "middleware",
    "models",
    "permission_calculator",
    "permission_integration",
    "permission_migration",
    "permission_service",
    "permission_service_v2",
    "persistence",
    "quota_scheduler",
    "quota_service",
    "resource_service",
    "response_utils",
    "search_service",
    "session_security_service",
    "session_service",
    "system_init",
    "task_manager",
    "translation_integration",
    "v1_event_bus",
}

_ATTR_HINTS = {
    "AccountService": "account_service",
    "AuditService": "audit_service",
    "PermissionService": "permission_service",
    "SessionService": "session_service",
    "init_middleware_services": "middleware",
    "require_auth": "middleware",
    "require_admin": "middleware",
    "init_system": "system_init",
    "SystemInitializer": "system_init",
}


__all__ = sorted(_SUBMODULES) + sorted(_ATTR_HINTS)


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(f"manga_translator.server.core.{name}")
        globals()[name] = module
        return module

    hinted_module = _ATTR_HINTS.get(name)
    if hinted_module:
        module = import_module(f"manga_translator.server.core.{hinted_module}")
        value = getattr(module, name)
        globals()[name] = value
        return value

    for module_name in _SUBMODULES:
        module = import_module(f"manga_translator.server.core.{module_name}")
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value

    raise AttributeError(f"module 'manga_translator.server.core' has no attribute {name!r}")
