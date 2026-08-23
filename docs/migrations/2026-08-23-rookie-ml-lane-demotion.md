# Migration: Rookie ML lane demoted out of the promoted namespace

**Issue:** [TIBER-Rookies #286](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/286) — WP-2
**Authorized base commit:** `54215af61e581000b7370e941dbc90a8a1a70195`
**Date:** 2026-08-23
**Posture:** namespace relocation and governance only. No retraining, no regeneration, no promotion.

## What changed

The experimental Rookie ML lane stopped being carried as a *promoted* artifact family.
Its artifacts moved namespace and its integrity coverage moved validator. Nothing about
the artifacts themselves changed.

| | Before | After |
| --- | --- | --- |
| Artifact path | `exports/promoted/rookie-ml-lane/` | `exports/experimental/rookie-ml-lane/` |
| Integrity validator | `scripts/validate_promoted_integrity.py` | `scripts/validate_experimental_integrity.py` |
| Integrity registry | `exports/promoted_integrity_registry_v0.json` | `exports/experimental_integrity_registry_v0.json` |
| Producer default output | `exports/promoted/rookie-ml-lane` | `runs/rookie-ml-lane` (gitignored) |
| Declared promoted families | 5 | 4 |

## Why

The lane is an experimental, fixture-fed evaluation harness. It was never a calibrated
model, but living under `exports/promoted/` implied otherwise: a reader encountering
`exports/promoted/rookie-ml-lane/heldout_probabilities.json` had no way to tell that its
probability-shaped fields are diagnostics rather than forecasts. Demotion makes the
repository state match the claim the lane was always entitled to make.

Demotion is **not** deregulation. The family kept fail-closed byte-level integrity
coverage; it simply moved to a validator that also enforces what the artifacts are
allowed to say about themselves.

## Byte preservation

Every pre-existing artifact carries the **same SHA-256 and the same byte size** it had at
the authorized base commit under the old promoted path. The move was performed with
`git mv`, which recorded all nine files as pure renames. No artifact was regenerated,
reformatted, re-serialized, retrained, or rewritten.

| Artifact | SHA-256 before | Bytes before | SHA-256 after | Bytes after | Result |
| --- | --- | --- | --- | --- | --- |
| `dataset_diagnostics.json` | `89947ec0c97e0a00defe10bbf7c5341fd1b654b4c8668fb193280f1b5d045291` | 1100 | `89947ec0c97e0a00defe10bbf7c5341fd1b654b4c8668fb193280f1b5d045291` | 1100 | unchanged |
| `evaluation_report.json` | `b9c448e95ef0ce1d097eefbfffc9bd1e00612874f945f4fad7202687a6a98585` | 12873 | `b9c448e95ef0ce1d097eefbfffc9bd1e00612874f945f4fad7202687a6a98585` | 12873 | unchanged |
| `feature_coverage_report.json` | `dabb3bd6039bea9ac61c5dd5873f0559a68644b9d0ccc459348ad5b6bdc1b1a4` | 3673 | `dabb3bd6039bea9ac61c5dd5873f0559a68644b9d0ccc459348ad5b6bdc1b1a4` | 3673 | unchanged |
| `feature_importance_report.json` | `839e416cc019e3b6f0913f647bf429eb3703e3f975f6e9bb80f1717abab3a104` | 1122 | `839e416cc019e3b6f0913f647bf429eb3703e3f975f6e9bb80f1717abab3a104` | 1122 | unchanged |
| `feature_table.json` | `99dca17ae65043312a57e7ca4f8dbf39442a2d8cd41ea0c1ac51e001a67d3a8e` | 14851 | `99dca17ae65043312a57e7ca4f8dbf39442a2d8cd41ea0c1ac51e001a67d3a8e` | 14851 | unchanged |
| `heldout_probabilities.csv` | `3a57453506050dd20e1c497b83705e4279757c7dbfe67f7aa4ac973b11f8b4f6` | 253 | `3a57453506050dd20e1c497b83705e4279757c7dbfe67f7aa4ac973b11f8b4f6` | 253 | unchanged |
| `heldout_probabilities.json` | `9fecb43979174820e8f704983025c36004d6d0e02abc74772d323057844244f6` | 366 | `9fecb43979174820e8f704983025c36004d6d0e02abc74772d323057844244f6` | 366 | unchanged |
| `historical_labeled_dataset.csv` | `0561559e00022a3a2d53a3c1fc7573f8486e196f682301f55934fcae00bf6fa8` | 4321 | `0561559e00022a3a2d53a3c1fc7573f8486e196f682301f55934fcae00bf6fa8` | 4321 | unchanged |
| `historical_labeled_dataset.json` | `279cef5ee2fa40b99c2e283feff3c894ea650ea193833a5cedb0bc1d54499356` | 18524 | `279cef5ee2fa40b99c2e283feff3c894ea650ea193833a5cedb0bc1d54499356` | 18524 | unchanged |

These nine digests are additionally pinned in code as `FROZEN_HISTORICAL_ARTIFACTS` in
`scripts/validate_experimental_integrity.py`. That pinning is the trust anchor: because
the expected inventory lives in the validator rather than in the editable registry,
removing a registry entry does not remove the check, and a registry updated to agree with
tampered bytes still fails.

## What is added, not moved

`exports/experimental/rookie-ml-lane/experimental_status_v0.json` is new. It is the governed status
sidecar that carries the lane's semantics — `artifact_class:
experimental_fixture_evaluation`, `is_calibrated_probability: false`,
`eligible_for_promotion: false`, and an explicit warning that the probability-shaped
legacy fields are not calibrated claims. It exists so those semantics could be stated
**without mutating the frozen historical bytes**, which remain exactly as they were.

The producer writes this sidecar on every run, and the validator rejects the family if it
is missing, unregistered, or claims calibration or promotion eligibility.

## Archive and runs are separate

The frozen archive is not a working directory. Generated producer output goes to
`runs/rookie-ml-lane/`, outside `exports/` and gitignored, and the producer refuses to
write into the archive at all.

An earlier revision of this work defaulted the producer to the archive path. Running the
documented command would have overwritten three of the nine frozen artifacts, added five
unregistered outputs, and replaced the migration sidecar with a run-shaped record — a
state the registry could not be regenerated out of, because the frozen tier pins the
historical bytes in code. The two lifecycles are now separated, and
`tests/test_validate_experimental_integrity.py` proves the documented workflow cannot
mutate the archive.

Generated runs get their own fail-closed validation
(`validate_experimental_integrity.py --run-dir <path>`): same governed semantics, a
self-inventory bijection, and an explicit refusal to carry the archive's migration
provenance.

## Old-path references

`exports/promoted/rookie-ml-lane/` no longer exists. Repository-wide search finds the old path
only in this migration record, in negative tests that prove the promoted namespace
rejects ML artifacts, and in **dated historical audit documents** that describe repository
state at an earlier point in time:

- `docs/repo-state-audit-2026-postdraft.md` (May 2026 snapshot)
- `docs/reports/2026-07-08-machine-readable-artifact-audit.md` (audit-only report)
- `docs/reports/2023-historical-reconstruction-pilot.md` (pilot report)
- `docs/audits/2023-input-integrity-remediation.{md,json}` (pinned to base `524bc54…`)

Those are point-in-time records, several pinned to specific base commits. Rewriting them
to reference the new path would falsify the historical record they exist to preserve, so
they are left byte-unchanged. This classification is enforced, not merely asserted:
`tests/test_experimental_demotion_references.py` fails if the old promoted path appears
anywhere outside that allowlist, so any *new* operational reference is rejected in CI.

## Scope boundaries

This migration did not touch deterministic Rookie Alpha scores, weights, or producer
behavior; historical seeds; promoted non-ML artifact bytes; or the Forecast and Fantasy
contracts. It does not activate WP-1 or WP-3 through WP-6, and it does not promote,
retrain, or deploy anything.
