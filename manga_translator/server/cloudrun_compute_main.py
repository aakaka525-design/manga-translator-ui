"""Compute-only Cloud Run entrypoint.

This app intentionally exposes only the internal translation endpoint
to avoid loading unrelated web/admin/scraper routes in compute service.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from manga_translator.server.core import config_manager, task_manager
from manga_translator.server.routes import internal_translate_router


logger = logging.getLogger("manga_translator.server.cloudrun_compute")
os.environ.setdefault("MANGA_TRANSLATOR_WEB_SERVER", "true")

# Ensure admin/runtime config file exists for config-dependent utilities.
config_manager.init_server_config_file()

app = FastAPI(title="Manga Translator Compute Service")
app.include_router(internal_translate_router)


@app.on_event("startup")
async def startup_event() -> None:
    resolved_use_gpu = task_manager._ensure_runtime_for_translator(
        None,
        source="cloudrun_compute_startup",
        force=False,
    )
    task_manager.init_semaphore()
    logger.info(
        "CloudRun compute startup ready: use_gpu=%s source=%s",
        resolved_use_gpu,
        task_manager.server_config.get("_runtime_config_source", "unknown"),
    )


@app.get("/", include_in_schema=False)
async def root_health() -> dict[str, str]:
    return {"status": "ok"}
