function round1(value) {
  return Math.round(value * 10) / 10;
}

export function computeDraftCapitalAdjustment({ draftRound, overallPick, isUdfa }) {
  if (isUdfa) return { delta: -8, note: 'UDFA outcomes carry lower insulation early.', tag: 'udfa_headwind' };
  if (!Number.isFinite(draftRound)) return { delta: 0, note: null, tag: 'pending_draft_data' };
  if (draftRound === 1 && Number.isFinite(overallPick) && overallPick <= 16) {
    return { delta: 5, note: 'Premium Round 1 investment boosts runway.', tag: 'premium_capital' };
  }
  if (draftRound === 1) return { delta: 4, note: 'Round 1 investment supports opportunity insulation.', tag: 'strong_capital' };
  if (draftRound === 2) return { delta: 2, note: 'Round 2 capital improves short-term deployment odds.', tag: 'solid_capital' };
  if (draftRound === 3) return { delta: 1, note: 'Day 2 capital provides moderate opportunity signal.', tag: 'day2_capital' };
  if (draftRound >= 4) return { delta: -1.5, note: 'Day 3 profiles face thinner opportunity insulation.', tag: 'day3_capital' };
  return { delta: 0, note: null, tag: 'pending_draft_data' };
}

export function computeLandingSpotAdjustment() {
  return { delta: 0, note: null, tag: 'landing_spot_pending' };
}

export function computeOpportunityPathAdjustment() {
  return { delta: 0, note: null, tag: 'opportunity_pending' };
}

export function computeEnvironmentFitAdjustment() {
  return { delta: 0, note: null, tag: 'environment_fit_pending' };
}

export function computeInsulationAdjustment() {
  return { delta: 0, note: null, tag: 'insulation_pending' };
}

export function applyPostDraftAdjustments({ preDraftGrade, draftResult }) {
  const draftCapital = computeDraftCapitalAdjustment({
    draftRound: draftResult?.draft_round ?? null,
    overallPick: draftResult?.overall_pick ?? null,
    isUdfa: draftResult?.is_udfa ?? false,
  });
  const landingSpot = computeLandingSpotAdjustment({ draftResult });
  const opportunityPath = computeOpportunityPathAdjustment({ draftResult });
  const environmentFit = computeEnvironmentFitAdjustment({ draftResult });
  const insulation = computeInsulationAdjustment({ draftResult });

  const components = {
    draftCapital,
    landingSpot,
    opportunityPath,
    environmentFit,
    insulation,
  };
  const totalDelta = round1(Object.values(components).reduce((sum, component) => sum + (component.delta ?? 0), 0));
  const postDraftAdjustedGrade = Number.isFinite(preDraftGrade)
    ? round1(Math.max(0, Math.min(100, preDraftGrade + totalDelta)))
    : null;

  return {
    preDraftGrade: Number.isFinite(preDraftGrade) ? preDraftGrade : null,
    postDraftAdjustedGrade,
    postDraftDelta: totalDelta,
    postDraftTag: draftCapital.tag ?? 'post_draft_pending',
    landingSpotNote: landingSpot.note,
    opportunityNote: opportunityPath.note,
    components,
  };
}
