#!/usr/bin/env python3
"""Fetch current KTC dynasty values and update 2026_dynasty_adp.json.

KTC does not have an official public API. To find the correct endpoint:

  1. Open https://keeptradecut.com/dynasty-rankings in Chrome
  2. Open DevTools (F12) → Network tab → filter for "Fetch/XHR"
  3. Reload the page
  4. Look for a request returning a JSON array of player objects with a
     numeric 'value' field (typically 0–9999 scale)
  5. Copy that request URL into KTC_API_URL below

Run manually:
  python3 scripts/fetch_ktc_values.py

Schedule (cron, every 24h at 06:00):
  0 6 * * * cd /path/to/tiber-rookies && python3 scripts/fetch_ktc_values.py

Only players already in 2026_dynasty_adp.json are updated. New players are
not added automatically — add them manually with ktc_rank: null first.
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Configure this ────────────────────────────────────────────────────────────
KTC_API_URL: str | None = None  # e.g. "https://keeptradecut.com/api/players?format=2&numQBs=1"
# ─────────────────────────────────────────────────────────────────────────────

DYNASTY_ADP_PATH = Path("data/processed/2026_dynasty_adp.json")

# KTC raw value → our 0-100 scale uses min-max normalisation within the class.
# A floor is applied so unranked/negligible players don't skew the range.
KTC_VALUE_FLOOR = 100  # ignore players below this raw KTC value


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def match_ktc_player(our_name: str, ktc_players: list[dict]) -> dict | None:
    """Fuzzy-match our player name against the KTC player list."""
    best_score = 0.0
    best = None
    for ktc in ktc_players:
        name = ktc.get("playerName") or ktc.get("name") or ""
        score = _similarity(our_name, name)
        if score > best_score:
            best_score = score
            best = ktc
    if best_score >= 0.80:
        return best
    logging.warning("No KTC match for '%s' (best=%.2f)", our_name, best_score)
    return None


def fetch_ktc_players(url: str) -> list[dict]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; tiber-rookies/1.0)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalise_within_class(rows: list[dict], ktc_value_key: str = "ktc_raw_value") -> list[dict]:
    """Min-max normalise ktc_raw_value to dynasty_adp_0_100 within the class."""
    values = [r[ktc_value_key] for r in rows if r.get(ktc_value_key) is not None]
    if not values:
        return rows
    lo, hi = min(values), max(values)
    span = hi - lo if hi != lo else 1
    for row in rows:
        raw = row.get(ktc_value_key)
        if raw is not None:
            row["dynasty_adp_0_100"] = round(((raw - lo) / span) * 100, 1)
    return rows


def main() -> None:
    if not KTC_API_URL:
        logging.error(
            "KTC_API_URL is not set. See the docstring at the top of this script "
            "for instructions on how to find the correct endpoint."
        )
        sys.exit(1)

    logging.info("Fetching KTC dynasty values from %s", KTC_API_URL)
    ktc_players = fetch_ktc_players(KTC_API_URL)
    logging.info("Fetched %d players from KTC", len(ktc_players))

    # Filter to players with meaningful value
    ktc_players = [p for p in ktc_players if (p.get("value") or 0) >= KTC_VALUE_FLOOR]

    our_rows = json.loads(DYNASTY_ADP_PATH.read_text(encoding="utf-8"))

    updated = 0
    for row in our_rows:
        ktc = match_ktc_player(row["player_name"], ktc_players)
        if ktc is None:
            continue
        raw_value = ktc.get("value") or ktc.get("dynastyValue") or ktc.get("sfValue")
        if raw_value is None:
            logging.warning("No value field found for %s in KTC response", row["player_name"])
            continue
        row["ktc_raw_value"] = int(raw_value)
        # Derive positional rank string if available
        pos_rank = ktc.get("positionRank") or ktc.get("posRank")
        if pos_rank:
            row["ktc_rank"] = f"{row['position']}{pos_rank}"
        updated += 1
        logging.info("  %s → raw=%d", row["player_name"], raw_value)

    if updated == 0:
        logging.error("No players matched — check KTC_API_URL and response format.")
        sys.exit(1)

    # Normalise raw values to 0-100 within this class
    normalise_within_class(our_rows, ktc_value_key="ktc_raw_value")

    # Clean up temp field
    for row in our_rows:
        row.pop("ktc_raw_value", None)

    DYNASTY_ADP_PATH.write_text(
        json.dumps(our_rows, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logging.info("Updated %d/%d players in %s", updated, len(our_rows), DYNASTY_ADP_PATH)


if __name__ == "__main__":
    main()
