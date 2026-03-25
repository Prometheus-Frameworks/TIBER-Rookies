# TIBER-Rookies Architecture Note

## Scope now (implemented)

This repo intentionally contains only a standalone pre-draft Rookie Alpha pipeline.

Implemented formula (honest current state):

- RAS: 35%
- College production: 45%
- Draft capital proxy: 20%
- Age-at-entry: **not yet implemented**

The pipeline consumes local artifacts only and writes promoted exports (JSON + CSV). There are no DB writes and no dependency on TIBER-Fantasy runtime services.

## Upstream conceptual lineage

This standalone flow ports the intent of the existing TIBER-Fantasy rookie scripts into a clean handoff shape:

- RAS scoring
- College production scoring
- Rookie Alpha fusion/ranking

## Future phases (not implemented yet)

1. Landing spot adjustment
2. NFL transition blending

These later phases should layer on top of the promoted pre-draft export rather than coupling this repository back to runtime services.
