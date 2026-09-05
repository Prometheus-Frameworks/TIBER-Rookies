// Display/derived CSV state only; never synthesize a raw transition observation.
export function deriveDevyActiveStatus(row) {
  if (row.transition_status === 'active_devy') return 'active_devy';
  if (row.transition_status === 'graduated_to_rookie') {
    return typeof row.rookie_card_slug === 'string' && row.rookie_card_slug.trim()
      ? 'graduated_to_rookie' : 'rookie_card_pending';
  }
  return 'unknown';
}

export function normalizeTransitionMap(payload) {
  const envelopes = ['transitions', 'rows', 'prospects'].filter((key) => Array.isArray(payload?.[key]));
  if (envelopes.length !== 1) throw new Error('Transition envelope unavailable or ambiguous.');
  const map = new Map();
  for (const row of payload[envelopes[0]]) {
    if (!row || typeof row.player_id !== 'string' || !row.player_id.trim()) {
      throw new Error('Malformed transition identity.');
    }
    // Duplicate identities cannot silently select a winner, even if rows agree.
    map.set(row.player_id, map.has(row.player_id) ? null : row);
  }
  return map;
}

export function enrichDevyRows(seedRows, transitionMap) {
  return seedRows.map((row) => {
    const transition = transitionMap.get(row.player_id) ?? {};
    const enriched = {
      ...row,
      identity_source_type: row.identity_provenance?.source_type ?? 'unknown',
      identity_source_urls: row.identity_provenance?.source_urls ?? [],
      transition_status: transition.transition_status ?? '',
      rookie_card_slug: transition.rookie_card_slug ?? '',
    };
    return { ...enriched, devy_active_status: deriveDevyActiveStatus(enriched) };
  });
}

export function readDevySeedRows(payload) {
  if (!Array.isArray(payload?.prospects) || payload.prospects.some((row) =>
    !row || typeof row.player_id !== 'string' || !row.player_id.trim()
    || typeof row.player_name !== 'string' || !row.player_name.trim())) {
    throw new Error('Malformed Devy seed watchlist.');
  }
  return payload.prospects;
}
