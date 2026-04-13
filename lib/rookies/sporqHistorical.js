/**
 * sporqHistorical.js
 *
 * Provides lookup and comparison utilities over the historical SPORQ dataset
 * (RB / WR / TE, 2475 players, sourced from FantasyPoints.com).
 *
 * Data is lazy-loaded once on first use.
 */

let _cache = null;

async function loadData() {
  if (_cache) return _cache;
  const res = await fetch('/data/historical/sporq_historical.json');
  if (!res.ok) throw new Error(`Failed to load SPORQ historical data: ${res.status}`);
  _cache = await res.json();
  return _cache;
}

/**
 * Returns the SPORQ percentile (0–100) for a score within a position group.
 * Uses linear interpolation over the scored population.
 *
 * @param {'RB'|'WR'|'TE'} position
 * @param {number} sporqScore
 * @returns {Promise<number|null>}
 */
export async function getSporqPercentile(position, sporqScore) {
  if (sporqScore == null) return null;
  const data = await loadData();
  const scored = (data.by_position[position] ?? [])
    .filter((p) => p.sporq != null)
    .sort((a, b) => a.sporq - b.sporq);
  if (scored.length === 0) return null;

  let lo = 0;
  let hi = scored.length - 1;
  // Binary search for insertion point
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (scored[mid].sporq < sporqScore) lo = mid + 1;
    else hi = mid;
  }
  return Math.round((lo / (scored.length - 1)) * 100 * 10) / 10;
}

/**
 * Finds players with the most similar SPORQ profiles within a position.
 * Similarity is scored by weighted Euclidean distance over available metrics.
 *
 * @param {'RB'|'WR'|'TE'} position
 * @param {{ sporq?: number, forty?: number, vertical?: number, broad?: number, speed_score?: number }} metrics
 * @param {number} [topN=5]
 * @returns {Promise<Array<{name:string, pos:string, school:string, year:number|null, sporq:number|null, sporq_percentile:number|null, similarity:number}>>}
 */
export async function findSimilarAthletes(position, metrics, topN = 5) {
  const data = await loadData();
  const pool = (data.by_position[position] ?? []).filter((p) => p.sporq != null);

  const WEIGHTS = {
    sporq: 3.0,
    speed_score: 2.0,
    forty: 1.5,
    vertical: 1.0,
    broad: 1.0,
  };

  const scores = pool.map((p) => {
    let totalWeight = 0;
    let distSq = 0;

    for (const [key, weight] of Object.entries(WEIGHTS)) {
      const refVal = metrics[key];
      const pVal = p[key];
      if (refVal == null || pVal == null) continue;

      // Normalise: SPORQ 0–100, forty ~4.2–5.2 (×20 to get ~0–20 scale), others 0–140
      let scale;
      if (key === 'sporq') scale = 100;
      else if (key === 'forty') scale = 1;   // already similar range
      else if (key === 'speed_score') scale = 100;
      else scale = 50; // vertical, broad

      const diff = (refVal - pVal) / scale;
      distSq += weight * diff * diff;
      totalWeight += weight;
    }

    if (totalWeight === 0) return null;
    const similarity = Math.round((1 - Math.sqrt(distSq / totalWeight)) * 100);
    return { p, similarity };
  }).filter(Boolean);

  scores.sort((a, b) => b.similarity - a.similarity);

  return scores.slice(0, topN).map(({ p, similarity }) => ({
    name: p.name,
    pos: p.pos,
    school: p.school,
    year: p.year,
    round: p.round,
    sporq: p.sporq,
    sporq_percentile: p.sporq_percentile,
    similarity,
  }));
}

/**
 * Looks up a player by name and position (case-insensitive fuzzy match).
 *
 * @param {string} name
 * @param {'RB'|'WR'|'TE'} [position]
 * @returns {Promise<object|null>}
 */
export async function lookupPlayer(name, position) {
  const data = await loadData();
  const pool = position ? (data.by_position[position] ?? []) : data.players;
  const needle = name.toLowerCase().trim();

  // Exact match first
  const exact = pool.find((p) => p.name.toLowerCase() === needle);
  if (exact) return exact;

  // Partial match
  return pool.find((p) => p.name.toLowerCase().includes(needle)) ?? null;
}

/**
 * Returns distribution stats for a position (min, max, mean, p25, p50, p75).
 *
 * @param {'RB'|'WR'|'TE'} position
 * @returns {Promise<{count:number, min:number, max:number, mean:number, p25:number, p50:number, p75:number}>}
 */
export async function getSporqDistribution(position) {
  const data = await loadData();
  const scored = (data.by_position[position] ?? [])
    .filter((p) => p.sporq != null)
    .map((p) => p.sporq)
    .sort((a, b) => a - b);

  if (scored.length === 0) return null;

  const at = (pct) => scored[Math.round(pct * (scored.length - 1))];
  const mean = scored.reduce((s, v) => s + v, 0) / scored.length;

  return {
    count: scored.length,
    min: scored[0],
    max: scored[scored.length - 1],
    mean: Math.round(mean * 10) / 10,
    p25: at(0.25),
    p50: at(0.5),
    p75: at(0.75),
  };
}
