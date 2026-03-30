# Canonical historical prospect features row schema (v0 scaffold)

Each row represents one historical drafted prospect candidate used for nearest-neighbor matching.

## Required fields

- `player_id` (string): stable identity key used across feature and outcome files.
- `player_name` (string)
- `position` (string): normalized position group used for position-only matching.
- `school` (string | null)
- `draft_year` (integer)
- `source_season` (integer): season context for how feature values were sourced.
- `ras_0_100` (number | null): normalized athletic profile signal.
- `production_0_100` (number | null): normalized college production signal.
- `draft_capital_proxy_0_100` (number | null): draft-market context proxy on the same 0-100 scale.

## Optional fields

- `size_context_0_100` (number | null): deterministic height/weight percentile context signal for talent-profile tie-breaking. For WR, computed as `max(0, min(100, round(50 + composite_z * 15, 1)))` where `composite_z = 0.55 * height_z + 0.45 * weight_z`, `height_z = (height_in - 72.5) / 2.0`, `weight_z = (weight_lb - 197.0) / 18.0`. Reference anchors (72.5 in / 197 lb) are approximate NFL combine WR medians. Historical WR rows were seeded from the same ingredient set; 2026 rookie WR scores are derived from `data/raw/2026_combine_results.json`.
- `normalization_scope` (string | null): optional producer-assigned declaration of how `production_0_100` was normalized (for example `cohort-local`, `class-local`, `historical-wr-cfbd-method-v1`, or `historical-wr-cfbd-season-pop-v1`).
- `normalization_anchor` (object | null): optional explicit min/max anchor metadata for the current `production_0_100` normalization regime (e.g., min/max player id and raw production values).
- `source_name` (string | null): human-readable provenance source label.
- `source_url` (string | null): provenance URL.
- `notes` (string | null): operator note if useful.

## Rationale for draft field

This scaffold uses `draft_capital_proxy_0_100` instead of raw pick value to keep direct compatibility with current Rookie Alpha producer conventions and permit future market-context comp mode without translation glue.

## Null policy

Explicit `null` values are valid for unavailable historical inputs. Nulls do not get inferred.

## Example

See `historical_prospect_features.sample.json`.
