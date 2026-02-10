from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

from PIL import Image

import manga_translator.server.request_extraction as request_extraction


class _FakeTranslator:
    def __init__(self) -> None:
        self.single_calls = 0
        self.batch_calls = 0
        self.cancel_callback = None

    def set_cancel_check_callback(self, callback) -> None:
        self.cancel_callback = callback

    async def translate(self, pil_image, config):
        _ = (pil_image, config)
        self.single_calls += 1
        return SimpleNamespace(result=None)

    async def translate_batch(self, images_with_configs, batch_size):
        _ = batch_size
        self.batch_calls += 1
        return [SimpleNamespace(result=None) for _ in images_with_configs]


def _patch_task_manager(monkeypatch, translator: _FakeTranslator) -> None:
    monkeypatch.setattr(
        "manga_translator.server.core.task_manager.get_global_translator",
        lambda: translator,
    )
    monkeypatch.setattr(
        "manga_translator.server.core.task_manager.begin_translation_operation",
        lambda: None,
    )
    monkeypatch.setattr(
        "manga_translator.server.core.task_manager.end_translation_operation",
        lambda: None,
    )
    monkeypatch.setattr(
        "manga_translator.server.core.task_manager.cleanup_after_request",
        lambda *args, **kwargs: False,
    )


def test_run_translate_sync_reuses_thread_event_loop(monkeypatch):
    translator = _FakeTranslator()
    _patch_task_manager(monkeypatch, translator)

    monkeypatch.setattr(request_extraction, "_TRANSLATION_THREAD_STATE", threading.local())

    real_new_event_loop = asyncio.new_event_loop
    counters = {"new_event_loop_calls": 0}

    def _counted_new_event_loop():
        counters["new_event_loop_calls"] += 1
        return real_new_event_loop()

    monkeypatch.setattr(request_extraction.asyncio, "new_event_loop", _counted_new_event_loop)

    image = Image.new("RGB", (8, 8), color=(255, 255, 255))
    config = SimpleNamespace()
    try:
        request_extraction._run_translate_sync(image, config)
        request_extraction._run_translate_sync(image, config)
    finally:
        image.close()
        request_extraction._close_translation_event_loop_for_current_thread()

    assert translator.single_calls == 2
    assert counters["new_event_loop_calls"] == 1


def test_run_translate_batch_sync_reuses_thread_event_loop(monkeypatch):
    translator = _FakeTranslator()
    _patch_task_manager(monkeypatch, translator)

    monkeypatch.setattr(request_extraction, "_TRANSLATION_THREAD_STATE", threading.local())

    real_new_event_loop = asyncio.new_event_loop
    counters = {"new_event_loop_calls": 0}

    def _counted_new_event_loop():
        counters["new_event_loop_calls"] += 1
        return real_new_event_loop()

    monkeypatch.setattr(request_extraction.asyncio, "new_event_loop", _counted_new_event_loop)

    image = Image.new("RGB", (8, 8), color=(255, 255, 255))
    config = SimpleNamespace()
    images_with_configs = [(image, config), (image, config)]
    try:
        request_extraction._run_translate_batch_sync(images_with_configs, batch_size=2)
        request_extraction._run_translate_batch_sync(images_with_configs, batch_size=2)
    finally:
        image.close()
        request_extraction._close_translation_event_loop_for_current_thread()

    assert translator.batch_calls == 2
    assert counters["new_event_loop_calls"] == 1
