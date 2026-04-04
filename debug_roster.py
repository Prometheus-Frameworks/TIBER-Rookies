#!/usr/bin/env python3
import sys
sys.path.insert(0, ".")
from scripts.compute_breakout_age import fetch_roster
from scripts.compute_production_scores import normalize_identity

roster = fetch_roster("Indiana", 2025)
print(f"Indiana 2025 roster: {len(roster)} players")
target = normalize_identity("Fernando Mendoza")
print(f"Looking for: {repr(target)}")
for p in roster:
    fn = str(p.get("firstName", ""))
    ln = str(p.get("lastName", ""))
    full = f"{fn} {ln}".strip()
    norm = normalize_identity(full)
    if norm == target or "fernand" in norm.lower() or "mendoz" in norm.lower():
        print(f"  FOUND: {repr(full)} -> year={p.get('year')}")
print("---")
print("First 3 names:", [(p.get("firstName"), p.get("lastName"), p.get("year")) for p in roster[:3]])
