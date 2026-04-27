import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeFullRoleOpportunityFound } from '../lib/rookies/workbench/roleOpportunityNormalization.mjs';

test('normalizeFullRoleOpportunityFound prefers full_role_opportunity_found when present', () => {
  const row = {
    full_role_opportunity_found: false,
    role_opportunity_found: true,
  };

  assert.equal(normalizeFullRoleOpportunityFound(row), false);
});

test('normalizeFullRoleOpportunityFound falls back to role_opportunity_found', () => {
  const row = {
    player_name: '__ROLE_ONLY__',
    role_opportunity_found: true,
  };

  assert.equal(normalizeFullRoleOpportunityFound(row), true);
});

test('normalizeFullRoleOpportunityFound returns null when neither field is present', () => {
  assert.equal(normalizeFullRoleOpportunityFound({ player_name: '__NO_ROLE__' }), null);
});
