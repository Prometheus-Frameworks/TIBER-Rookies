const SCORE_BANDS = [
  { min: 80, label: 'blue-chip grade band' },
  { min: 72, label: 'priority draft band' },
  { min: 64, label: 'developmental draft band' },
  { min: 0, label: 'long-term project band' },
];

function scoreBandLabel(rookieGrade) {
  if (!Number.isFinite(rookieGrade)) return 'grade pending band';
  return SCORE_BANDS.find((band) => rookieGrade >= band.min)?.label ?? 'grade pending band';
}

function buildArchetypeLabel(position, ras, production, draftCapital) {
  const rolePrefix = position ? `${position} profile` : 'Rookie profile';
  const candidates = [
    { key: 'production', value: production, label: 'production-led' },
    { key: 'athletic', value: ras, label: 'traits-led' },
    { key: 'capital', value: draftCapital, label: 'capital-backed' },
  ].filter((candidate) => Number.isFinite(candidate.value));

  if (!candidates.length) return `${rolePrefix} (limited evidence)`;

  candidates.sort((a, b) => b.value - a.value);
  const top = candidates[0];
  const topLabel = top.value >= 75 ? top.label : 'balanced-signal';
  return `${rolePrefix} (${topLabel})`;
}

function topSignalPhrase({ ras, production, draftCapital }) {
  const candidates = [
    { value: production, phrase: production >= 80 ? 'strong production signal' : 'production signal present' },
    { value: ras, phrase: ras >= 75 ? 'above-baseline athletic signal' : 'athletic signal present' },
    { value: draftCapital, phrase: draftCapital >= 75 ? 'favorable capital signal' : 'capital signal present' },
  ].filter((candidate) => Number.isFinite(candidate.value));

  if (!candidates.length) return 'evidence signal limited';
  candidates.sort((a, b) => b.value - a.value);
  return candidates[0].phrase;
}

export function deriveRookieProfileSummary({ identity, rookieGrade, ras, production, draftCapital, missingInputs = [] }) {
  const archetype = buildArchetypeLabel(identity?.position, ras, production, draftCapital);
  const band = scoreBandLabel(rookieGrade);
  const signalPhrase = topSignalPhrase({ ras, production, draftCapital });
  const missingNote = missingInputs.length ? `missing ${missingInputs.length} model input${missingInputs.length === 1 ? '' : 's'}` : 'full model inputs available';

  return {
    archetype,
    projection: `${identity?.roleLabel ?? 'Role'} pathway`,
    profileSummary: `${archetype} • ${signalPhrase} • ${band}`,
    identityNote: `${signalPhrase}; ${missingNote}.`,
    boardSummary: `${signalPhrase} • ${band}`,
  };
}
