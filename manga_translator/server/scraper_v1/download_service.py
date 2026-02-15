"""Download orchestration service for scraper tasks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

from .base import ProviderContext
from .helpers import infer_output_extension, safe_name
from .http_client import DownloadResult, ScraperHttpClient
from .models import ScraperDownloadRequest
from .providers import BrowserUnavailableError, ProviderAdapter
from .mangaforfree import CloudflareChallengeError


SetTaskStateFn = Callable[..., asyncio.Future | None]


class DownloadService:
    def __init__(
        self,
        *,
        raw_dir: Path,
        http_client: ScraperHttpClient,
        set_task_state: Callable[..., asyncio.Future | None],
        image_retry_delays: tuple[float, ...] = (0.5, 1.0, 2.0),
        task_retry_delay_sec: int = 15,
        max_task_retries: int = 2,
    ):
        self.raw_dir = raw_dir
        self.http_client = http_client
        self._set_task_state = set_task_state
        self.image_retry_delays = image_retry_delays
        self.task_retry_delay_sec = max(1, int(task_retry_delay_sec))
        self.max_task_retries = max(0, int(max_task_retries))
        self._active_tasks: set[asyncio.Task] = set()

    def _default_chapter_url(self, provider: ProviderAdapter, base_url: str, manga_id: str, chapter_id: str) -> str:
        if provider.key == "toongod":
            return urljoin(base_url, f"/webtoon/{manga_id}/{chapter_id}/")
        return urljoin(base_url, f"/manga/{manga_id}/{chapter_id}/")

    async def _set_state(self, *args, **kwargs):
        result = self._set_task_state(*args, **kwargs)
        if asyncio.iscoroutine(result):
            await result

    def submit(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def shutdown(self) -> None:
        if not self._active_tasks:
            return
        for task in list(self._active_tasks):
            task.cancel()
        await asyncio.gather(*self._active_tasks, return_exceptions=True)
        self._active_tasks.clear()

    async def run_download_task(
        self,
        task_id: str,
        req: ScraperDownloadRequest,
        provider: ProviderAdapter,
        context: ProviderContext,
        *,
        retry_count: int = 0,
        max_retries: int | None = None,
    ) -> None:
        max_retries = self.max_task_retries if max_retries is None else int(max_retries)
        await self._set_state(
            task_id,
            status="running",
            message="下载中...",
            retry_count=retry_count,
            max_retries=max_retries,
            next_retry_at=None,
            started_at=None,
            progress_completed=0,
            progress_total=0,
        )

        manga_id = safe_name(req.manga.id or req.manga.title or "manga")
        chapter_id = safe_name(req.chapter.id or req.chapter.title or "chapter")
        chapter_url = req.chapter.url or self._default_chapter_url(provider, context.base_url, req.manga.id, req.chapter.id)

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        output_dir = self.raw_dir / manga_id / chapter_id
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            image_urls = await provider.reader_images(context, chapter_url)
        except BrowserUnavailableError as exc:
            await self._set_state(
                task_id,
                status="error",
                message=f"浏览器环境不可用: {exc}",
                report={"success_count": 0, "failed_count": 0, "total_count": 0},
                error_code="SCRAPER_BROWSER_UNAVAILABLE",
                finished=True,
                retry_count=retry_count,
                max_retries=max_retries,
                last_error=str(exc),
            )
            return
        except CloudflareChallengeError as exc:
            await self._set_state(
                task_id,
                status="error",
                message=str(exc),
                report={"success_count": 0, "failed_count": 0, "total_count": 0},
                error_code="SCRAPER_AUTH_CHALLENGE",
                finished=True,
                retry_count=retry_count,
                max_retries=max_retries,
                last_error=str(exc),
            )
            return
        except Exception as exc:  # noqa: BLE001
            await self._set_state(
                task_id,
                status="error",
                message=f"抓取失败: {exc}",
                report={"success_count": 0, "failed_count": 0, "total_count": 0},
                error_code="SCRAPER_DOWNLOAD_FAILED",
                finished=True,
                retry_count=retry_count,
                max_retries=max_retries,
                last_error=str(exc),
            )
            return

        if not image_urls:
            await self._set_state(
                task_id,
                status="error",
                message="章节未返回可下载图片",
                report={"success_count": 0, "failed_count": 0, "total_count": 0},
                error_code="SCRAPER_IMAGE_EMPTY",
                finished=True,
                retry_count=retry_count,
                max_retries=max_retries,
                last_error="章节未返回可下载图片",
            )
            return

        semaphore = asyncio.Semaphore(max(1, min(32, int(req.concurrency or context.concurrency or 6))))
        total_count = len(image_urls)
        results: list[tuple[bool, str | None, bool]] = []

        async def worker(index: int, image_url: str) -> None:
            ext = infer_output_extension(image_url)
            output_path = output_dir / f"{index:03d}{ext}"

            if output_path.exists() and output_path.stat().st_size > 0:
                results.append((True, None, False))
                await self._set_state(task_id, status="running", message="下载中...", progress_completed=len(results), progress_total=total_count)
                return

            async with semaphore:
                outcome: DownloadResult = await self.http_client.download_binary(
                    image_url,
                    output_path,
                    cookies=context.cookies,
                    user_agent=context.user_agent,
                    referer=chapter_url,
                    timeout_sec=30,
                    retry_delays=(0.0, *self.image_retry_delays),
                    rate_limit_rps=float(req.rate_limit_rps or context.rate_limit_rps),
                    concurrency=int(req.concurrency or context.concurrency or 6),
                )
                results.append((bool(outcome.ok), outcome.error, bool(outcome.retryable)))
                await self._set_state(task_id, status="running", message="下载中...", progress_completed=len(results), progress_total=total_count)

        await asyncio.gather(*[worker(idx, image_url) for idx, image_url in enumerate(image_urls, start=1)])

        success_count = sum(1 for flag, _, _ in results if flag)
        failed_count = max(total_count - success_count, 0)
        retryable_failures = [entry for entry in results if (not entry[0] and entry[2])]
        failure_errors = [entry[1] for entry in results if (not entry[0] and entry[1])]
        last_error = failure_errors[-1] if failure_errors else None

        if success_count <= 0 and retry_count < max_retries and retryable_failures:
            await self._set_state(
                task_id,
                status="retrying",
                message=f"下载失败，准备重试 ({retry_count + 1}/{max_retries})",
                report={
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "total_count": total_count,
                    "output_dir": str(output_dir),
                    "manga_id": manga_id,
                    "chapter_id": chapter_id,
                    "provider": provider.key,
                },
                retry_count=retry_count,
                max_retries=max_retries,
                next_retry_at=None,
                last_error=last_error,
                progress_completed=total_count,
                progress_total=total_count,
            )

            async def _retry_later() -> None:
                await asyncio.sleep(self.task_retry_delay_sec)
                await self.run_download_task(
                    task_id,
                    req,
                    provider,
                    context,
                    retry_count=retry_count + 1,
                    max_retries=max_retries,
                )

            self.submit(_retry_later())
            return

        if success_count <= 0:
            status = "error"
            error_code = "SCRAPER_RETRY_EXHAUSTED" if retryable_failures and retry_count >= max_retries else "SCRAPER_DOWNLOAD_FAILED"
        elif failed_count > 0:
            status = "partial"
            error_code = None
        else:
            status = "success"
            error_code = None

        report = {
            "success_count": success_count,
            "failed_count": failed_count,
            "total_count": total_count,
            "output_dir": str(output_dir),
            "manga_id": manga_id,
            "chapter_id": chapter_id,
            "provider": provider.key,
        }
        message = "下载完成" if status == "success" else "下载部分完成" if status == "partial" else "下载失败"
        await self._set_state(
            task_id,
            status=status,
            message=message,
            report=report,
            finished=True,
            retry_count=retry_count,
            max_retries=max_retries,
            error_code=error_code,
            last_error=last_error,
            next_retry_at=None,
            progress_completed=total_count,
            progress_total=total_count,
        )
