import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeRookieIdentity } from '../lib/rookies/normalizeRookieIdentity.js';

test('normalizeRookieIdentity maps known positions to labels and roles', () => {
  const out = normalizeRookieIdentity({ alphaPlayer: { player_name: 'Jane Back', position: 'rb' } });
  assert.equal(out.name, 'Jane Back');
  assert.equal(out.position, 'RB'); // upper-cased
  assert.equal(out.positionLabel, 'Running Back');
  assert.equal(out.roleLabel, 'Early-down runner');
});

test('normalizeRookieIdentity falls back through context fields and trims whitespace', () => {
  const out = normalizeRookieIdentity({
    alphaPlayer: { context: { player_name: 'From Context', school: '  Ohio   State ', class_year: 2026 } },
  });
  assert.equal(out.name, 'From Context');
  assert.equal(out.school, 'Ohio State'); // collapsed internal whitespace
  assert.equal(out.classYear, 2026);
});

test('normalizeRookieIdentity supplies placeholders when data is missing', () => {
  const out = normalizeRookieIdentity({ alphaPlayer: {} });
  assert.equal(out.name, 'Unknown Rookie');
  assert.equal(out.position, null);
  assert.equal(out.positionLabel, 'Position unavailable');
  assert.equal(out.roleLabel, 'Role still forming');
  assert.equal(out.schoolDisplay, 'School unavailable in current artifacts');
  assert.equal(out.classYear, null);
});

test('normalizeRookieIdentity passes through unknown positions uppercased', () => {
  const out = normalizeRookieIdentity({ alphaPlayer: { position: 'edge' } });
  assert.equal(out.position, 'EDGE');
  assert.equal(out.positionLabel, 'EDGE'); // no label mapping, echoes the code
  assert.equal(out.roleLabel, 'Role still forming');
});

test('normalizeRookieIdentity ignores non-finite class years', () => {
  const out = normalizeRookieIdentity({ alphaPlayer: { context: { class_year: 'soon' } } });
  assert.equal(out.classYear, null);
});
