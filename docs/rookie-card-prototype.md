# Rookie Card Prototype Handoff (2026 class)

## PR8 update summary (compare surface)

- Added a dedicated rookie compare route so two real 2026 rookies can be evaluated side by side.
- Added reusable compare UI components (selector + compare view) that render from existing mapped rookie card objects.
- Added deterministic compare helper logic that returns verdict, grade delta, score/evidence rows, and compare notes.
- Added lightweight compare launch affordances from class board (`Open rookie compare tool`) and compact cards (`Compare from this player`).

## Routes

- `/cards/rookies/index.html` (class board + compact cards + controls)
- `/cards/rookies/player.html?slug=<player_id>` (full detail route)
- `/cards/rookies/compare/index.html?left=<slug>&right=<slug>` (two-player compare surface)
- `/cards/rookies/wr-malik-ford/index.html` (direct single-player entry for one real rookie)

## Source data used (unchanged)

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/raw/2026_combine_results.json`
- `data/processed/2026_college_production.json`
- `data/processed/2026_draft_capital_proxy.json`

## Compare verdict logic (transparent + deterministic)

Helper: `lib/rookies/compareRookies.js`

Returned compare object includes:

- `overallDelta` (left Rookie Grade − right Rookie Grade)
- `verdict` (`Lean <name>`, `Close profile`, or `Insufficient edge`)
- `scoreComparisons` (shared score buckets with winner/tie per row)
- `evidenceComparisons` (shared metric rows sorted by absolute edge)
- `sharedPosition` and `notes` (context + data-availability caveats)

Verdict decision order:

1. Compare overall Rookie Grade if available.
2. Check edge balance from evidence rows.
3. Emit one of:
   - `Lean Player` (clear/slight edge)
   - `Close profile` (small grade delta + narrow evidence split)
   - `Insufficient edge` (grade missing / sparse evidence)

No fake model narration is used.

## Evidence row selection behavior

- Evidence rows are derived from existing position-aware selection helper (`selectRookieEvidenceMetrics`) for each card.
- Compare helper intersects shared metric labels and only keeps rows with values on both sides.
- Rows are sorted by absolute delta and capped:
  - same-position: up to 6 rows
  - cross-position: lighter cap (up to 4 rows)
- Directional honesty is enforced (`40 Yard Dash (s)` treats lower time as better).

## Same-position vs cross-position handling

- **Same position:** richer apples-to-apples evidence rows with stronger metric table.
- **Cross position:** intentionally lighter evidence usage, with more weight on overall grade/scores and explicit notes.
- If shared evidence is too sparse, compare view falls back to honest unavailable copy instead of fabricating precision.

## Data honesty constraints still enforced

- No fabricated school/age/comps/season rows.
- No fake export claims (PNG/PDF is still TODO).
- If artifacts do not carry a metric, card sections omit it or show explicit unavailable copy.
- Verdict remains deterministic and inspectable from visible data fields.

## Next likely expansion path

1. Promote richer processed rookie profile artifact (school/age/bio + position-native stat fields).
2. Add board-level “compare queue” flow (pick first, pick second) with persisted query state.
3. Add role-specific compare templates once additional trustworthy metrics are in promoted artifacts.
4. Reuse compare helper output for future draft-room decision views and exports.
