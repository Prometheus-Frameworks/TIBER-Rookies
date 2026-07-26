# Phase 1B reconstruction note

This draft branch was rebuilt cleanly on the merged Phase 1A main commit (`a825431402f89f7ec4fe69e72de073ca4b301ea3`) after the original local-only checkpoint was lost when the conversation branched.

The recovered truth-layer subset includes:

- explicit `NEUTRAL_DEFAULT` athletic-source labeling;
- exclusion of neutral priors from observed-evidence selection;
- removal of neutral-prior athletic edge claims in compare;
- verdict copy conditional on actual shared observed evidence.

The remaining #280 presentation batch is completed on this branch before review: shared PPR scaling, mobile containment, radar label geometry, evidence-readiness copy, and regression coverage. Live 390px validation remains a separate non-production preview gate.

No model weights, governed artifacts, narratives, Railway settings, or production deployment state are changed.
