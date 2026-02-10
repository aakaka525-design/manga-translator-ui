from __future__ import annotations

import asyncio
import json
import io
import time
from types import SimpleNamespace
from pathlib import Path

import pytest
from PIL import Image

from manga_translator.config import Config
import manga_translator.server.routes.v1_translate as v1_translate
from manga_translator.server.core import task_manager


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_demo_chapter(root: Path, page_count: int = 3) -> tuple[Path, Path]:
    raw_dir = root / "raw"
    results_dir = root / "results"
    chapter_dir = raw_dir / "demo_manga" / "chapter_perf"
    chapter_dir.mkdir(parents=True, exist_ok=True)

    for idx in range(1, page_count + 1):
        image_path = chapter_dir / f"{idx:03d}.jpg"
        image = Image.new("RGB", (1280, 720), color=(245, 245, 245))
        image.save(image_path, format="JPEG", quality=88)

    return raw_dir, results_dir


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, int(round(0.95 * (len(sorted_values) - 1)))))
    return sorted_values[index]


async def _run_mock_chapter_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    delays_ms: dict[str, int],
    concurrency: int,
) -> dict[str, float]:
    raw_dir, results_dir = _build_demo_chapter(tmp_path)
    v1_translate.library_service.raw_dir = raw_dir
    v1_translate.library_service.results_dir = results_dir

    # Keep this helper focused on single-page path perf characteristics.
    monkeypatch.setenv("MANGA_V1_CHAPTER_EXECUTION_MODE", "single_page")
    monkeypatch.setenv("MANGA_V1_CHAPTER_PAGE_CONCURRENCY", str(concurrency))

    page_durations: list[float] = []
    publish_ts: list[float] = []

    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (source_language, target_language)
        start = time.perf_counter()
        await asyncio.sleep(delays_ms[image_path.name] / 1000.0)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"translated::{image_path.name}".encode("utf-8"))
        end = time.perf_counter()
        page_durations.append((end - start) * 1000.0)
        return {
            "output_path": str(output_path),
            "regions_count": 1,
            "output_changed": True,
            "fallback_used": False,
        }

    async def _fake_publish(_payload):
        publish_ts.append(time.perf_counter())

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_translate)
    monkeypatch.setattr(v1_translate.v1_event_bus, "publish", _fake_publish)

    req = v1_translate.ChapterTranslateRequest(manga_id="demo_manga", chapter_id="chapter_perf")
    chapter_start = time.perf_counter()
    await v1_translate._process_chapter_job(req)
    chapter_end = time.perf_counter()

    chapter_total_ms = (chapter_end - chapter_start) * 1000.0
    page_avg_ms = sum(page_durations) / len(page_durations)
    p95_page_ms = _p95(page_durations)
    gaps = [
        (publish_ts[idx] - publish_ts[idx - 1]) * 1000.0
        for idx in range(1, len(publish_ts))
    ]
    event_gap_ms = sum(gaps) / len(gaps) if gaps else 0.0
    return {
        "chapter_total_ms": chapter_total_ms,
        "page_avg_ms": page_avg_ms,
        "p95_page_ms": p95_page_ms,
        "event_gap_ms": event_gap_ms,
    }


@pytest.mark.anyio
async def test_single_page_mode_serializes_even_if_higher_concurrency_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    # warmup
    await _run_mock_chapter_job(
        monkeypatch,
        tmp_path / "warmup",
        delays_ms={"001.jpg": 30, "002.jpg": 30, "003.jpg": 30},
        concurrency=1,
    )

    serial_metrics = await _run_mock_chapter_job(
        monkeypatch,
        tmp_path / "serial",
        delays_ms={"001.jpg": 30, "002.jpg": 30, "003.jpg": 30},
        concurrency=1,
    )
    parallel_metrics = await _run_mock_chapter_job(
        monkeypatch,
        tmp_path / "parallel",
        delays_ms={"001.jpg": 30, "002.jpg": 30, "003.jpg": 30},
        concurrency=3,
    )

    assert serial_metrics["chapter_total_ms"] > 0
    assert parallel_metrics["chapter_total_ms"] > 0
    # Stability-first policy: single_page mode is serialized to avoid shared-state races.
    assert parallel_metrics["chapter_total_ms"] >= serial_metrics["chapter_total_ms"] * 0.8
    assert parallel_metrics["chapter_total_ms"] <= serial_metrics["chapter_total_ms"] * 1.5


@pytest.mark.anyio
async def test_single_page_tail_latency_is_consistent_when_concurrency_increases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    serial_metrics = await _run_mock_chapter_job(
        monkeypatch,
        tmp_path / "serial_tail",
        delays_ms={"001.jpg": 30, "002.jpg": 30, "003.jpg": 80},
        concurrency=1,
    )
    parallel_metrics = await _run_mock_chapter_job(
        monkeypatch,
        tmp_path / "parallel_tail",
        delays_ms={"001.jpg": 30, "002.jpg": 30, "003.jpg": 80},
        concurrency=3,
    )

    assert parallel_metrics["chapter_total_ms"] >= serial_metrics["chapter_total_ms"] * 0.8
    assert parallel_metrics["chapter_total_ms"] <= serial_metrics["chapter_total_ms"] * 1.5
    assert parallel_metrics["p95_page_ms"] >= 80.0


@pytest.mark.anyio
async def test_real_smoke_single_page_skips_when_runtime_unavailable(tmp_path: Path):
    source_path = tmp_path / "source.jpg"
    output_path = tmp_path / "output.jpg"

    image = Image.new("RGB", (1280, 720), color=(240, 240, 240))
    image.save(source_path, format="JPEG", quality=88)

    result = await v1_translate._translate_single_image(
        source_path,
        output_path,
        source_language=None,
        target_language="zh",
    )

    if result.get("fallback_used"):
        reason = result.get("fallback_reason") or "runtime unavailable"
        pytest.skip(f"real_smoke_single_page skipped: {reason}")

    assert output_path.exists()
    assert result.get("output_path") == str(output_path)
    assert result.get("regions_count") is not None


def test_chapter_page_concurrency_is_clamped_by_max_concurrent_tasks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MANGA_V1_CHAPTER_PAGE_CONCURRENCY", raising=False)
    monkeypatch.setattr(
        task_manager,
        "get_server_config",
        lambda: {"chapter_page_concurrency": 5, "max_concurrent_tasks": 2},
    )
    assert v1_translate._resolve_chapter_page_concurrency() == 2


@pytest.mark.anyio
async def test_metrics_shape_is_complete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    metrics = await _run_mock_chapter_job(
        monkeypatch,
        tmp_path / "shape",
        delays_ms={"001.jpg": 30, "002.jpg": 30, "003.jpg": 30},
        concurrency=1,
    )
    assert set(metrics.keys()) == {"chapter_total_ms", "page_avg_ms", "p95_page_ms", "event_gap_ms"}
    assert all(value >= 0 for value in metrics.values())


class _TrackedDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1
        super().clear()


class _TrackedList(list):
    def __init__(self, *args):
        super().__init__(*args)
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1
        super().clear()


def test_cleanup_after_request_is_throttled_and_deferred_when_inflight(monkeypatch: pytest.MonkeyPatch):
    translator = SimpleNamespace(
        _batch_contexts=_TrackedDict({"k": "v"}),
        _batch_configs=_TrackedDict({"k": "v"}),
        _current_image_context=object(),
        _saved_image_contexts=_TrackedDict({"k": "v"}),
        all_page_translations=_TrackedList(["x"]),
        _original_page_texts=_TrackedList(["y"]),
        _cancel_check_callback=object(),
    )

    monkeypatch.setattr(task_manager, "_global_translator", translator)
    monkeypatch.setattr(task_manager, "_cleanup_request_counter", 0, raising=False)
    monkeypatch.setattr(task_manager, "_inflight_translation_ops", 0, raising=False)
    monkeypatch.setitem(task_manager.server_config, "cleanup_interval_requests", 3)
    monkeypatch.setattr(task_manager, "_is_low_memory_pressure", lambda: False, raising=False)

    task_manager.cleanup_after_request()
    task_manager.cleanup_after_request()
    assert translator._batch_contexts.clear_calls == 0

    monkeypatch.setattr(task_manager, "_inflight_translation_ops", 1, raising=False)
    task_manager.cleanup_after_request()
    assert translator._batch_contexts.clear_calls == 0

    monkeypatch.setattr(task_manager, "_inflight_translation_ops", 0, raising=False)
    task_manager.cleanup_after_request()
    assert translator._batch_contexts.clear_calls == 1
    assert translator._batch_configs.clear_calls == 1
    assert translator._saved_image_contexts.clear_calls == 1
    assert translator.all_page_translations.clear_calls == 1
    assert translator._original_page_texts.clear_calls == 1
    assert translator._cancel_check_callback is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("execution_mode", "expected_single_calls", "expected_batch_calls"),
    [
        ("single_page", 2, 0),
        ("batch_pipeline", 0, 1),
    ],
)
async def test_chapter_execution_mode_switches_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    execution_mode: str,
    expected_single_calls: int,
    expected_batch_calls: int,
):
    raw_dir, results_dir = _build_demo_chapter(tmp_path, page_count=2)
    v1_translate.library_service.raw_dir = raw_dir
    v1_translate.library_service.results_dir = results_dir

    calls = {"single": 0, "batch": 0}

    async def _fake_single(image_path, output_path, source_language, target_language):
        _ = (source_language, target_language)
        calls["single"] += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"single::{image_path.name}".encode("utf-8"))
        return {
            "output_path": str(output_path),
            "regions_count": 1,
            "output_changed": True,
            "fallback_used": False,
        }

    async def _fake_batch(request, images, page_concurrency):
        _ = (request, page_concurrency)
        calls["batch"] += 1
        outputs = []
        for image_path in images:
            output_path = results_dir / "demo_manga" / "chapter_perf" / image_path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(f"batch::{image_path.name}".encode("utf-8"))
            outputs.append(
                (
                    image_path,
                    {
                        "output_path": str(output_path),
                        "regions_count": 1,
                        "output_changed": True,
                        "fallback_used": False,
                    },
                    None,
                )
            )
        return outputs

    async def _fake_publish(_payload):
        return None

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_single)
    monkeypatch.setattr(v1_translate, "_translate_chapter_batch_pipeline", _fake_batch)
    monkeypatch.setattr(v1_translate.v1_event_bus, "publish", _fake_publish)
    monkeypatch.setenv("MANGA_V1_CHAPTER_EXECUTION_MODE", execution_mode)
    monkeypatch.setenv("MANGA_V1_CHAPTER_PAGE_CONCURRENCY", "2")

    req = v1_translate.ChapterTranslateRequest(manga_id="demo_manga", chapter_id="chapter_perf")
    await v1_translate._process_chapter_job(req)

    assert calls["single"] == expected_single_calls
    assert calls["batch"] == expected_batch_calls


@pytest.mark.anyio
async def test_chapter_auto_mode_prefers_batch_pipeline_for_gemini_hq(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    raw_dir, results_dir = _build_demo_chapter(tmp_path, page_count=2)
    v1_translate.library_service.raw_dir = raw_dir
    v1_translate.library_service.results_dir = results_dir

    calls = {"single": 0, "batch": 0}

    class _TranslatorConfig:
        translator = "gemini_hq"
        attempts = 1
        target_lang = "CHS"
        skip_lang = None

    class _Config:
        translator = _TranslatorConfig()

    async def _fake_single(image_path, output_path, source_language, target_language):
        _ = (source_language, target_language)
        calls["single"] += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"single::{image_path.name}".encode("utf-8"))
        return {
            "output_path": str(output_path),
            "regions_count": 1,
            "output_changed": True,
            "fallback_used": False,
        }

    async def _fake_batch(request, images, page_concurrency):
        _ = (request, images, page_concurrency)
        calls["batch"] += 1
        return []

    async def _fake_publish(_payload):
        return None

    monkeypatch.setattr(
        "manga_translator.server.core.config_manager.load_default_config",
        lambda: _Config(),
    )
    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_single)
    monkeypatch.setattr(v1_translate, "_translate_chapter_batch_pipeline", _fake_batch)
    monkeypatch.setattr(v1_translate.v1_event_bus, "publish", _fake_publish)
    monkeypatch.setenv("MANGA_V1_CHAPTER_EXECUTION_MODE", "auto")
    monkeypatch.setenv("MANGA_V1_CHAPTER_PAGE_CONCURRENCY", "3")

    req = v1_translate.ChapterTranslateRequest(manga_id="demo_manga", chapter_id="chapter_perf")
    await v1_translate._process_chapter_job(req)

    assert calls["single"] == 0
    assert calls["batch"] == 1


def test_example_config_contains_chapter_page_concurrency():
    repo_root = Path(__file__).resolve().parents[1]
    example_path = repo_root / "examples" / "config-example.json"
    payload = json.loads(example_path.read_text(encoding="utf-8"))

    assert "chapter_page_concurrency" in payload
    assert isinstance(payload["chapter_page_concurrency"], int)
    assert payload["chapter_page_concurrency"] > 0

    parsed = Config.model_validate(payload)
    assert parsed is not None
