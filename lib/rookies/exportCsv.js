import { compareRookies } from '/lib/rookies/compareRookies.js';

function escCsvCell(value) {
  const str = String(value ?? '');
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function toCsvString(headers, rows) {
  return [
    headers.map(escCsvCell).join(','),
    ...rows.map((row) => headers.map((h) => escCsvCell(row[h])).join(',')),
  ].join('\n');
}

export function downloadCsv(csvString, filename) {
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function buildBoardCsv(rows) {
  const headers = [
    'board_rank', 'class_rank', 'name', 'position', 'school', 'draft_class',
    'tier', 'rookie_grade', 'athletic_score', 'production_score', 'draft_capital_score',
    'consensus_delta_positional', 'evidence_tier', 'breakout_age',
  ];
  const data = rows.map((row, i) => ({
    board_rank: i + 1,
    class_rank: row.classRank ?? '',
    name: row.name ?? '',
    position: row.position ?? '',
    school: row.school ?? '',
    draft_class: row.draftClass ?? '',
    tier: row.tier?.label ?? '',
    rookie_grade: row.rookieGrade?.toFixed(1) ?? '',
    athletic_score: row.athleticScore?.toFixed(1) ?? '',
    production_score: row.productionScore?.toFixed(1) ?? '',
    draft_capital_score: row.draftCapitalScore?.toFixed(1) ?? '',
    consensus_delta_positional: row.consensusDelta ?? '',
    evidence_tier: row.evidenceTier ?? '',
    breakout_age: row.breakoutAge ?? '',
  }));
  return toCsvString(headers, data);
}

export function buildCompareCsv(leftCard, rightCard) {
  const compared = compareRookies(leftCard, rightCard);
  const leftName = leftCard?.identity?.name ?? 'Left';
  const rightName = rightCard?.identity?.name ?? 'Right';
  const headers = ['metric', leftName, rightName, 'edge'];

  const rows = [
    { metric: 'Position',     [leftName]: leftCard?.identity?.position ?? '',                    [rightName]: rightCard?.identity?.position ?? '',                    edge: '' },
    { metric: 'School',       [leftName]: leftCard?.identity?.school ?? '',                      [rightName]: rightCard?.identity?.school ?? '',                      edge: '' },
    { metric: 'Draft Class',  [leftName]: leftCard?.identity?.classYear ?? '',                   [rightName]: rightCard?.identity?.classYear ?? '',                   edge: '' },
    { metric: 'Rookie Grade', [leftName]: leftCard?.summary?.rookieGrade?.toFixed(1) ?? '',      [rightName]: rightCard?.summary?.rookieGrade?.toFixed(1) ?? '',      edge: `delta ${compared.overallDelta?.toFixed(1) ?? 'N/A'}` },
    { metric: 'Verdict',      [leftName]: '',                                                    [rightName]: '',                                                    edge: compared.verdict?.headline ?? '' },
    ...compared.scoreComparisons.map((r) => ({
      metric: r.label,
      [leftName]: r.leftValue?.toFixed(1) ?? '',
      [rightName]: r.rightValue?.toFixed(1) ?? '',
      edge: r.winner,
    })),
    ...compared.evidenceComparisons.map((r) => ({
      metric: r.label,
      [leftName]: r.leftDisplay ?? '',
      [rightName]: r.rightDisplay ?? '',
      edge: r.winner,
    })),
  ];

  return toCsvString(headers, rows);
}
