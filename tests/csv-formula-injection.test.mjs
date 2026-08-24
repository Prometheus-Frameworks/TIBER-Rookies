import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import { buildBoardCsv, buildCompareCsv } from '../lib/rookies/exportCsv.js';
import { buildDevyCsv } from '../lib/devy/exportDevyCsv.js';

// Issue #274, Finding 2: CSV cells opening with =, +, - or @ are executed as
// formulas by Excel/Sheets. Every live export helper must prefix them with a
// single apostrophe before its existing comma/quote/newline quoting.
const DANGEROUS_PREFIXES = ['=', '+', '-', '@'];

const PAYLOADS = {
  '=': '=1+1',
  '+': '+1+1',
  '-': '-1+1',
  '@': '@SUM(A1:A2)',
};

// --- workbench.js loader -----------------------------------------------------
// cards/rookies/workbench/workbench.js is a browser module: it reads
// `document` at module scope and imports via a server-absolute path, so it
// cannot be imported under Node. Its CSV helpers are extracted from the
// shipped source instead, which keeps this test bound to the real bytes.
const workbenchPath = new URL('../cards/rookies/workbench/workbench.js', import.meta.url);
const workbenchSource = fs.readFileSync(workbenchPath, 'utf8');

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `expected function ${name}() in workbench.js`);
  let depth = 0;
  for (let i = source.indexOf('{', start); i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    else if (source[i] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error(`unbalanced braces extracting ${name}() from workbench.js`);
}

const { toCsvValue: workbenchCsvValue, buildCsv: workbenchBuildCsv } = new Function(
  `${extractFunction(workbenchSource, 'toCsvValue')}
   ${extractFunction(workbenchSource, 'buildCsv')}
   return { toCsvValue, buildCsv };`,
)();

// The exact header list and tag normalization used by exportJournalCsv().
const JOURNAL_HEADERS = [
  'candidate_id', 'source_entry_id', 'player_name', 'team', 'position', 'entity_type',
  'claim_summary', 'model_impact', 'confidence', 'needs_verification', 'review_status',
  'source_type', 'positive_signal_tags', 'risk_tags', 'context_tags',
];

const normalizeJournalRow = (row) => ({
  ...row,
  positive_signal_tags: JSON.stringify(row.positive_signal_tags),
  risk_tags: JSON.stringify(row.risk_tags),
  context_tags: JSON.stringify(row.context_tags),
});

// --- CSV reader --------------------------------------------------------------
// Returns raw cells with quoting intact, so assertions can inspect the exact
// emitted leading character rather than a re-normalized value.
function parseCsvRaw(text) {
  const rows = [[]];
  let cell = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      cell += ch;
      if (ch === '"') {
        if (text[i + 1] === '"') { cell += '"'; i += 1; } else { inQuotes = false; }
      }
      continue;
    }
    if (ch === '"') { inQuotes = true; cell += ch; continue; }
    if (ch === ',') { rows[rows.length - 1].push(cell); cell = ''; continue; }
    if (ch === '\n') { rows[rows.length - 1].push(cell); cell = ''; rows.push([]); continue; }
    cell += ch;
  }
  rows[rows.length - 1].push(cell);
  return rows;
}

const unquote = (cell) => (cell.startsWith('"') && cell.endsWith('"') && cell.length >= 2
  ? cell.slice(1, -1).replace(/""/g, '"')
  : cell);

// What a spreadsheet sees first inside the field, ignoring CSV quoting.
const leadingChar = (cell) => (cell.startsWith('"') ? cell.slice(1, 2) : cell.slice(0, 1));

function assertNeutralized(cell, original) {
  assert.equal(leadingChar(cell), "'", `expected apostrophe guard, got cell ${JSON.stringify(cell)}`);
  assert.ok(!DANGEROUS_PREFIXES.includes(leadingChar(cell)), 'field must not open with a formula character');
  assert.equal(unquote(cell), `'${original}`, 'guard must prepend exactly one apostrophe and preserve the value');
}

// --- surfaces under test -----------------------------------------------------
// Each surface injects a value through a real live export path and reports the
// raw cell that value lands in.
const SURFACES = [
  {
    name: 'lib/rookies/exportCsv.js :: buildBoardCsv',
    cellFor(value) {
      const csv = buildBoardCsv([{ name: value, alphaStatus: 'scored' }]);
      const rows = parseCsvRaw(csv);
      return rows[1][rows[0].indexOf('name')];
    },
  },
  {
    name: 'lib/rookies/exportCsv.js :: buildCompareCsv',
    cellFor(value) {
      const left = { identity: { name: 'Left Player', school: value } };
      const right = { identity: { name: 'Right Player', school: 'Safe State' } };
      const rows = parseCsvRaw(buildCompareCsv(left, right));
      const schoolRow = rows.find((row) => row[0] === 'School');
      return schoolRow[1];
    },
  },
  {
    name: 'lib/devy/exportDevyCsv.js :: buildDevyCsv',
    cellFor(value) {
      const csv = buildDevyCsv([{ player_name: value }]);
      const rows = parseCsvRaw(csv);
      return rows[1][rows[0].indexOf('player_name')];
    },
  },
  {
    name: 'cards/rookies/workbench/workbench.js :: buildCsv (players export)',
    cellFor(value) {
      const rows = parseCsvRaw(workbenchBuildCsv(['player_name'], [{ player_name: value }]));
      return rows[1][0];
    },
  },
  {
    name: 'cards/rookies/workbench/workbench.js :: buildCsv (journal export)',
    cellFor(value) {
      const csv = workbenchBuildCsv(JOURNAL_HEADERS, [normalizeJournalRow({
        candidate_id: 'cand-1',
        claim_summary: value,
        positive_signal_tags: ['burst'],
        risk_tags: [],
        context_tags: ['role'],
      })]);
      const rows = parseCsvRaw(csv);
      return rows[1][rows[0].indexOf('claim_summary')];
    },
  },
];

// --- 1. all four prefixes, every surface ------------------------------------
for (const surface of SURFACES) {
  for (const prefix of DANGEROUS_PREFIXES) {
    test(`${surface.name} neutralizes a leading "${prefix}"`, () => {
      const payload = PAYLOADS[prefix];
      assertNeutralized(surface.cellFor(payload), payload);
    });
  }

  // --- 2. dangerous values that also need CSV quoting -----------------------
  test(`${surface.name} guards a dangerous value containing a comma`, () => {
    const payload = '=SUM(1,2)';
    const cell = surface.cellFor(payload);
    assert.ok(cell.startsWith('"') && cell.endsWith('"'), 'comma value must stay quoted');
    assertNeutralized(cell, payload);
  });

  test(`${surface.name} guards a dangerous value containing a double quote`, () => {
    const payload = '=HYPERLINK("http://evil.test")';
    const cell = surface.cellFor(payload);
    assert.ok(cell.startsWith('"') && cell.endsWith('"'), 'quote value must stay quoted');
    assert.ok(cell.includes('""'), 'inner quotes must stay doubled');
    assertNeutralized(cell, payload);
  });

  test(`${surface.name} guards a dangerous value containing CR/LF`, () => {
    const payload = '@cmd\r\nsecond line';
    const cell = surface.cellFor(payload);
    assert.ok(cell.startsWith('"') && cell.endsWith('"'), 'newline value must stay quoted');
    assertNeutralized(cell, payload);
  });

  // --- 3. safe values are untouched (no double-neutralizing) ----------------
  test(`${surface.name} leaves ordinary text unchanged`, () => {
    const cell = surface.cellFor('Marvin Harrison Jr.');
    assert.equal(cell, 'Marvin Harrison Jr.');
    assert.equal(leadingChar(cell), 'M');
  });

  test(`${surface.name} leaves an existing quoted field unchanged`, () => {
    const payload = 'Smith, John "JJ"';
    const cell = surface.cellFor(payload);
    assert.equal(cell, '"Smith, John ""JJ"""');
    assert.equal(unquote(cell), payload, 'no apostrophe added to a safe quoted value');
  });

  test(`${surface.name} does not stack apostrophes on an already-guarded value`, () => {
    const cell = surface.cellFor("'=1+1");
    assert.equal(unquote(cell), "'=1+1", 'a value already starting with an apostrophe is safe as-is');
  });

  // The guard is type-aware, so every surface must let a real number through.
  test(`${surface.name} preserves a genuine negative number`, () => {
    const cell = surface.cellFor(-3.5);
    assert.equal(cell, '-3.5', 'a real negative number must stay a numeric cell');
    assert.ok(!cell.startsWith("'"), 'no apostrophe on a genuine number');
  });

  test(`${surface.name} guards the string form of that same value`, () => {
    assert.equal(unquote(surface.cellFor('-3.5')), "'-3.5", 'a string is guarded even when it looks numeric');
  });
}

// --- 4. nullish + numeric behavior preserved --------------------------------
test('nullish and numeric handling is unchanged across the shared helpers', () => {
  // workbench buildCsv takes raw values, so nullish/numeric pass straight through.
  const rows = parseCsvRaw(workbenchBuildCsv(
    ['a', 'b', 'c', 'd'],
    [{ a: null, b: undefined, c: 0, d: 42.5 }],
  ));
  assert.deepEqual(rows[1], ['', '', '0', '42.5']);

  // A missing key is still an empty cell, not "undefined".
  assert.equal(workbenchCsvValue(undefined), '');
  assert.equal(workbenchCsvValue(null), '');
  assert.equal(workbenchCsvValue(0), '0');
});

test('buildDevyCsv keeps nullish fields empty and joins array fields', () => {
  const rows = parseCsvRaw(buildDevyCsv([{ player_name: 'Safe Name', development_tags: ['a', 'b'] }]));
  const header = rows[0];
  assert.equal(rows[1][header.indexOf('school')], '', 'missing field stays empty');
  assert.equal(rows[1][header.indexOf('development_tags')], 'a|b');
  assert.equal(rows[1][header.indexOf('devy_active_status')], 'active_devy', 'derived status preserved');
});

test('buildBoardCsv preserves numeric formatting and unscored blanks', () => {
  const rows = parseCsvRaw(buildBoardCsv([
    { name: 'Scored Player', alphaStatus: 'scored', rookieGrade: 91.25, classRank: 3 },
    { name: 'Unscored Player', alphaStatus: 'not_scored' },
  ]));
  const header = rows[0];
  assert.equal(rows[1][header.indexOf('board_rank')], '1');
  assert.equal(rows[1][header.indexOf('rookie_grade')], '91.3', 'toFixed(1) formatting preserved');
  assert.equal(rows[1][header.indexOf('class_rank')], '3');
  assert.equal(rows[2][header.indexOf('board_rank')], '', 'unscored rows keep a blank rank');
  assert.equal(rows[2][header.indexOf('rookie_grade')], '', 'missing score stays empty');
});

// --- 4b. genuine numbers stay numeric -------------------------------------
// The guard is type-aware: a JS number cannot carry a formula expression, so
// finite numbers are exempt and negative values remain numeric cells. A
// numeric-looking *string* is still guarded, because a string can.
test('buildBoardCsv preserves a numeric negative consensusDelta', () => {
  const rows = parseCsvRaw(buildBoardCsv([
    { name: 'Delta Player', alphaStatus: 'scored', consensusDelta: -3.5 },
  ]));
  const cell = rows[1][rows[0].indexOf('consensus_delta_positional')];
  assert.equal(cell, '-3.5', 'a real negative number must stay a numeric cell');
  assert.ok(!cell.startsWith("'"), 'no apostrophe on a genuine number');
});

test('workbench buildCsv preserves a numeric negative post_draft_delta', () => {
  const rows = parseCsvRaw(workbenchBuildCsv(
    ['player_name', 'post_draft_delta'],
    [{ player_name: 'Zachariah Branch', post_draft_delta: -0.8 }],
  ));
  assert.equal(rows[1][1], '-0.8');
  assert.ok(!rows[1][1].startsWith("'"));
});

test('positive, zero and fractional numbers are unchanged', () => {
  const rows = parseCsvRaw(workbenchBuildCsv(
    ['a', 'b', 'c', 'd', 'e'],
    [{ a: 0, b: -0, c: 12, d: 42.5, e: -1.3 }],
  ));
  assert.deepEqual(rows[1], ['0', '0', '12', '42.5', '-1.3']);
  for (const raw of [0, -0, 12, 42.5, -1.3, -0.8, Number.MIN_SAFE_INTEGER]) {
    assert.equal(workbenchCsvValue(raw), String(raw), `numeric ${raw} must pass through`);
  }
});

test('a numeric-looking string is still guarded (type-aware, not value-aware)', () => {
  assert.equal(workbenchCsvValue('-3.5'), "'-3.5", 'string "-3.5" is not a number');
  assert.equal(workbenchCsvValue(-3.5), '-3.5', 'number -3.5 is');
  // Non-finite numbers fall back to the guard rather than emitting bare "-Infinity".
  assert.equal(workbenchCsvValue(-Infinity), "'-Infinity");
  assert.equal(workbenchCsvValue(NaN), 'NaN', 'NaN has no dangerous prefix');
});

test('the string payload "-1+1" remains neutralized in every helper', () => {
  for (const surface of SURFACES) {
    const cell = surface.cellFor('-1+1');
    assert.equal(unquote(cell), "'-1+1", `${surface.name} must still guard the string -1+1`);
  }
});

// Real-data regression for the exact case flagged in review: the promoted
// postdraft artifact carries genuine negative post_draft_delta values.
test('promoted postdraft artifact negatives survive as numeric cells', () => {
  const artifact = JSON.parse(fs.readFileSync(
    new URL('../exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.json', import.meta.url),
    'utf8',
  ));
  const deltas = artifact.rows
    .map((row) => row.post_draft_delta)
    .filter((delta) => typeof delta === 'number');
  assert.ok(deltas.length > 0, 'artifact should carry numeric deltas');
  for (const delta of deltas) {
    assert.equal(workbenchCsvValue(delta), String(delta));
    assert.ok(!String(workbenchCsvValue(delta)).startsWith("'"));
  }
});

// --- 5. data-derived headers are guarded too --------------------------------
test('buildCompareCsv guards a dangerous player name used as a column header', () => {
  const left = { identity: { name: '=cmd|calc', school: 'State' } };
  const right = { identity: { name: 'Right Player', school: 'Tech' } };
  const header = parseCsvRaw(buildCompareCsv(left, right))[0];
  assert.equal(header[1], "'=cmd|calc");
  assert.ok(!DANGEROUS_PREFIXES.includes(leadingChar(header[1])));
});

// --- 6. negative control -----------------------------------------------------
// A verbatim copy of the pre-change helper, proving the corpus is not
// vacuously green: the old code emitted these payloads unguarded.
function legacyEscCsvCell(value) {
  const str = String(value ?? '');
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

test('negative control: the prior implementation emitted unsafe leading characters', () => {
  for (const prefix of DANGEROUS_PREFIXES) {
    const payload = PAYLOADS[prefix];
    const legacy = legacyEscCsvCell(payload);
    assert.equal(leadingChar(legacy), prefix, 'pre-change helper left the formula character exposed');
    assert.ok(DANGEROUS_PREFIXES.includes(leadingChar(legacy)));
  }
  // ...including when the value also required quoting.
  assert.equal(leadingChar(legacyEscCsvCell('=SUM(1,2)')), '=');
  // The legacy helper is otherwise byte-identical, so safe values must agree
  // with the hardened helpers — the guard is the only behavioral difference.
  for (const safe of ['Marvin Harrison Jr.', 'Smith, John "JJ"', '', '0']) {
    assert.equal(legacyEscCsvCell(safe), workbenchCsvValue(safe));
  }
});

test('negative control: every live helper source carries the guard', () => {
  const sources = [
    'lib/devy/exportDevyCsv.js',
    'lib/rookies/exportCsv.js',
    'cards/rookies/workbench/workbench.js',
  ];
  for (const rel of sources) {
    const src = fs.readFileSync(new URL(`../${rel}`, import.meta.url), 'utf8');
    assert.match(src, /\/\^\[=\+\\-@\]\/\.test\(/, `${rel} must retain the formula-injection guard`);
  }
});
