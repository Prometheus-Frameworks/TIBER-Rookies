"""Local read-through cache for CFBD API responses.

Every successful CFBD response is saved under CFBD_CACHE_DIR (default
`.cfbd_cache/` at the repo root, gitignored) and served from there on later
runs, so a full pull only has to happen once and reruns work offline.

LOCAL ONLY. CFBD Terms §5 prohibit redistributing raw API Data, and
TIBER-Rookies is public: never commit, upload, or share this folder. Derived
outputs built from it are fine to commit.

Layout: {CFBD_CACHE_DIR}/{year}/{endpoint}/{sha256(url)[:20]}.json, each file
holding {"url", "fetched_at", "payload"}. URLs carry no API key (the key is
sent as a header), so the key is never written to disk.

To refresh a season (e.g. replace season-to-date stats with final stats),
delete its year folder, e.g. `.cfbd_cache/2026/stats-player-season/`.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
MISS = object()


def cache_dir() -> Path:
    return Path(os.getenv("CFBD_CACHE_DIR") or REPO_ROOT / ".cfbd_cache")


def cache_path(url: str) -> Path:
    parsed = urlparse(url)
    year = parse_qs(parsed.query).get("year", ["no-year"])[0]
    endpoint = parsed.path.strip("/").replace("/", "-") or "root"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return cache_dir() / year / endpoint / f"{digest}.json"


def load(url: str) -> Any:
    """Cached payload for url, or MISS."""
    path = cache_path(url)
    if not path.exists():
        return MISS
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logging.warning("Ignoring unreadable CFBD cache file %s", path)
        return MISS
    if record.get("url") != url:
        return MISS
    return record["payload"]


def store(url: str, payload: Any) -> None:
    path = cache_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "url": url,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "payload": payload,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record), encoding="utf-8")
    tmp.replace(path)


def fetch_category(year: int, category: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Cached wrapper for compute_production_scores.fetch_cfbd_category.

    That module is hash-pinned by the 2024 reconstruction
    (build_2024_reconstruction.REPO_FILE_BINDING_PATHS), so caching wraps it
    from outside instead of editing it. Its own main() therefore still fetches
    live.
    """
    from urllib.parse import urlencode

    from scripts.compute_production_scores import CFBD_BASE_URL, fetch_cfbd_category

    url = f"{CFBD_BASE_URL}/stats/player/season?{urlencode({'year': year, 'category': category})}"
    cached = load(url)
    if cached is not MISS:
        return cached
    rows = fetch_cfbd_category(year, category, **kwargs)
    store(url, rows)
    return rows
