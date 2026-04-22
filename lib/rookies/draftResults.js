const DAY_BY_ROUND = {
  1: 1,
  2: 2,
  3: 2,
  4: 3,
  5: 3,
  6: 3,
  7: 3,
};

export function deriveDraftCapitalTier(round, overallPick) {
  if (!Number.isFinite(round)) return null;
  if (round === 1 && Number.isFinite(overallPick) && overallPick <= 16) return 'premium_round_1';
  if (round === 1) return 'round_1';
  if (round === 2) return 'round_2';
  if (round === 3) return 'round_3';
  if (round >= 4 && round <= 5) return 'day_3_priority';
  if (round >= 6 && round <= 7) return 'late_day_3';
  return null;
}

export function normalizeDraftResult(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const playerId = String(raw.player_id ?? '').trim().toLowerCase();
  if (!playerId) return null;

  const draftRound = Number.isFinite(raw.draft_round) ? raw.draft_round : null;
  const overallPick = Number.isFinite(raw.overall_pick) ? raw.overall_pick : null;
  const isUdfa = Boolean(raw.is_udfa) || (!draftRound && !overallPick);
  const draftDay = Number.isFinite(raw.draft_day)
    ? raw.draft_day
    : (!isUdfa ? (DAY_BY_ROUND[draftRound] ?? null) : null);

  return {
    player_id: playerId,
    nfl_team: typeof raw.nfl_team === 'string' ? raw.nfl_team : null,
    draft_round: draftRound,
    overall_pick: overallPick,
    draft_day: draftDay,
    draft_capital_tier: typeof raw.draft_capital_tier === 'string'
      ? raw.draft_capital_tier
      : (isUdfa ? 'udfa' : deriveDraftCapitalTier(draftRound, overallPick)),
    is_udfa: isUdfa,
  };
}

export function keyByPlayerId(rows) {
  return new Map(
    rows
      .map(normalizeDraftResult)
      .filter(Boolean)
      .map((row) => [row.player_id, row]),
  );
}
