from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

import manga_translator.server.routes.v1_translate as v1_translate


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_demo_chapter(root: Path, page_count: int = 2) -> tuple[Path, Path]:
    raw_dir = root / "raw"
    results_dir = root / "results"
    chapter_dir = raw_dir / "demo_manga" / "chapter_diag"
    chapter_dir.mkdir(parents=True, exist_ok=True)

    for idx in range(1, page_count + 1):
        image_path = chapter_dir / f"{idx:03d}.jpg"
        image = Image.new("RGB", (64, 64), color=(240, 240, 240))
        image.save(image_path, format="JPEG")

    return raw_dir, results_dir


@pytest.mark.anyio
async def test_chapter_complete_event_contains_pipeline_and_stage_timings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    raw_dir, results_dir = _build_demo_chapter(tmp_path, page_count=2)
    v1_translate.library_service.raw_dir = raw_dir
    v1_translate.library_service.results_dir = results_dir

    async def _fake_batch(request, images, page_concurrency):
        _ = (request, page_concurrency)
        outputs = []
        for image_path in images:
            output_path = results_dir / "demo_manga" / "chapter_diag" / image_path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"translated")
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

    events: list[dict] = []

    async def _fake_publish(payload):
        events.append(payload)

    monkeypatch.setattr(v1_translate, "_translate_chapter_batch_pipeline", _fake_batch)
    monkeypatch.setattr(v1_translate.v1_event_bus, "publish", _fake_publish)
    monkeypatch.setenv("MANGA_V1_CHAPTER_EXECUTION_MODE", "batch_pipeline")
    monkeypatch.setenv("MANGA_V1_RUNTIME_PROFILE", "basic")

    request = v1_translate.ChapterTranslateRequest(manga_id="demo_manga", chapter_id="chapter_diag")
    await v1_translate._process_chapter_job(request)

    chapter_complete = next(event for event in events if event.get("type") == "chapter_complete")
    assert chapter_complete["status"] == "success"
    assert chapter_complete["pipeline"] == "batch_pipeline"
    assert isinstance(chapter_complete["stage_elapsed_ms"], dict)
    assert "translate" in chapter_complete["stage_elapsed_ms"]
    assert "total" in chapter_complete["stage_elapsed_ms"]


@pytest.mark.anyio
async def test_failed_progress_event_contains_failure_stage(monkeypatch: pytest.MonkeyPatch):
    events: list[dict] = []

    async def _fake_publish(payload):
        events.append(payload)

    monkeypatch.setattr(v1_translate.v1_event_bus, "publish", _fake_publish)

    request = v1_translate.ChapterTranslateRequest(manga_id="demo_manga", chapter_id="chapter_diag")
    ok = await v1_translate._publish_page_result(
        request=request,
        image_path=Path("001.jpg"),
        task_id="task-1",
        result=None,
        error=RuntimeError("translate failed"),
        pipeline="single_page",
    )

    assert ok is False
    failed_event = events[-1]
    assert failed_event["status"] == "failed"
    assert failed_event["stage"] == "failed"
    assert failed_event["failure_stage"] == "translate"


@pytest.mark.anyio
async def test_failed_progress_event_contains_cloudrun_status_code(monkeypatch: pytest.MonkeyPatch):
    events: list[dict] = []

    async def _fake_publish(payload):
        events.append(payload)

    monkeypatch.setattr(v1_translate.v1_event_bus, "publish", _fake_publish)

    request = v1_translate.ChapterTranslateRequest(manga_id="demo_manga", chapter_id="chapter_diag")
    ok = await v1_translate._publish_page_result(
        request=request,
        image_path=Path("001.jpg"),
        task_id="task-1",
        result={"stage_elapsed_ms": {"executor_attempts": 2}},
        error=v1_translate.CloudRunExecutionError(
            status_code=429,
            message="cloudrun status=429",
            failure_stage="remote",
            retryable=True,
        ),
        pipeline="single_page",
        execution_backend="cloudrun",
    )

    assert ok is False
    failed_event = events[-1]
    assert failed_event["status"] == "failed"
    assert failed_event["failure_stage"] == "remote"
    assert "status=429" in failed_event["error_message"]
