import { selectRookieEvidenceMetrics } from '/lib/rookies/selectRookieEvidenceMetrics.js';

const GRADE_CLOSE_DELTA = 1.5;
const GRADE_LEAN_DELTA = 4;
const MAX_EVIDENCE_ROWS = 6;

function round(value, decimals = 1) {
  if (value == null || Number.isNaN(Number(value))) return null;
  const factor = 10 ** decimals;
  return Math.round(Number(value) * factor) / factor;
}

function compareDirectionByLabel(label) {
  return label === '40 Yard Dash (s)' ? 'lower' : 'higher';
}

function numericDelta(left, right, direction = 'higher') {
  if (left == null || right == null) return null;
  const raw = left - right;
  return direction === 'lower' ? -raw : raw;
}

function winnerFromDelta(delta) {
  if (delta == null || delta === 0) return 'tie';
  return delta > 0 ? 'left' : 'right';
}

function scoreComparisons(leftCard, rightCard) {
  const leftScores = new Map((leftCard?.scores ?? []).map((score) => [score.label, score]));
  const rightScores = new Map((rightCard?.scores ?? []).map((score) => [score.label, score]));
  const labels = [...new Set([...leftScores.keys(), ...rightScores.keys()])];

  return labels
    .map((label) => {
      const left = leftScores.get(label)?.value ?? null;
      const right = rightScores.get(label)?.value ?? null;
      const delta = numericDelta(left, right, 'higher');
      return {
        label,
        leftValue: round(left),
        rightValue: round(right),
        delta: round(delta),
        winner: winnerFromDelta(delta),
      };
    })
    .filter((row) => row.leftValue != null || row.rightValue != null);
}

function buildEvidenceComparisons(leftCard, rightCard, samePosition) {
  const leftMetrics = selectRookieEvidenceMetrics(leftCard, samePosition ? 'full' : 'compact');
  const rightMetrics = selectRookieEvidenceMetrics(rightCard, samePosition ? 'full' : 'compact');
  const leftByLabel = new Map(leftMetrics.map((metric) => [metric.label, metric]));
  const rightByLabel = new Map(rightMetrics.map((metric) => [metric.label, metric]));
  const sharedLabels = leftMetrics
    .map((metric) => metric.label)
    .filter((label) => rightByLabel.has(label));

  return sharedLabels
    .map((label) => {
      const leftMetric = leftByLabel.get(label);
      const rightMetric = rightByLabel.get(label);
      const direction = compareDirectionByLabel(label);
      const delta = numericDelta(leftMetric?.value ?? null, rightMetric?.value ?? null, direction);
      return {
        label,
        leftDisplay: leftMetric?.display ?? 'N/A',
        rightDisplay: rightMetric?.display ?? 'N/A',
        leftValue: leftMetric?.value ?? null,
        rightValue: rightMetric?.value ?? null,
        delta: round(delta, 2),
        winner: winnerFromDelta(delta),
        direction,
      };
    })
    .filter((row) => row.leftValue != null && row.rightValue != null)
    .sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0))
    .slice(0, samePosition ? MAX_EVIDENCE_ROWS : 4);
}

function classRankNote(leftCard, rightCard) {
  const leftRank = leftCard?.summary?.classRank ?? null;
  const rightRank = rightCard?.summary?.classRank ?? null;
  if (leftRank == null || rightRank == null) return 'Class rank unavailable for one or both rookies.';

  if (leftRank === rightRank) return `Both are currently class rank #${leftRank}.`;

  const winner = leftRank < rightRank ? leftCard.identity.name : rightCard.identity.name;
  const gap = Math.abs(leftRank - rightRank);
  return `${winner} is ranked ${gap} spot${gap === 1 ? '' : 's'} higher in current class ordering.`;
}

function verdictFromCompare(leftCard, rightCard, overallDelta, evidenceRows) {
  const leftName = leftCard?.identity?.name ?? 'Left rookie';
  const rightName = rightCard?.identity?.name ?? 'Right rookie';

  if (overallDelta == null) {
    return {
      code: 'insufficient',
      headline: 'Insufficient edge',
      detail: 'Rookie Grade missing for one or both players, so only descriptive comparison is shown.',
    };
  }

  const evidenceBalance = evidenceRows.reduce((acc, row) => {
    if (row.winner === 'left') return acc + 1;
    if (row.winner === 'right') return acc - 1;
    return acc;
  }, 0);

  if (Math.abs(overallDelta) <= GRADE_CLOSE_DELTA && Math.abs(evidenceBalance) <= 1) {
    return {
      code: 'close',
      headline: 'Close profile',
      detail: `Overall grades are within ${GRADE_CLOSE_DELTA} points and evidence edges are narrow.`,
    };
  }

  const leanLeft = overallDelta > 0 || (Math.abs(overallDelta) <= GRADE_CLOSE_DELTA && evidenceBalance > 0);
  const leanName = leanLeft ? leftName : rightName;
  const leanStrength = Math.abs(overallDelta) >= GRADE_LEAN_DELTA ? 'clear' : 'slight';

  return {
    code: leanLeft ? 'lean-left' : 'lean-right',
    headline: `Lean ${leanName}`,
    detail: `${leanStrength === 'clear' ? 'Clear' : 'Slight'} edge based on Rookie Grade delta and supporting evidence rows.`,
  };
}

export function compareRookies(leftCard, rightCard) {
  const samePosition = leftCard?.identity?.position && leftCard.identity.position === rightCard?.identity?.position;
  const leftGrade = leftCard?.summary?.rookieGrade ?? null;
  const rightGrade = rightCard?.summary?.rookieGrade ?? null;
  const overallDelta = numericDelta(leftGrade, rightGrade, 'higher');
  const scores = scoreComparisons(leftCard, rightCard);
  const evidence = buildEvidenceComparisons(leftCard, rightCard, samePosition);
  const verdict = verdictFromCompare(leftCard, rightCard, overallDelta, evidence);

  const notes = [
    classRankNote(leftCard, rightCard),
    samePosition
      ? 'Same-position compare: evidence rows emphasize apples-to-apples metrics for this role.'
      : 'Cross-position compare: detailed evidence is intentionally limited to shared transparent metrics.',
  ];

  if (!evidence.length) {
    notes.push('Shared evidence metrics were limited, so no detailed edge rows are shown.');
  }

  return {
    sharedPosition: Boolean(samePosition),
    overallDelta: round(overallDelta),
    leftGrade: round(leftGrade),
    rightGrade: round(rightGrade),
    verdict,
    scoreComparisons: scores,
    evidenceComparisons: evidence,
    notes,
  };
}
