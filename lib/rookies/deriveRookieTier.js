const TIER_RULES = [
  { key: 'tier_1', label: 'Top cluster', minGrade: 75 },
  { key: 'tier_2', label: 'Strong starter tier', minGrade: 70 },
  { key: 'tier_3', label: 'Development tier', minGrade: 65 },
  { key: 'tier_4', label: 'Swing tier', minGrade: Number.NEGATIVE_INFINITY },
];

export function deriveRookieTier(rookieGrade) {
  if (rookieGrade == null) {
    return { key: 'unscored', label: 'Unscored cluster', bucketOrder: 99 };
  }

  const matched = TIER_RULES.find((rule) => rookieGrade >= rule.minGrade) ?? TIER_RULES[TIER_RULES.length - 1];
  return {
    key: matched.key,
    label: matched.label,
    bucketOrder: TIER_RULES.findIndex((rule) => rule.key === matched.key),
  };
}

export function getRookieTierRules() {
  return TIER_RULES.map((rule) => ({ ...rule }));
}
