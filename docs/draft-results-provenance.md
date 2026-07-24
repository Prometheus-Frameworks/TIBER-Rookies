# Draft-results provenance protocol

> Status: documentation guardrail, not an implementation claim.
>
> Revalidated against `main` at `2ef92faf9a9c91a393f53e9140428451529a1c48`. [Issue #242](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/242) remains open: the 2022–2025 processed draft-result files are empty, and `lib/rookies/draftResults.js` does not currently implement `PLAYER_ID_ALIASES`.
>
> The rules below define the intended historical-backfill boundary. Examples from issue #243 remain pending until their corresponding source, data, and code state is present and verified.

## Scope and source boundary

- Draft-result artifacts carry observed NFL draft or verified UDFA facts. They do not create a score, projection, or inferred landing-spot assessment.
- For the historical 2022–2025 backfill tracked in #242, CFBD is TIBER-Data's designated primary upstream source (`GET /draft/picks?year={year}`). TIBER-Data owns CFBD ingestion, normalization, provenance, and production of the governed `exports/promoted/nfl_draft_results/nfl_draft_results_{year}.json` artifact. TIBER-Rookies consumes that artifact through `scripts/ingest_draft_results_from_tiber_data.py`; it must not fetch CFBD directly or maintain a second authoritative draft-results path.
- The CFBD fields used by the TIBER-Data producer are `name`, `nflTeam`, `nflTeamId`, `overall`, `round`, and `pick`.
- Official draft facts for other seasons must also arrive through a governed TIBER-Data artifact. TIBER-Data may use a separately verified public source, but must preserve each row's actual lineage and never relabel a non-CFBD row as CFBD-derived.
- Keep `source_name`, `source_url`, `source_status`, and `upstream_provenance_status` explicit wherever the governed and consumer schemas support them.

## Team disambiguation

CFBD can return the same short city name for two teams. The TIBER-Data producer must resolve those rows with `nflTeamId`, not a guess based on city text:

| CFBD `nflTeamId` | TIBER team |
|---:|:---|
| `20` | `NYJ` |
| `19` | `NYG` |
| `24` | `LAC` |
| `14` | `LAR` |

An unknown or conflicting team identifier must fail closed for operator review.

## Name matching and manual overrides

The TIBER-Data historical build path starts with deterministic normalized-name matching. It must not silently accept a fuzzy match. If CFBD uses a legal name while TIBER uses a familiar name, that build path may add an explicit `NAME_OVERRIDES` entry. Every entry must record the upstream spelling, the repository identity, and why the override is necessary.

- **Tank Dell (`wr-tank-dell`)**: issue #243 records CFBD's `Nathaniel Dell` spelling as the intended manual-override case. This remains a pending edge case until the TIBER-Data historical backfill, override, and governed artifact have been implemented and consumed.

## UDFA rows

Absence from CFBD draft picks does not prove that a player signed as an UDFA. Under the current cross-repo contract, UDFAs are a separate manual TIBER-Rookies input rather than rows in TIBER-Data's official NFL Draft Results artifact. Add an UDFA row only when a separate public source verifies the signing.

The row must use `is_udfa: true`, null draft round/pick values, an appropriate UDFA status, the source citation, and `upstream_provenance_status: "source_verified"` where that field is part of the target schema. Explain the exception in `source_name` or the row's source-note field.

- **Jaylen Warren (`rb-jaylen-warren`)**: issue #243 records a Pittsburgh UDFA signing as the intended exception to the CFBD draft-pick feed. Treat it as pending until the historical row and its independent citation are committed.

Never convert a missing draft-pick match into an UDFA outcome by inference.

## `needs_verification`

`needs_verification` means the source record is intentionally unresolved, not a drafted or UDFA fact. Preserve it only in TIBER-Data source-review or other non-runtime staging with its warning so an operator can complete the source check; do not delete it or fill missing fields from memory. Until verified, the row must remain outside `data/processed/{year}_draft_results.json` and every other model-facing or runtime artifact. It cannot affect scoring, post-draft adjustments, ranking, presentation, or downstream inference. The current Rookies ingestion adapter accepts flagged `needs_verification` rows, and the runtime does not retain their provenance status, so this document does not claim that an enforcement gate exists. The historical backfill must not be consumed until either TIBER-Data excludes unresolved rows from the governed artifact supplied to Rookies or the Rookies ingestion boundary rejects them.

Issue #243 originally named `te-daequan-wright` as an example. Current `main` has a separately sourced verified UDFA-signing record for that player, so do not recreate the old placeholder or use it as evidence that the historical backfill is complete.

## Player ID aliases

`PLAYER_ID_ALIASES` is an intended resolution layer for a genuine disagreement between a stable alpha ID and a stored draft-result ID. No such map exists in `lib/rookies/draftResults.js` at the revalidation pin above, so this document does not claim alias behavior is implemented.

If an alias layer is introduced, add the narrow mapping and a regression test at the join boundary. Do not rewrite historical IDs merely to make a join pass, and do not use an ID alias to solve a display-name-only difference.

- **Nick Singleton (`rb-nick-singleton`)**: issue #243 records a prior `rb-nicholas-singleton` mismatch. Current processed 2026 data uses `rb-nick-singleton`; retain this as an edge-case test, not as evidence of an existing alias map.

## Change checklist

1. Pin the governed TIBER-Data artifact, its upstream source, and class year.
2. Record every manual override and non-CFBD exception.
3. Resolve ambiguous teams through `nflTeamId` in the TIBER-Data producer.
4. Reject duplicate IDs, silent fuzzy matches, and inferred UDFA outcomes.
5. Quarantine unresolved rows outside every processed runtime artifact until verified.
6. Validate row counts, source fields, alpha-to-result joins, and the absence of unresolved model-facing rows.
7. Update this document when #242 lands so intended and implemented state agree.
