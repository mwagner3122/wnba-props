"""Odds API HTTP client and raw JSON helpers (phase 2)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.logging_setup import setup_logging

logger = setup_logging()

API_HOST = "https://api.the-odds-api.com"
QUOTA_HEADERS = (
    "x-requests-remaining",
    "x-requests-used",
    "x-requests-last",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_stamp(dt: datetime | None = None) -> str:
    """Filesystem-safe ISO-8601 UTC timestamp ending in Z."""
    d = dt or _utc_now()
    return d.strftime("%Y-%m-%dT%H-%M-%SZ")


def _iso_utc(dt: datetime | None = None) -> str:
    d = dt or _utc_now()
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _odds_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return dict(cfg.get("odds") or {})


def _api_key() -> str | None:
    load_dotenv()
    key = os.environ.get("ODDS_API_KEY", "").strip()
    return key or None


def _http_get(url: str, timeout: float = 30.0) -> tuple[Any, dict[str, str]]:
    """GET JSON; return (parsed_body, lowercased headers). Never logs the URL's apiKey."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            body = json.loads(raw.decode("utf-8")) if raw else None
            return body, headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _merge_quota(dst: dict[str, str | None], headers: dict[str, str]) -> None:
    for h in QUOTA_HEADERS:
        if h in headers:
            dst[h] = headers[h]


def fetch_events(sport_key: str, api_key: str, quota: dict[str, str | None]) -> list[dict[str, Any]]:
    qs = urllib.parse.urlencode({"apiKey": api_key})
    url = f"{API_HOST}/v4/sports/{sport_key}/events?{qs}"
    body, headers = _http_get(url)
    _merge_quota(quota, headers)
    if body is None:
        return []
    if not isinstance(body, list):
        logger.error("Malformed events response (expected list)")
        return []
    return body


def fetch_event_odds(
    sport_key: str,
    event_id: str,
    api_key: str,
    *,
    regions: str,
    markets: str,
    odds_format: str,
    quota: dict[str, str | None],
) -> dict[str, Any] | None:
    qs = urllib.parse.urlencode(
        {
            "apiKey": api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": "iso",
        }
    )
    url = f"{API_HOST}/v4/sports/{sport_key}/events/{event_id}/odds?{qs}"
    body, headers = _http_get(url)
    _merge_quota(quota, headers)
    if body is None:
        return None
    if not isinstance(body, dict):
        logger.error("Malformed event-odds response for event %s", event_id)
        return None
    return body


def save_raw_odds(raw_dir: Path, captured_at: datetime, payload: dict[str, Any]) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{_iso_stamp(captured_at)}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def find_latest_raw(raw_dir: Path) -> Path | None:
    if not raw_dir.is_dir():
        return None
    files = sorted(raw_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def load_raw_payload(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Raw odds file must be a JSON object: {path}")
    return data
