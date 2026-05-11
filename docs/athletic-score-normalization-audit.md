# Athletic-score normalization audit (issue #205)

Status: **investigation only**. No model logic was modified.

## TL;DR

The `athletic_score_0_100` field on the promoted Rookie Alpha exports is
**not** the Kent Lee Platte RAS percentile most readers would assume. It is a
within-class z-score (`50 + 16.6667·z`, clamped 0–100) computed against the
players in the same season's `data/raw/<year>_combine_results.json` file.

That construction has three predictable side-effects, all visible in the
exports today:

1. **Class mean is mechanically pinned at ~50.** Across 2022–2026 the mean
   athletic score is 48.8–52.3 and the IQR is ~14–20 points wide. There is
   no "elite class" or "weak class" signal — every cohort is centered by
   construction.
2. **Tiny historical cohorts amplify noise.** The 2022/2023/2024 combine
   files each carry 13–15 rows total (4–5 RBs, 6–9 WRs, 1–2 TEs). With
   `pstdev` over 2 verticals or 3 forties, |z| collapses to a small set of
   round numbers. Bijan Robinson's 42.2 is the canonical example.
3. **Cross-class comparisons are not commensurable.** A 60 in 2023 is a
   different distributional position than a 60 in 2026. Anything downstream
   that mixes classes (historical comps, ML features, archetype clusters)
   is comparing apples to oranges.

For Bijan specifically: his componentwise scores are
`forty 27.4 / vertical 33.3 / broad 33.3 / cone 66.7 / size 71.0`, weighted
to **42.20**. That matches the export to four decimals. The reason these
are below 50 is that he was compared to a 4-RB cohort that included Devon
Achane (4.32 forty); his official Kent Lee Platte RAS of 9.56/10 has no
bearing on the model output.

## Methodology

Audit script: `scripts/audit_athletic_score_normalization.py`. It reads the
existing promoted predraft exports under
`exports/promoted/rookie-alpha/` and the historical SPORQ table at
`data/historical/sporq_historical.json`. For each class it reports:

- the athletic-score distribution (n, mean, median, p25, p75, share <50, <40)
- the underlying combine cohort size by position
- players where `athletic_score < 50` while `production ≥ 75` and
  `draft_capital ≥ 75` (the "looks like elite production + capital but the
  model says non-athlete" pattern)
- players whose computed `athletic_score` is ≥ 20 points below their
  on-file SPORQ percentile when SPORQ is high (≥ 65)

Run:

```
python3 scripts/audit_athletic_score_normalization.py
python3 scripts/audit_athletic_score_normalization.py --json /tmp/audit.json
```

## Findings

### Class-level distribution

| class | n  | mean | median | p25  | p75  | <50 | <40 | combine rows |
|-------|----|------|--------|------|------|-----|-----|--------------|
| 2022  | 15 | 48.8 | 51.6   | 37.6 | 59.1 | 47% | 27% | 15           |
| 2023  | 13 | 52.3 | 53.3   | 44.5 | 58.6 | 46% | 15% | 13           |
| 2024  | 15 | 49.3 | 46.6   | 40.1 | 58.0 | 53% | 20% | 15           |
| 2025  | 67 | 49.4 | 49.9   | 42.2 | 57.1 | 51% | 15% | 67           |
| 2026  | 85 | 49.9 | 50.0   | 43.3 | 56.5 | 45% | 12% | 96           |

The pattern is uniform: every class is centered just below 50, with a tight
IQR. That is a property of the algorithm, not of the underlying athletic
talent.

### Suspicious athletic-score / capital combinations (pre-2026)

Players with `athletic_score < 50`, `production ≥ 75`, and
`draft_capital ≥ 75`:

| year | player              | pos | athletic | source            | prod | dc  |
|------|---------------------|-----|----------|-------------------|------|-----|
| 2022 | Drake London        | WR  | 34.6     | RAS               | 80.0 | 92.0|
| 2022 | Jameson Williams    | WR  | 37.6     | COMBINE_FALLBACK  | 88.0 | 88.0|
| 2023 | Bijan Robinson      | RB  | 42.2     | RAS               | 92.0 | 92.0|
| 2024 | Caleb Williams      | QB  | 37.2     | COMBINE_FALLBACK  | 91.0 | 98.0|
| 2024 | Drake Maye          | QB  | 40.1     | RAS               | 80.0 | 95.0|
| 2024 | Rome Odunze         | WR  | 43.3     | RAS               | 92.0 | 90.0|

These are the players the issue points at: top-of-draft prospects whose
athletic scores are dragging their composite below where elite
production + capital should land them.

### SPORQ divergence (sporq ≥ 65, gap ≥ 20 points)

The repo already carries a SPORQ percentile for many of these players in
`data/historical/sporq_historical.json`. SPORQ is a position-aware
historical percentile and is therefore directly comparable across classes.
The gap between SPORQ and the model's `athletic_score` is large and
systematic:

Pre-2026 highlights:

| year | player            | pos | model | SPORQ | delta |
|------|-------------------|-----|-------|-------|-------|
| 2022 | Breece Hall       | RB  | 54.9  | 98.7  | +43.8 |
| 2022 | Alec Pierce       | WR  | 60.7  | 94.9  | +34.2 |
| 2023 | Bijan Robinson    | RB  | 42.2  | 84.1  | +41.9 |
| 2023 | Jahmyr Gibbs      | RB  | 55.5  | 86.7  | +31.2 |
| 2024 | Rome Odunze       | WR  | 43.3  | 84.3  | +41.0 |
| 2024 | Brian Thomas Jr.  | WR  | 53.7  | 92.7  | +39.0 |
| 2024 | Xavier Worthy     | WR  | 46.3  | 94.8  | +48.5 |
| 2024 | Ladd McConkey     | WR  | 36.9  | 75.0  | +38.1 |
| 2025 | Luther Burden III | WR  | 46.1  | 92.0  | +45.9 |
| 2025 | Bhayshul Tuten    | RB  | 65.2  | 99.6  | +34.4 |

Total flagged across all classes: **3 (2022), 3 (2023), 6 (2024), 25
(2025), 35 (2026)**. The 2026 count is just as high as the historical
ones, which is the strongest evidence the issue is **systemic** rather
than pre-2026-specific.

### Source mix

`athletic_source` distribution:

- `RAS` — full 5-component within-class composite (this is the dominant
  path for top picks)
- `RAS_PARTIAL` — 3–4 metrics, also within-class
- `RAS_SPORQ_BLEND` — WR-only, partial RAS blended 55/45 with SPORQ
- `COMBINE_FALLBACK` — has 40 + size but no explosive metric; downweighted
- `NEUTRAL_DEFAULT` — 50.0, no usable RAS/SPORQ
- `SPORQ` — TE only, used when RAS missing

`SPORQ_TRUST` (scripts/compute_rookie_alpha.py:649–654):

```
TE: preferred  →  SPORQ used when RAS missing
WR: supplemental → SPORQ used only in partial-RAS blend
RB: ignore   → SPORQ never used, even though most RBs have one
QB: ignore   → SPORQ never used
```

Bijan, Gibbs, Hall, Cook, etc. all have valid SPORQ percentiles in the
repo today, but `SPORQ_TRUST["RB"] = "ignore"` so the model never reads
them. That is a deliberate, documented choice — flagging it because it
interacts directly with this audit.

## Root cause

`compute_ras_scores` (scripts/compute_rookie_alpha.py:500–638) takes the
combine rows for a single season as input, computes `safe_stats`
(`statistics.pstdev`) per metric per position **within that file only**,
and turns each component into `z_to_score(z) = clamp(0, 100, 50 + 16.67·z)`.

There is no global / historical reference distribution. The only knob the
model has to push a player above 50 is to be far in the right tail of *that
year's* same-position cohort. With elite-heavy small classes (2023 RB,
2024 WR), nobody gets to 80; with weak classes, mid-tier athletes get to
65 trivially.

Two implementation details make small-cohort years even noisier:

1. `safe_stats` returns `(values[0], 1.0)` for n=1 and a real pstdev for
   n=2, so every comparison snaps to integer multiples of `1·sd`.
2. `EXCEPTIONAL_Z_THRESHOLD = 1.65` is interpreted as "top 5% within
   cohort" (compute_rookie_alpha.py:124–126), but in a 4-player cohort
   `|z|` cannot exceed ~`1.5` for any single value, so this gate fires
   almost never on the small classes regardless of how truly exceptional
   the metric is.

## Documented assumptions (current state)

- `athletic_score_0_100` is **per-class**, not historical. The label "RAS"
  in the export refers to this in-house composite, not Kent Lee Platte RAS.
- Cross-class comparison of `athletic_score_0_100` is not supported by
  the algorithm. Any consumer doing that (historical comps, archetype
  clusters, ML feature joins) is implicitly trusting that class means are
  identical, which is true mechanically but says nothing about athletic
  talent.
- SPORQ is the position-aware reference percentile already in the repo.
  It is intentionally ignored for RB/QB and treated as supplemental for WR.
- Pre-2026 combine inputs are sparse (13–15 rows for 2022–2024). The
  algorithm runs on whatever is there and produces an answer; it does
  **not** widen the reference frame when the cohort is too small.

## Proposed fixes (for follow-up; not implemented)

These are the surgical options, ordered by blast radius. Per AGENTS.md §6
("Do not modify model logic unless explicitly requested"), none of them
are applied here.

1. **Lowest-risk: rename and document.** Rename the export field to
   `athletic_score_within_class_0_100` (or surface the SPORQ percentile
   alongside it) and document explicitly that it is not historically
   comparable. This unblocks downstream consumers without touching the
   composite.
2. **Promote SPORQ to a tie-breaker for RB/QB.** Change
   `SPORQ_TRUST["RB"]` and `SPORQ_TRUST["QB"]` from `"ignore"` to
   `"supplemental"` so the existing blended path lights up when SPORQ
   contradicts an unstable per-class RAS by ≥ N points. Bijan, Gibbs,
   Hall, Burden, etc. all have SPORQ on file; this is the smallest change
   that recovers the directional signal.
3. **Use a global combine reference distribution.** Build position-level
   means/sds from the union of all combine years (or a longer historical
   table) and pass that as the reference instead of the per-class file.
   This is the principled fix and matches what real RAS does, but it
   changes scores for every player in every class.
4. **Cohort-size guardrail.** When a `(year, position)` cohort has < 10
   rows, fall back to SPORQ where available or to `NEUTRAL_DEFAULT`
   instead of computing unstable z-scores. This caps the damage on the
   2022–2024 historical years without touching 2025/2026 logic.

The deliberate next step recommended by this audit is **option 1 + option
2** (rename + RB/QB SPORQ supplemental). Options 3 and 4 are larger and
should be scoped as their own change with calibration evidence.

## Files

- `scripts/audit_athletic_score_normalization.py` — re-runnable audit
- `scripts/compute_rookie_alpha.py` — current model (unchanged)
- `data/historical/sporq_historical.json` — SPORQ percentile reference
- `data/raw/<year>_combine_results.json` — per-class combine inputs
- `exports/promoted/rookie-alpha/<year>_rookie_alpha_predraft_v0.json` —
  promoted exports the audit reads
