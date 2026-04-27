export function normalizeFullRoleOpportunityFound(row) {
  if (typeof row?.full_role_opportunity_found === 'boolean') {
    return row.full_role_opportunity_found;
  }

  if (typeof row?.role_opportunity_found === 'boolean') {
    return row.role_opportunity_found;
  }

  return null;
}
