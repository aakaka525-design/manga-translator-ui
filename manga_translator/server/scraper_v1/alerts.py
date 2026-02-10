"""Scraper alert rules and webhook delivery helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .task_store import AlertStoreRecord, ScraperTaskStore


DEFAULT_ALERT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "poll_interval_sec": 30,
    "cooldown_sec": 300,
    "threshold_backlog": 30,
    "threshold_error_rate": 0.25,
    "threshold_min_sample": 20,
    "webhook": {
        "enabled": False,
        "url": "",
        "timeout_sec": 5,
        "max_retries": 3,
    },
}


def _deep_merge(defaults: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    payload = payload or {}
    for key, default_value in defaults.items():
        incoming = payload.get(key, default_value)
        if isinstance(default_value, dict):
            incoming_dict = incoming if isinstance(incoming, dict) else {}
            result[key] = _deep_merge(default_value, incoming_dict)
        else:
            result[key] = incoming
    for key, value in payload.items():
        if key not in result:
            result[key] = value
    return result


def normalize_alert_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = _deep_merge(DEFAULT_ALERT_SETTINGS, payload)
    webhook_cfg = merged.get("webhook", {})
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["poll_interval_sec"] = max(5, int(merged.get("poll_interval_sec", 30)))
    merged["cooldown_sec"] = max(0, int(merged.get("cooldown_sec", 300)))
    merged["threshold_backlog"] = max(1, int(merged.get("threshold_backlog", 30)))
    merged["threshold_error_rate"] = min(1.0, max(0.0, float(merged.get("threshold_error_rate", 0.25))))
    merged["threshold_min_sample"] = max(1, int(merged.get("threshold_min_sample", 20)))
    merged["webhook"] = {
        "enabled": bool(webhook_cfg.get("enabled", False)),
        "url": str(webhook_cfg.get("url", "") or "").strip(),
        "timeout_sec": max(1, int(webhook_cfg.get("timeout_sec", 5))),
        "max_retries": max(1, int(webhook_cfg.get("max_retries", 3))),
    }
    return merged


def _build_candidates(
    *,
    queue_stats: dict[str, Any],
    metrics: dict[str, Any],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    threshold_backlog = int(settings["threshold_backlog"])
    if int(queue_stats.get("backlog", 0) or 0) >= threshold_backlog:
        candidates.append(
            {
                "rule": "backlog_high",
                "severity": "warning",
                "message": f"Scraper backlog is high ({queue_stats.get('backlog', 0)})",
                "payload": {"queue_stats": queue_stats, "threshold_backlog": threshold_backlog},
            }
        )

    total = int(metrics.get("total", 0) or 0)
    error = int(metrics.get("error", 0) or 0)
    min_sample = int(settings["threshold_min_sample"])
    threshold_error_rate = float(settings["threshold_error_rate"])
    error_rate = (float(error) / float(total)) if total else 0.0
    if total >= min_sample and error_rate >= threshold_error_rate:
        candidates.append(
            {
                "rule": "error_rate_high",
                "severity": "warning",
                "message": f"Scraper error rate is high ({error_rate:.2%})",
                "payload": {
                    "metrics": metrics,
                    "error_rate": error_rate,
                    "threshold_error_rate": threshold_error_rate,
                    "threshold_min_sample": min_sample,
                },
            }
        )

    stale_count = int((metrics.get("error_code_breakdown", {}) or {}).get("SCRAPER_TASK_STALE", 0) or 0)
    if stale_count > 0:
        candidates.append(
            {
                "rule": "stale_detected",
                "severity": "error",
                "message": f"Detected stale scraper task(s): {stale_count}",
                "payload": {"stale_count": stale_count, "metrics": metrics},
            }
        )
    return candidates


async def send_webhook(
    *,
    webhook_url: str,
    payload: dict[str, Any],
    timeout_sec: int = 5,
    max_retries: int = 3,
) -> dict[str, Any]:
    delays = [0.0]
    for idx in range(max(1, int(max_retries)) - 1):
        delays.append(float(2**idx))

    attempts = 0
    last_error: str | None = None
    timeout = aiohttp.ClientTimeout(total=max(1, int(timeout_sec)))
    headers = {"Content-Type": "application/json"}
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt, delay in enumerate(delays, start=1):
            attempts = attempt
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                async with session.post(webhook_url, json=payload, headers=headers) as response:
                    if 200 <= response.status < 300:
                        return {
                            "sent": True,
                            "attempts": attempts,
                            "status": "sent",
                            "message": f"webhook delivered ({response.status})",
                        }
                    text = (await response.text()).strip()
                    last_error = f"HTTP {response.status}" + (f": {text}" if text else "")
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)

    return {
        "sent": False,
        "attempts": attempts,
        "status": "failed",
        "message": last_error or "webhook delivery failed",
    }


class ScraperAlertEngine:
    def __init__(self, store: ScraperTaskStore, settings: dict[str, Any] | None):
        self.store = store
        self.settings = normalize_alert_settings(settings)

    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", True))

    def poll_interval_sec(self) -> int:
        return int(self.settings.get("poll_interval_sec", 30))

    async def emit_alert(
        self,
        *,
        rule: str,
        severity: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> AlertStoreRecord:
        alert = self.store.append_alert(rule=rule, severity=severity, message=message, payload=payload)
        webhook_cfg = self.settings.get("webhook", {})
        webhook_enabled = bool(webhook_cfg.get("enabled")) and bool(webhook_cfg.get("url"))
        if not webhook_enabled:
            updated = self.store.update_alert_webhook(alert.id, status="skipped", attempts=0)
            return updated or alert

        result = await send_webhook(
            webhook_url=str(webhook_cfg["url"]),
            payload={
                "event": "scraper_alert",
                "rule": rule,
                "severity": severity,
                "message": message,
                "payload": payload or {},
                "time": datetime.now(timezone.utc).isoformat(),
            },
            timeout_sec=int(webhook_cfg.get("timeout_sec", 5)),
            max_retries=int(webhook_cfg.get("max_retries", 3)),
        )
        status = "sent" if bool(result.get("sent")) else "failed"
        updated = self.store.update_alert_webhook(
            alert.id,
            status=status,
            attempts=int(result.get("attempts", 0) or 0),
            last_error=None if status == "sent" else str(result.get("message", "")),
        )
        return updated or alert

    async def run_once(self) -> list[AlertStoreRecord]:
        if not self.enabled():
            return []

        queue_stats = self.store.queue_stats()
        metrics = self.store.metrics(hours=24)
        candidates = _build_candidates(queue_stats=queue_stats, metrics=metrics, settings=self.settings)
        cooldown_sec = int(self.settings.get("cooldown_sec", 300))
        emitted: list[AlertStoreRecord] = []

        for candidate in candidates:
            existing = self.store.latest_alert_in_cooldown(
                rule=str(candidate["rule"]),
                severity=str(candidate["severity"]),
                cooldown_sec=cooldown_sec,
            )
            if existing is not None:
                continue
            alert = await self.emit_alert(
                rule=str(candidate["rule"]),
                severity=str(candidate["severity"]),
                message=str(candidate["message"]),
                payload=candidate.get("payload") if isinstance(candidate.get("payload"), dict) else None,
            )
            emitted.append(alert)
        return emitted


async def send_test_webhook(
    *,
    webhook_url: str,
    timeout_sec: int = 5,
    max_retries: int = 3,
) -> dict[str, Any]:
    payload = {
        "event": "scraper_alert_test",
        "time": datetime.now(timezone.utc).isoformat(),
        "message": "manual webhook connectivity test",
    }
    return await send_webhook(
        webhook_url=webhook_url,
        payload=payload,
        timeout_sec=timeout_sec,
        max_retries=max_retries,
    )
