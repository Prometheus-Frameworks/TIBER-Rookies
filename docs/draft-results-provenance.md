# Draft-results provenance protocol

> Status: documentation guardrail, not an implementation claim.
>
> Revalidated against `main` at `2ef92faf9a9c91a393f53e9140428451529a1c48`. [Issue #242](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/242) remains open: the 2022–2025 processed draft-result files are empty, and `lib/rookies/draftResults.js` does not currently implement `PLAYER_ID_ALIASES`.
>
> The rules below define the intended historical-backfill boundary. Examples from issue #243 remain pending until their corresponding source, data, and code state is present and verified.

## Scope and source boundary

- Draft-result artifacts carry observed NFL draft or verified UDFA facts. They do not create a score, projection, or inferred landing-spot assessment.
- For the historical 2022–2025 backfill tracked in #242, CFBD is the designated primary upstream source: `GET /draft/picks?year={year}`.
- The CFBD fields used are `name`, `nflTeam`, `nflTeamId`, `overall`, `round`, and `pick`.
- Other seasons may come from a governed TIBER-Data artifact or a separately verified public source. Preserve each row's actual lineage; never relabel a non-CFBD row as CFBD-derived.
- Keep `source_name`, `source_url`, `source_status`, and `upstream_provenance_status` explicit wherever the target schema supports them.

## Team disambiguation

CFBD can return the same short city name for two teams. Resolve those rows with `nflTeamId`, not a guess based on city text:

| CFBD `nflTeamId` | TIBER team |
|---:|:---|
| `20` | `NYJ` |
| `19` | `NYG` |
| `24` | `LAC` |
| `14` | `LAR` |

An unknown or conflicting team identifier must fail closed for operator review.

## Name matching and manual overrides

Start with deterministic normalized-name matching. Do not silently accept a fuzzy match. If CFBD uses a legal name while the repository uses a familiar name, a historical build script may add an explicit `NAME_OVERRIDES` entry. Every entry must record the upstream spelling, the repository identity, and why the override is necessary.

- **Tank Dell (`wr-tank-dell`)**: issue #243 records CFBD's `Nathaniel Dell` spelling as the intended manual-override case. This remains a pending edge case until the historical backfill and override table exist on `main`.

## UDFA rows

Absence from CFBD draft picks does not prove that a player signed as an UDFA. Add an UDFA row only when a separate public source verifies the signing.

The row must use `is_udfa: true`, null draft round/pick values, an appropriate UDFA status, the source citation, and `upstream_provenance_status: "source_verified"` where that field is part of the target schema. Explain the exception in `source_name` or the row's source-note field.

- **Jaylen Warren (`rb-jaylen-warren`)**: issue #243 records a Pittsburgh UDFA signing as the intended exception to the CFBD draft-pick feed. Treat it as pending until the historical row and its independent citation are committed.

Never convert a missing draft-pick match into an UDFA outcome by inference.

## `needs_verification`

`needs_verification` means the source record is intentionally unresolved. It is not a drafted or UDFA fact. Preserve the row and its warning so an operator can complete the source check; do not delete it, fill missing fields from memory, or promote it as verified. Downstream consumers must not treat it as eligible verified evidence.

Issue #243 originally named `te-daequan-wright` as an example. Current `main` has a separately sourced verified UDFA-signing record for that player, so do not recreate the old placeholder or use it as evidence that the historical backfill is complete.

## Player ID aliases

`PLAYER_ID_ALIASES` is an intended resolution layer for a genuine disagreement between a stable alpha ID and a stored draft-result ID. No such map exists in `lib/rookies/draftResults.js` at the revalidation pin above, so this document does not claim alias behavior is implemented.

If an alias layer is introduced, add the narrow mapping and a regression test at the join boundary. Do not rewrite historical IDs merely to make a join pass, and do not use an ID alias to solve a display-name-only difference.

- **Nick Singleton (`rb-nick-singleton`)**: issue #243 records a prior `rb-nicholas-singleton` mismatch. Current processed 2026 data uses `rb-nick-singleton`; retain this as an edge-case test, not as evidence of an existing alias map.

## Change checklist

1. Pin the upstream source and class year.
2. Record every manual override and non-CFBD exception.
3. Resolve ambiguous teams through `nflTeamId`.
4. Reject duplicate IDs, silent fuzzy matches, and inferred UDFA outcomes.
5. Preserve unresolved rows as `needs_verification`.
6. Validate row counts, source fields, and alpha-to-result joins.
7. Update this document when #242 lands so intended and implemented state agree.
