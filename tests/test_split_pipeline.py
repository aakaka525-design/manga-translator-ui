from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import manga_translator.server.routes.v1_translate as v1_translate
from manga_translator.server.core.ctx_cache import CtxCache


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_ctx_cache_reason_codes():
    cache = CtxCache(max_size=4, default_ttl=30)
    ttl = cache.put("task-a", "sha256:abc", {"value": 1})
    assert ttl == 30

    item, reason = cache.get("task-a", "sha256:abc")
    assert reason == "OK"
    assert item == {"value": 1}

    item, reason = cache.get("task-a", "sha256:def")
    assert item is None
    assert reason == "IMAGE_HASH_MISMATCH"

    cache._store["task-a"] = (time.time() - 1, "sha256:abc", {"value": 1})
    item, reason = cache.get("task-a", "sha256:abc")
    assert item is None
    assert reason == "TASK_EXPIRED"

    item, reason = cache.get("missing", "sha256:abc")
    assert item is None
    assert reason == "CACHE_MISS"


def test_internal_detect_returns_region_index(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MANGA_INTERNAL_API_TOKEN", "token-1")

    async def _fake_detect_payload(*_args, **_kwargs):
        return {
            "task_id": "task-1",
            "ttl_seconds": 300,
            "image_hash": "sha256:abc",
            "regions": [
                {"text": "hello"},
                {"text": "world"},
            ],
            "from_lang": "JPN",
            "elapsed_ms": {"detect": 10, "ocr": 20, "total": 30},
        }

    monkeypatch.setattr(v1_translate, "_split_detect_payload", _fake_detect_payload)

    app = FastAPI()
    app.include_router(v1_translate.internal_router)

    with TestClient(app) as client:
        response = client.post(
            "/internal/translate/detect",
            headers={"X-Internal-Token": "token-1"},
            files={"image": ("001.jpg", b"raw-image", "image/jpeg")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["regions_count"] == 2
    assert [region["region_index"] for region in payload["regions"]] == [0, 1]


def test_internal_render_state_machine(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MANGA_INTERNAL_API_TOKEN", "token-1")
    monkeypatch.delenv("MANGA_CLOUDRUN_COMPUTE_ONLY", raising=False)

    async def _fake_render_payload(*_args, **_kwargs):
        return b"rendered-image", {"regions_count": 1, "stage_elapsed_ms": {"render": 11.0}}

    monkeypatch.setattr(v1_translate, "_split_render_payload", _fake_render_payload)

    app = FastAPI()
    app.include_router(v1_translate.internal_router)

    with TestClient(app) as client:
        missing = client.post(
            "/internal/translate/render",
            headers={"X-Internal-Token": "token-1"},
            json={"task_id": "missing", "image_hash": "sha256:x", "translated_regions": []},
        )
        assert missing.status_code == 404
        assert missing.json()["detail"] == "CACHE_MISS"

        v1_translate._SPLIT_CTX_CACHE.put(
            "task-1",
            "sha256:ok",
            {"ctx": {"text_regions": [object()]}, "config": object()},
        )
        mismatch = client.post(
            "/internal/translate/render",
            headers={"X-Internal-Token": "token-1"},
            json={"task_id": "task-1", "image_hash": "sha256:bad", "translated_regions": []},
        )
        assert mismatch.status_code == 422
        assert mismatch.json()["detail"] == "IMAGE_HASH_MISMATCH"

        v1_translate._SPLIT_CTX_CACHE.put(
            "task-2",
            "sha256:ok",
            {"ctx": {"text_regions": [object()]}, "config": object()},
        )
        v1_translate._SPLIT_CTX_CACHE._store["task-2"] = (
            time.time() - 1,
            "sha256:ok",
            {"ctx": {"text_regions": [object()]}, "config": object()},
        )
        expired = client.post(
            "/internal/translate/render",
            headers={"X-Internal-Token": "token-1"},
            json={"task_id": "task-2", "image_hash": "sha256:ok", "translated_regions": []},
        )
        assert expired.status_code == 410
        assert expired.json()["detail"] == "TASK_EXPIRED"

        v1_translate._SPLIT_CTX_CACHE.put(
            "task-3",
            "sha256:ok",
            {"ctx": {"text_regions": [object()]}, "config": object()},
        )
        invalid = client.post(
            "/internal/translate/render",
            headers={"X-Internal-Token": "token-1"},
            json={
                "task_id": "task-3",
                "image_hash": "sha256:ok",
                "translated_regions": [{"region_index": 5, "translation": "x"}],
            },
        )
        assert invalid.status_code == 400
        assert invalid.json()["detail"] == "RENDER_INPUT_INVALID"


@pytest.mark.anyio
async def test_cloudrun_split_falls_back_to_unified_on_cache_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    image_path = tmp_path / "001.jpg"
    out_path = tmp_path / "out.jpg"
    image_path.write_bytes(b"raw")

    executor = v1_translate.CloudRunTranslateExecutor(
        endpoint="https://example.com",
        timeout_sec=10,
        pipeline_mode="split",
    )

    async def _fake_split(*_args, **_kwargs):
        raise v1_translate.CloudRunExecutionError(
            status_code=404,
            message="CACHE_MISS",
            failure_stage="render",
            retryable=False,
        )

    async def _fake_unified(*_args, **_kwargs):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"translated")
        return {
            "output_path": str(out_path),
            "regions_count": 1,
            "output_changed": True,
            "fallback_used": False,
            "fallback_reason": None,
            "stage_elapsed_ms": {"total": 10.0},
            "failure_stage": None,
            "execution_backend": "cloudrun",
            "remote_elapsed_ms": 10,
            "cold_start": False,
            "page_translation_text": "ok",
            "primary_model": "gemini-3-flash-preview",
            "fallback_model": "gemini-2.5-flash",
            "selected_model": "gemini-3-flash-preview",
            "model_fallback_reason": None,
            "pipeline_mode": "fallback_to_unified",
        }

    monkeypatch.setattr(executor, "_translate_via_split_pipeline", _fake_split)
    monkeypatch.setattr(executor, "_translate_via_unified_pipeline", _fake_unified)

    result = await executor.translate_page(
        image_path=image_path,
        output_path=out_path,
        source_language="en",
        target_language="zh",
        context_translations=["ctx-a"],
    )
    assert result["pipeline_mode"] == "fallback_to_unified"
    assert out_path.exists()


@pytest.mark.anyio
async def test_split_translate_semaphore_serializes_phase2(monkeypatch: pytest.MonkeyPatch):
    active = 0
    max_active = 0

    async def _fake_translate(*_args, **_kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return ["ok"]

    monkeypatch.setattr(v1_translate, "_split_translate_texts_impl", _fake_translate)

    await asyncio.gather(
        v1_translate._translate_texts_for_split(["a"], None, None, "JPN", []),
        v1_translate._translate_texts_for_split(["b"], None, None, "JPN", []),
    )
    assert max_active == 1
