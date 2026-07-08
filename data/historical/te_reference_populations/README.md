# Historical TE reference populations — QUARANTINED

**Status (as of issue [#257](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/257)):
all five season files in this directory are intentionally empty (`[]`).**

## What was found

Every file previously committed here (`2017`–`2021_te_receiving_population.json`) contained
**WR reference-population rows with only the `position` field changed from `"WR"` to `"TE"`**.
Each file was byte-identical to the first N alphabetically-sorted, `receptions >= 20` rows of
that same season's `data/historical/wr_reference_populations/{year}_wr_receiving_population.json`
(e.g. "A.J. Brown," a wide receiver, appeared as row 1 of the 2017 TE file with his real WR
receiving stats and `"position": "TE"`). This held across all 5 seasons. No genuine tight end
statistics were present in any of these files.

## Root cause

This was a **fabrication/authoring error present from the moment the TE historical-comps lane
was introduced**, not a later regression. `scripts/fetch_te_reference_populations.py` — the
script whose job is to populate this directory — is implemented correctly: it queries CFBD's
`stats/player/season?category=receiving` endpoint and filters to `TE`/`H-BACK`/`FB` positions
only. The committed files were not produced by running that script against live data; they were
seeded with WR rows relabeled as TE, and no downstream validation ever checked that the content
actually described tight ends (the consuming loader only checks field presence and that
`position` is one of `TE`/`H-BACK`/`FB` — a relabeled WR row passes that check trivially).

No branch in this repository's history (including branches never merged to `main` that also
touch this lane) contains a genuine TE population, and `te_production_profiles/` contains only
two individual hand-curated player profiles, not a season-level cohort usable for normalization.

## Why quarantine instead of repair

Producing a real replacement requires calling the CFBD API with a valid `CFBD_API_KEY`
(free registration at collegefootballdata.com — see `.env.example`). No key is configured in
this environment, and unauthenticated requests to the CFBD endpoint return `401 Unauthorized`.
Fabricating "plausible" TE numbers instead would repeat exactly the mistake this issue exists to
fix, so the files are quarantined (emptied) rather than repaired with unverifiable data.

## Effect of quarantine

`scripts/compute_historical_comps.py::_load_te_reference_populations` requires at least
**30 qualifying rows** for a season to be treated as a valid reference population. With these
files empty, no season qualifies, so the TE lane correctly falls back to in-cohort normalization
(`historical-te-cfbd-method-v1`) and `methodology_compatible` is `false` for TE — the same honest
non-compatible treatment already applied to the QB and RB lanes, instead of the previously false
`methodology_compatible: true` / `status: "ui_safe"` claim produced by the mislabeled data.

## Populate files with real data

Once a `CFBD_API_KEY` is available:

```
CFBD_API_KEY=your_key python3 scripts/fetch_te_reference_populations.py --years 2017 2018 2019 2020 2021
```

`tests/test_te_reference_population_integrity.py` will need its quarantine assertion updated
once real rows are populated, and must continue to pass its cross-check against
`wr_reference_populations/` to guard against this defect recurring.
