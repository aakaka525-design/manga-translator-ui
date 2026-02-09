"""Manga Translator Web API Server package.

This module avoids eager imports so utility modules can be imported in
lightweight contexts (e.g., unit tests) without initializing the full server.
"""

from __future__ import annotations

from importlib import import_module

__version__ = "2.0.0"
__author__ = "Manga Translator Team"

__all__ = [
    "app",
    "run_server",
    "TranslateRequest",
    "BatchTranslateRequest",
    "get_ctx",
    "get_batch_ctx",
    "while_streaming",
    "ExecutorInstance",
    "executor_instances",
    "task_queue",
    "QueueElement",
    "BatchQueueElement",
    "TranslationResponse",
    "to_translation",
]


def __getattr__(name: str):
    if name in {"app", "run_server"}:
        module = import_module("manga_translator.server.main")
        return getattr(module, name)
    if name in {"TranslateRequest", "BatchTranslateRequest", "get_ctx", "get_batch_ctx", "while_streaming"}:
        module = import_module("manga_translator.server.request_extraction")
        return getattr(module, name)
    if name in {"ExecutorInstance", "executor_instances"}:
        module = import_module("manga_translator.server.instance")
        return getattr(module, name)
    if name in {"task_queue", "QueueElement", "BatchQueueElement"}:
        module = import_module("manga_translator.server.myqueue")
        return getattr(module, name)
    if name in {"TranslationResponse", "to_translation"}:
        module = import_module("manga_translator.server.to_json")
        return getattr(module, name)
    raise AttributeError(f"module 'manga_translator.server' has no attribute {name!r}")
