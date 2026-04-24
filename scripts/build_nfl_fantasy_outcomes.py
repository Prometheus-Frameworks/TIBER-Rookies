#!/usr/bin/env python3
"""Build normalized NFL player-season PPR outcomes for draft cohorts.

Public-source lane only: nflverse release data (player_stats + draft_picks).
This script intentionally does not touch Rookie Alpha scoring artifacts.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import io
import json
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("exports/promoted/nfl-fantasy-outcomes")
OUTPUT_JSON = OUTPUT_DIR / "player_year_ppr_outcomes_v1.json"
OUTPUT_CSV = OUTPUT_DIR / "player_year_ppr_outcomes_v1.csv"
OUTPUT_SOURCE_METADATA = OUTPUT_DIR / "source_metadata_v1.json"

CACHE_DIR = Path("data/external/nflverse")
LEGACY_STATS_CACHE = CACHE_DIR / "player_stats.csv"
STATS_PLAYER_CACHE = CACHE_DIR / "stats_player_reg.csv"
DRAFT_CACHE = CACHE_DIR / "draft_picks.csv"

NFLVERSE_LEGACY_PLAYER_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv.gz"
)
NFLVERSE_STATS_PLAYER_RELEASE_API = "https://api.github.com/repos/nflverse/nflverse-data/releases/tags/stats_player"
NFLVERSE_STATS_PLAYER_BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/"
NFLVERSE_DRAFT_PICKS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv.gz"
)

POSITIONS = {"WR", "RB", "TE", "QB"}
WEEKLY_MODE_COLUMNS = {"week", "game_id", "recent_team", "opponent_team"}
STATS_PLAYER_SEASON_PATTERN = re.compile(r"^stats_player_reg_(\d{4})\.(csv\.gz|csv)$")

FIELDNAMES = [
    "player_id",
    "player_name",
    "position",
    "draft_year",
    "draft_round",
    "overall_pick",
    "nfl_team_drafted",
    "nfl_season",
    "career_year",
    "games",
    "ppr_points",
    "ppr_per_game",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "rushing_yards",
    "rushing_tds",
    "source",
    "source_notes",
]


def slugify_player_name(name: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return clean or "unknown-player"


def to_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_ppr(receptions: float, receiving_yards: float, receiving_tds: float, rushing_yards: float, rushing_tds: float) -> float:
    return (
        receptions * 1.0
        + receiving_yards * 0.1
        + receiving_tds * 6.0
        + rushing_yards * 0.1
        + rushing_tds * 6.0
    )


def career_year_for_season(draft_year: int, nfl_season: int) -> int:
    return nfl_season - draft_year + 1


def download_csv(url: str) -> list[dict[str, str]]:
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read()
    if url.endswith(".gz"):
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as gz:
            text = gz.read().decode("utf-8")
    else:
        text = payload.decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_source_rows(url: str, cache_path: Path, refresh: bool) -> tuple[list[dict[str, str]], str]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if refresh:
        rows = download_csv(url)
        write_csv(cache_path, rows, list(rows[0].keys()) if rows else [])
        return rows, "download"
    if cache_path.exists():
        return read_csv(cache_path), "cache"

    rows = download_csv(url)
    write_csv(cache_path, rows, list(rows[0].keys()) if rows else [])
    return rows, "download"


def fetch_release_asset_names(release_api_url: str) -> list[str]:
    request = urllib.request.Request(
        release_api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "tiber-rookies-source-check"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [asset.get("name", "") for asset in payload.get("assets", []) if asset.get("name")]


def discover_stats_player_seasonal_assets(asset_names: list[str]) -> dict[int, str]:
    seasonal: dict[int, str] = {}
    for name in asset_names:
        match = STATS_PLAYER_SEASON_PATTERN.match(name)
        if not match:
            continue
        season = int(match.group(1))
        existing = seasonal.get(season)
        if not existing or (existing.endswith(".csv") and name.endswith(".csv.gz")):
            seasonal[season] = name
    return seasonal


def detect_source_mode(stats_rows: list[dict[str, str]]) -> str:
    if not stats_rows:
        return "seasonal_source"
    sample_columns = set(stats_rows[0].keys())
    if WEEKLY_MODE_COLUMNS.intersection(sample_columns):
        return "weekly_aggregated"
    return "seasonal_source"


def latest_stats_season(stats_rows: list[dict[str, str]]) -> int:
    return max((to_int(row.get("season"), 0) for row in stats_rows), default=0)


def latest_draft_year(draft_rows: list[dict[str, str]]) -> int:
    return max((to_int(row.get("season") or row.get("draft_year"), 0) for row in draft_rows), default=0)


def is_stale_source(latest_season: int, expected_latest_season: int | None) -> bool:
    if expected_latest_season is None:
        return False
    return latest_season < expected_latest_season


def build_source_metadata(
    stats_rows: list[dict[str, str]],
    draft_rows: list[dict[str, str]],
    source_mode: str,
    expected_latest_season: int | None,
    source_notes: str,
    stats_source: str,
    stats_url: str | None = None,
    stats_urls: list[str] | None = None,
    stats_seasons_loaded: list[int] | None = None,
    missing_stats_seasons: list[int] | None = None,
) -> dict[str, Any]:
    latest_season = latest_stats_season(stats_rows)
    earliest_season = min((to_int(row.get("season"), 0) for row in stats_rows if to_int(row.get("season"), 0) > 0), default=0)
    latest_draft = latest_draft_year(draft_rows)
    stale = is_stale_source(latest_season, expected_latest_season)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "player_stats_row_count": len(stats_rows),
        "draft_picks_row_count": len(draft_rows),
        "latest_stats_season": latest_season,
        "earliest_stats_season": earliest_season,
        "latest_draft_year": latest_draft,
        "source_mode": source_mode,
        "stats_source": stats_source,
        "expected_latest_season": expected_latest_season,
        "is_stale_relative_to_expected": stale,
        "source_notes": source_notes,
    }
    if stats_urls is not None:
        metadata["stats_urls"] = stats_urls
    elif stats_url is not None:
        metadata["stats_url"] = stats_url
    if stats_seasons_loaded is not None:
        metadata["stats_seasons_loaded"] = stats_seasons_loaded
    if missing_stats_seasons is not None:
        metadata["missing_stats_seasons"] = missing_stats_seasons
    return metadata


def build_draft_index(draft_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in draft_rows:
        position = (row.get("position") or row.get("pos") or "").upper()
        if position not in POSITIONS:
            continue
        draft_year = to_int(row.get("season") or row.get("draft_year"), 0)
        if draft_year <= 0:
            continue
        stable_id = (
            row.get("gsis_id")
            or row.get("player_id")
            or row.get("pfr_player_id")
            or f"{slugify_player_name(row.get('player_name', ''))}-{draft_year}"
        )
        index[stable_id] = {
            "player_id": stable_id,
            "player_name": row.get("player_name", ""),
            "position": position,
            "draft_year": draft_year,
            "draft_round": to_int(row.get("round") or row.get("draft_round"), 0),
            "overall_pick": to_int(row.get("pick") or row.get("overall_pick"), 0),
            "nfl_team_drafted": row.get("team") or row.get("draft_team") or "",
        }
    return index


def map_stat_row_to_drafted_player(stat_row: dict[str, str], draft_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    keys = [
        stat_row.get("player_id"),
        stat_row.get("gsis_id"),
        stat_row.get("pfr_player_id"),
    ]
    for k in keys:
        if k and k in draft_index:
            return draft_index[k]

    name = stat_row.get("player_name", "")
    season = to_int(stat_row.get("season"), 0)
    for rec in draft_index.values():
        if rec["player_name"].strip().lower() == name.strip().lower() and rec["draft_year"] <= season:
            return rec
    return None


def has_participation(row: dict[str, str]) -> bool:
    return (
        to_float(row.get("receptions")) > 0
        or to_float(row.get("receiving_yards")) > 0
        or to_float(row.get("receiving_tds")) > 0
        or to_float(row.get("rushing_yards")) > 0
        or to_float(row.get("rushing_tds")) > 0
        or to_int(row.get("games")) > 0
    )


def build_player_outcome_rows(
    stats_rows: list[dict[str, str]],
    draft_rows: list[dict[str, str]],
    source_notes: str,
) -> list[dict[str, Any]]:
    draft_index = build_draft_index(draft_rows)
    source_mode = detect_source_mode(stats_rows)
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    weekly_keys: dict[tuple[str, int], set[str]] = defaultdict(set)

    for row in stats_rows:
        pos = (row.get("position") or row.get("pos") or "").upper()
        if pos not in POSITIONS:
            continue

        draft = map_stat_row_to_drafted_player(row, draft_index)
        if not draft:
            continue

        nfl_season = to_int(row.get("season"), 0)
        if nfl_season <= 0:
            continue

        key = (draft["player_id"], nfl_season)
        if key not in grouped:
            grouped[key] = {
                "player_id": draft["player_id"],
                "player_name": draft["player_name"] or row.get("player_name", ""),
                "position": draft["position"],
                "draft_year": draft["draft_year"],
                "draft_round": draft["draft_round"],
                "overall_pick": draft["overall_pick"],
                "nfl_team_drafted": draft["nfl_team_drafted"],
                "nfl_season": nfl_season,
                "career_year": career_year_for_season(draft["draft_year"], nfl_season),
                "games": 0,
                "receptions": 0.0,
                "receiving_yards": 0.0,
                "receiving_tds": 0.0,
                "rushing_yards": 0.0,
                "rushing_tds": 0.0,
            }

        rec = grouped[key]
        rec["receptions"] += to_float(row.get("receptions"))
        rec["receiving_yards"] += to_float(row.get("receiving_yards"))
        rec["receiving_tds"] += to_float(row.get("receiving_tds"))
        rec["rushing_yards"] += to_float(row.get("rushing_yards"))
        rec["rushing_tds"] += to_float(row.get("rushing_tds"))

        if source_mode == "weekly_aggregated":
            if has_participation(row):
                marker = row.get("game_id") or row.get("week") or f"row-{len(weekly_keys[key]) + 1}"
                weekly_keys[key].add(str(marker))
        else:
            rec["games"] = max(rec["games"], to_int(row.get("games"), 0))

    out: list[dict[str, Any]] = []
    for key, rec in grouped.items():
        if source_mode == "weekly_aggregated":
            rec["games"] = len(weekly_keys.get(key, set()))

        ppr_points = round(
            compute_ppr(
                rec["receptions"],
                rec["receiving_yards"],
                rec["receiving_tds"],
                rec["rushing_yards"],
                rec["rushing_tds"],
            ),
            2,
        )
        ppr_per_game = round(ppr_points / rec["games"], 3) if rec["games"] > 0 else 0.0

        out.append(
            {
                **rec,
                "ppr_points": ppr_points,
                "ppr_per_game": ppr_per_game,
                "source": "nflverse_public_release",
                "source_notes": f"{source_notes}; source_mode={source_mode}",
            }
        )

    out.sort(key=lambda r: (r["draft_year"], r["player_name"], r["nfl_season"]))
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build NFL fantasy outcome calibration player-year artifacts")
    parser.add_argument("--refresh", action="store_true", help="Force download fresh nflverse source snapshots")
    parser.add_argument("--stats-cache", type=Path, default=None)
    parser.add_argument(
        "--stats-season-start",
        type=int,
        default=2022,
        help="Inclusive season start when --stats-source=stats_player and season-sliced assets are used.",
    )
    parser.add_argument(
        "--stats-season-end",
        type=int,
        default=None,
        help="Inclusive season end when --stats-source=stats_player. Defaults to --expected-latest-season if set, else latest discovered season.",
    )
    parser.add_argument(
        "--stats-source",
        choices=["legacy_player_stats", "stats_player"],
        default="stats_player",
        help="Stats source family. `stats_player` prefers regular-season summary assets; falls back to legacy player_stats when needed.",
    )
    parser.add_argument(
        "--stats-source-url",
        type=str,
        default=None,
        help="Optional explicit URL override for player stats source asset.",
    )
    parser.add_argument("--draft-cache", type=Path, default=DRAFT_CACHE)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-source-metadata", type=Path, default=OUTPUT_SOURCE_METADATA)
    parser.add_argument(
        "--expected-latest-season",
        type=int,
        default=None,
        help="Expected latest season in player_stats. Warn/fail if source lags this season.",
    )
    parser.add_argument(
        "--fail-on-stale-source",
        action="store_true",
        help="Exit nonzero if --expected-latest-season is set and source latest season is stale.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    resolved_stats_url = args.stats_source_url
    resolved_stats_urls: list[str] | None = None
    stats_seasons_loaded: list[int] | None = None
    missing_stats_seasons: list[int] | None = None
    seasonal_cache_paths: list[Path] = []
    stats_resolution_note = "manual_stats_source_url"
    resolved_stats_source = args.stats_source
    if not resolved_stats_url and args.stats_source == "stats_player":
        try:
            asset_names = fetch_release_asset_names(NFLVERSE_STATS_PLAYER_RELEASE_API)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"stats_player source discovery failed ({exc}); retrying with legacy_player_stats fallback.")
            resolved_stats_url = NFLVERSE_LEGACY_PLAYER_STATS_URL
            resolved_stats_source = "legacy_player_stats"
            stats_resolution_note = f"stats_player_release_lookup_failed:{exc}; fallback=legacy_player_stats"
        else:
            seasonal_assets = discover_stats_player_seasonal_assets(asset_names)
            if not seasonal_assets:
                resolved_stats_url = NFLVERSE_LEGACY_PLAYER_STATS_URL
                resolved_stats_source = "legacy_player_stats"
                stats_resolution_note = (
                    "stats_player_release_lookup_failed:no_supported_seasonal_reg_csv_asset; "
                    "fallback=legacy_player_stats"
                )
            else:
                latest_discovered = max(seasonal_assets)
                season_end = args.stats_season_end or args.expected_latest_season or latest_discovered
                season_start = args.stats_season_start
                requested_seasons = list(range(season_start, season_end + 1))
                stats_rows = []
                resolved_stats_urls = []
                stats_seasons_loaded = []
                missing_stats_seasons = []
                for season in requested_seasons:
                    asset_name = seasonal_assets.get(season)
                    if not asset_name:
                        missing_stats_seasons.append(season)
                        print(f"WARNING: missing stats_player regular-season asset for {season}")
                        continue
                    asset_url = f"{NFLVERSE_STATS_PLAYER_BASE_URL}{asset_name}"
                    cache_path = CACHE_DIR / f"stats_player_reg_{season}.csv"
                    rows, _ = load_source_rows(asset_url, cache_path, refresh=args.refresh)
                    stats_rows.extend(rows)
                    resolved_stats_urls.append(asset_url)
                    seasonal_cache_paths.append(cache_path)
                    stats_seasons_loaded.append(season)
                stats_mode = "download" if args.refresh else "cache_or_download"
                stats_resolution_note = (
                    f"stats_player_seasonal_assets_loaded={len(stats_seasons_loaded)};"
                    f" requested_range={season_start}-{season_end}; latest_discovered={latest_discovered}"
                )
    if not resolved_stats_url and resolved_stats_source == "legacy_player_stats":
        resolved_stats_url = NFLVERSE_LEGACY_PLAYER_STATS_URL
        stats_resolution_note = "legacy_player_stats_default_url"
    if not resolved_stats_url and resolved_stats_source == "stats_player":
        if args.stats_source == "legacy_player_stats":
            resolved_stats_url = NFLVERSE_LEGACY_PLAYER_STATS_URL
            stats_resolution_note = "legacy_player_stats_default_url"
        else:
            resolved_stats_url = NFLVERSE_LEGACY_PLAYER_STATS_URL
            resolved_stats_source = "legacy_player_stats"
            stats_resolution_note = "stats_player_unresolved; fallback=legacy_player_stats"

    stats_cache = args.stats_cache or (STATS_PLAYER_CACHE if resolved_stats_source == "stats_player" else LEGACY_STATS_CACHE)

    if resolved_stats_source != "stats_player" or resolved_stats_url is not None and resolved_stats_urls is None:
        try:
            stats_rows, stats_mode = load_source_rows(resolved_stats_url, stats_cache, refresh=args.refresh)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            if args.stats_source == "stats_player" and not args.stats_source_url:
                print(f"stats_player source load failed ({exc}); retrying with legacy_player_stats fallback.")
                resolved_stats_url = NFLVERSE_LEGACY_PLAYER_STATS_URL
                resolved_stats_source = "legacy_player_stats"
                stats_cache = args.stats_cache or LEGACY_STATS_CACHE
                stats_rows, stats_mode = load_source_rows(resolved_stats_url, stats_cache, refresh=args.refresh)
                stats_resolution_note = f"{stats_resolution_note}; download_fallback=legacy_player_stats"
            else:
                raise

    draft_rows, draft_mode = load_source_rows(NFLVERSE_DRAFT_PICKS_URL, args.draft_cache, refresh=args.refresh)

    player_stats_source_note = (
        ",".join(str(path) for path in seasonal_cache_paths)
        if seasonal_cache_paths
        else str(stats_cache)
    )
    notes = f"stats_source={resolved_stats_source}; stats_resolution={stats_resolution_note}; player_stats={stats_mode}:{player_stats_source_note}; draft_picks={draft_mode}:{args.draft_cache}"
    source_mode = detect_source_mode(stats_rows)
    source_metadata = build_source_metadata(
        stats_rows=stats_rows,
        draft_rows=draft_rows,
        source_mode=source_mode,
        expected_latest_season=args.expected_latest_season,
        source_notes=notes,
        stats_source=resolved_stats_source,
        stats_url=resolved_stats_url,
        stats_urls=resolved_stats_urls,
        stats_seasons_loaded=stats_seasons_loaded,
        missing_stats_seasons=missing_stats_seasons,
    )

    print("Source freshness diagnostics:")
    print(f"  player_stats rows loaded: {source_metadata['player_stats_row_count']}")
    print(f"  draft_picks rows loaded:  {source_metadata['draft_picks_row_count']}")
    print(f"  latest_stats_season:      {source_metadata['latest_stats_season']}")
    print(f"  latest_draft_year:        {source_metadata['latest_draft_year']}")
    print(f"  stats_source:             {source_metadata['stats_source']}")
    print(f"  earliest_stats_season:    {source_metadata['earliest_stats_season']}")
    if source_metadata.get("stats_urls"):
        print(f"  stats_urls:               {len(source_metadata['stats_urls'])} seasonal assets")
    else:
        print(f"  stats_url:                {source_metadata.get('stats_url')}")
    if source_metadata.get("stats_seasons_loaded") is not None:
        print(f"  stats_seasons_loaded:     {source_metadata.get('stats_seasons_loaded')}")
    if source_metadata.get("missing_stats_seasons") is not None:
        print(f"  missing_stats_seasons:    {source_metadata.get('missing_stats_seasons')}")
    print(f"  source mode detected:     {source_metadata['source_mode']}")

    stale_or_missing = source_metadata["is_stale_relative_to_expected"] or bool(source_metadata.get("missing_stats_seasons"))
    if stale_or_missing:
        print(
            "!!! SOURCE STALENESS WARNING: "
            f"expected_latest_season={args.expected_latest_season}, "
            f"but latest_stats_season={source_metadata['latest_stats_season']}"
        )
        if source_metadata.get("missing_stats_seasons"):
            print(f"!!! MISSING STATS SEASONS: {source_metadata['missing_stats_seasons']}")
        if args.fail_on_stale_source:
            raise SystemExit(
                "Failing due to stale source: "
                f"expected_latest_season={args.expected_latest_season}, "
                f"latest_stats_season={source_metadata['latest_stats_season']}, "
                f"missing_stats_seasons={source_metadata.get('missing_stats_seasons', [])}"
            )

    rows = build_player_outcome_rows(stats_rows, draft_rows, source_notes=notes)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    write_csv(args.output_csv, rows, FIELDNAMES)
    args.output_source_metadata.write_text(json.dumps(source_metadata, indent=2) + "\n", encoding="utf-8")

    print(f"Built {len(rows)} rows")
    print(f"JSON -> {args.output_json}")
    print(f"CSV  -> {args.output_csv}")
    print(f"Metadata -> {args.output_source_metadata}")


if __name__ == "__main__":
    main()
