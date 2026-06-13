const POSITION_LABELS = {
  QB: 'Quarterback',
  RB: 'Running Back',
  WR: 'Wide Receiver',
  TE: 'Tight End',
};

const ROLE_BY_POSITION = {
  QB: 'Pocket passer',
  RB: 'Early-down runner',
  WR: 'Receiver profile',
  TE: 'Move tight end',
};

function firstString(values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function normalizeSchool(rawSchool) {
  if (!rawSchool) return null;
  return rawSchool.replace(/\s+/g, ' ').trim();
}

function normalizePosition(rawPosition) {
  if (typeof rawPosition !== 'string') return null;
  const normalized = rawPosition.trim().toUpperCase();
  return normalized || null;
}

export function normalizeRookieIdentity({ alphaPlayer }) {
  const position = normalizePosition(firstString([alphaPlayer?.position, alphaPlayer?.context?.position]));
  const school = normalizeSchool(
    firstString([
      alphaPlayer?.context?.school,
      alphaPlayer?.school,
      alphaPlayer?.program,
    ])
  );

  return {
    name: firstString([alphaPlayer?.player_name, alphaPlayer?.context?.player_name]) ?? 'Unknown Rookie',
    position,
    positionLabel: position ? POSITION_LABELS[position] ?? position : 'Position unavailable',
    roleLabel: position ? ROLE_BY_POSITION[position] ?? 'Role still forming' : 'Role still forming',
    school,
    schoolDisplay: school ?? 'School unavailable in current artifacts',
    classYear: Number.isFinite(alphaPlayer?.context?.class_year) ? alphaPlayer.context.class_year : null,
  };
}
