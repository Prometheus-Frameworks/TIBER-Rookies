# Archived 2023 contaminated seed rows

This directory preserves the exact defect-bearing rows identified by
[TIBER-Rookies #285](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/285).
They are fixtures of what previously ran, not facts to consume.

The complete seed files remain byte-for-byte unchanged at their original
paths. `contaminated_seed_rows_v0.json` copies only the rows implicated by the
five confirmed findings and pins the source commit and file hashes. Candidate
corrections live separately under
`data/candidate/2023_input_integrity/v0.1.0/`.

Do not use these archived rows for scoring, reconstruction, regeneration, or
promotion. Their purpose is correction lineage and regression evidence.
