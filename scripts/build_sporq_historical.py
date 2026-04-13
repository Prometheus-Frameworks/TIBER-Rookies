#!/usr/bin/env python3
"""
Parse the three SPORQ TSV files (RB, WR, TE) and produce
data/historical/sporq_historical.json

Schema per player entry:
  {
    "name": str,
    "pos": str,          # RB | WR | TE
    "school": str,
    "year": int | null,
    "round": int | null, # null if undrafted ("-") or TBD
    "ht_in": float | null,
    "wt": int | null,
    "bmi": float | null,
    "forty": float | null,
    "speed_score": float | null,
    "vertical": float | null,
    "broad": float | null,
    "bench": int | null,
    "three_cone": float | null,
    "shuttle": float | null,
    "sporq": float | null  # null for DNQ
  }

Output:
  data/historical/sporq_historical.json  — full list + per-position arrays
"""

import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "historical")

TSV_FILES = {
    "RB": os.path.join(DATA_DIR, "sporq_raw_rb.tsv"),
    "WR": os.path.join(DATA_DIR, "sporq_raw_wr.tsv"),
    "TE": os.path.join(DATA_DIR, "sporq_raw_te.tsv"),
}

OUTPUT_FILE = os.path.join(DATA_DIR, "sporq_historical.json")

EXPECTED_COLS = ["NAME", "POS", "SCHOOL", "HT", "WT", "BMI",
                 "40YD", "SPEED", "VERTICAL", "BROAD", "BENCH",
                 "3CONE", "SHUTTLE", "YEAR", "ROUND", "SPORQ"]


def parse_float(val):
    if not val or val.strip() in ("-", "DNQ", "TBD", ""):
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None


def parse_int(val):
    if not val or val.strip() in ("-", "DNQ", "TBD", ""):
        return None
    try:
        return int(float(val.strip()))
    except ValueError:
        return None


def parse_height(ht_str):
    """Convert '6\' 0"' or '6-0' style to total inches (float)."""
    if not ht_str or ht_str.strip() in ("-", ""):
        return None
    s = ht_str.strip()
    # Handle: 6' 0.5" or 6' 0"
    m = re.match(r"(\d+)'\s*([\d.]+)\"?", s)
    if m:
        feet = int(m.group(1))
        inches = float(m.group(2))
        return round(feet * 12 + inches, 2)
    # Handle: 6-0
    m = re.match(r"(\d+)-(\d+)", s)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    return None


def parse_row(cols, pos_override):
    if len(cols) < 16:
        return None
    name = cols[0].strip()
    if not name or name == "NAME":
        return None  # skip header or blank rows

    sporq_raw = cols[15].strip()
    is_dnq = sporq_raw.upper() in ("DNQ", "TBD", "")
    sporq = None if is_dnq else parse_float(sporq_raw)

    return {
        "name": name,
        "pos": pos_override,
        "school": cols[2].strip() or None,
        "year": parse_int(cols[13]),
        "round": parse_int(cols[14]),
        "ht_in": parse_height(cols[3]),
        "wt": parse_int(cols[4]),
        "bmi": parse_float(cols[5]),
        "forty": parse_float(cols[6]),
        "speed_score": parse_float(cols[7]),
        "vertical": parse_float(cols[8]),
        "broad": parse_float(cols[9]),
        "bench": parse_int(cols[10]),
        "three_cone": parse_float(cols[11]),
        "shuttle": parse_float(cols[12]),
        "sporq": sporq,
        "dnq": is_dnq,
    }


def load_tsv(path, pos):
    players = []
    skipped = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            cols = line.split("\t")
            row = parse_row(cols, pos)
            if row is None:
                skipped += 1
                continue
            players.append(row)
    print(f"  {pos}: {len(players)} rows parsed, {skipped} skipped")
    return players


def compute_percentiles(players_with_sporq):
    """Attach sporq_percentile (0–100) based on rank within position group."""
    scored = [p for p in players_with_sporq if p["sporq"] is not None]
    scored_sorted = sorted(scored, key=lambda p: p["sporq"])
    n = len(scored_sorted)
    for i, p in enumerate(scored_sorted):
        p["sporq_percentile"] = round((i / (n - 1)) * 100, 1) if n > 1 else 100.0
    # DNQ players get no percentile
    for p in players_with_sporq:
        if p.get("sporq_percentile") is None:
            p["sporq_percentile"] = None


def main():
    all_players = []
    by_pos = {}
    for pos, path in TSV_FILES.items():
        print(f"Parsing {pos} from {os.path.basename(path)}…")
        players = load_tsv(path, pos)
        compute_percentiles(players)
        by_pos[pos] = players
        all_players.extend(players)

    print(f"\nTotal: {len(all_players)} players across all positions")
    scored = [p for p in all_players if p["sporq"] is not None]
    print(f"  With SPORQ score: {len(scored)}")
    print(f"  DNQ: {len(all_players) - len(scored)}")

    output = {
        "meta": {
            "description": "Historical SPORQ athletic composite scores for RB/WR/TE prospects",
            "source": "FantasyPoints.com SPORQ",
            "positions": list(TSV_FILES.keys()),
            "total_players": len(all_players),
            "scored_players": len(scored),
        },
        "players": all_players,
        "by_position": {
            "RB": by_pos.get("RB", []),
            "WR": by_pos.get("WR", []),
            "TE": by_pos.get("TE", []),
        },
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nOutput written to {OUTPUT_FILE}")
    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"File size: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
