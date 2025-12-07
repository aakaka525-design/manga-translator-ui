"""
Data repository classes for JSON file storage.
"""

from .base_repository import BaseJSONRepository
from .resource_repository import ResourceRepository
from .translation_repository import TranslationRepository
from .permission_repository import PermissionRepository
from .cleanup_repository import CleanupRepository
from .config_repository import ConfigRepository
from .quota_repository import QuotaRepository
from .log_repository import LogRepository

__all__ = [
    'BaseJSONRepository',
    'ResourceRepository',
    'TranslationRepository',
    'PermissionRepository',
    'CleanupRepository',
    'ConfigRepository',
    'QuotaRepository',
    'LogRepository',
]
