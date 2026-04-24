# External Source Hygiene Policy

## Purpose

TIBER-Rookies may review external analyst work only as **qualitative research context** unless explicit written permission or licensing is in place. The project must not ingest, reproduce, or operationalize third-party proprietary analyst content as model data.

## Default rule

Unless licensing terms are documented, external analyst content is treated as reference-only context for human judgment.

## Prohibited uses (without explicit written permission/licensing)

The following are prohibited in this repository and its workflows:

- Scraping third-party analyst websites or services.
- Storing screenshots of third-party reports.
- Copying or paraphrasing substantial proprietary scouting report text.
- Committing paywalled text, tables, rankings, charts, or screenshots.
- Using third-party analyst content as direct model input.
- Creating source-specific model features derived from proprietary analysts or services.
- Training or fine-tuning models on third-party paid/proprietary materials.

## Allowed uses (with hygiene controls)

The following are allowed when handled in a non-reproductive, high-level way:

- Manual qualitative notes from public commentary.
- High-level thematic tags (for example: `separation`, `YAC`, `return_value`, `injury_concern`).
- Tracking source category metadata without reproducing protected expression.
- Licensed-source integration only when permission terms are documented in-repo.

## Safe JSON example (`external_research_signals`)

Use source categories and non-verbatim qualitative flags. Do not store proprietary excerpts.

```json
{
  "external_research_signals": [
    {
      "source_category": "public_commentary",
      "theme_tags": ["separation", "YAC", "injury_concern"],
      "qualitative_summary": "Public scouting discussion generally aligns with on-field separation and after-catch strengths, with some durability caution.",
      "used_in_model_score": false,
      "verbatim_stored": false,
      "licensed": false,
      "license_reference": null
    }
  ]
}
```

If `licensed` is `true`, include a documented license/permission reference and scope before integration.

## Public-writing guidance

- **Okay:** “external public scouting sentiment supported the separation/YAC profile.”
- **Avoid:** reproducing paid report language, screenshots, rankings, or detailed proprietary breakdowns.

## Repo review checklist

Before merging, verify all of the following:

- No screenshots from paid sites.
- No copied analyst report text.
- No scraped data from third-party analyst services.
- No third-party proprietary names embedded in model feature names.
- No unexplained external ranking fields.

## Legal note

This policy is operational guidance and **not legal advice**. Any commercial or licensed external-source usage should be reviewed before launch.
