export function groupRookiesByTier(rows) {
  const grouped = new Map();

  rows.forEach((row) => {
    const key = row.tier.key;
    if (!grouped.has(key)) {
      grouped.set(key, {
        key,
        label: row.tier.label,
        bucketOrder: row.tier.bucketOrder,
        rows: [],
      });
    }
    grouped.get(key).rows.push(row);
  });

  return [...grouped.values()].sort((a, b) => a.bucketOrder - b.bucketOrder);
}
