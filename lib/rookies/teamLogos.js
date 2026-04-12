/**
 * ESPN CDN team logo URL helpers.
 *
 * College: https://a.espncdn.com/i/teamlogos/ncaa/500/{school_id}.png
 * NFL:     https://a.espncdn.com/i/teamlogos/nfl/500/{abbrev}.png
 *
 * Graceful: returns null when the school or team is unknown — callers must
 * handle null and fall back to hiding the <img> element.
 */

/** @type {Record<string, string>} school name → ESPN NCAA school ID */
const NCAA_IDS = {
  Alabama: '333',
  Arizona: '12',
  'Arizona State': '9',
  Arkansas: '8',
  Auburn: '2',
  Baylor: '239',
  'Boise State': '68',
  'Boston College': '103',
  'Bowling Green': '189',
  BYU: '252',
  California: '25',
  Cincinnati: '2132',
  Clemson: '228',
  Colorado: '38',
  Duke: '150',
  Florida: '57',
  'Florida State': '52',
  Georgia: '61',
  'Georgia Tech': '59',
  Houston: '248',
  Illinois: '356',
  Indiana: '84',
  Iowa: '2294',
  'Iowa State': '66',
  Kansas: '2305',
  'Kansas State': '2306',
  Kentucky: '96',
  Louisville: '97',
  LSU: '99',
  Maryland: '120',
  Miami: '2390',
  'Miami (FL)': '2390',
  Michigan: '130',
  'Michigan State': '127',
  Minnesota: '135',
  Mississippi: '145',
  'Ole Miss': '145',
  'Mississippi State': '344',
  Missouri: '142',
  Nebraska: '158',
  'North Carolina': '153',
  'NC State': '152',
  'North Carolina State': '152',
  Northwestern: '77',
  'Notre Dame': '87',
  'Ohio State': '194',
  Oklahoma: '201',
  'Oklahoma State': '197',
  Oregon: '2483',
  'Oregon State': '204',
  'Penn State': '213',
  Pittsburgh: '221',
  Purdue: '2509',
  Rutgers: '164',
  'South Carolina': '2579',
  Stanford: '24',
  Syracuse: '183',
  TCU: '2628',
  Tennessee: '2633',
  Texas: '251',
  'Texas A&M': '245',
  'Texas Tech': '2641',
  Toledo: '2649',
  Tulane: '2655',
  UCF: '2116',
  UCLA: '26',
  USC: '30',
  Utah: '254',
  Vanderbilt: '238',
  Virginia: '258',
  'Virginia Tech': '259',
  'Wake Forest': '154',
  Washington: '264',
  'Washington State': '265',
  'West Virginia': '277',
  Wisconsin: '275',
};

/** @type {Record<string, string>} full NFL team name → ESPN abbreviation */
const NFL_ABBREVS = {
  'Arizona Cardinals': 'ari',
  'Atlanta Falcons': 'atl',
  'Baltimore Ravens': 'bal',
  'Buffalo Bills': 'buf',
  'Carolina Panthers': 'car',
  'Chicago Bears': 'chi',
  'Cincinnati Bengals': 'cin',
  'Cleveland Browns': 'cle',
  'Dallas Cowboys': 'dal',
  'Denver Broncos': 'den',
  'Detroit Lions': 'det',
  'Green Bay Packers': 'gb',
  'Houston Texans': 'hou',
  'Indianapolis Colts': 'ind',
  'Jacksonville Jaguars': 'jax',
  'Kansas City Chiefs': 'kc',
  'Las Vegas Raiders': 'lv',
  'Los Angeles Chargers': 'lac',
  'Los Angeles Rams': 'lar',
  'Miami Dolphins': 'mia',
  'Minnesota Vikings': 'min',
  'New England Patriots': 'ne',
  'New Orleans Saints': 'no',
  'New York Giants': 'nyg',
  'New York Jets': 'nyj',
  'Philadelphia Eagles': 'phi',
  'Pittsburgh Steelers': 'pit',
  'San Francisco 49ers': 'sf',
  'Seattle Seahawks': 'sea',
  'Tampa Bay Buccaneers': 'tb',
  'Tennessee Titans': 'ten',
  'Washington Commanders': 'was',
};

/**
 * Returns the ESPN CDN URL for a college team logo, or null if unknown.
 * @param {string|null} school
 * @returns {string|null}
 */
export function getCollegeLogoUrl(school) {
  if (!school) return null;
  const id = NCAA_IDS[school.trim()];
  return id ? `https://a.espncdn.com/i/teamlogos/ncaa/500/${id}.png` : null;
}

/**
 * Returns the ESPN CDN URL for an NFL team logo, or null if unknown.
 * @param {string|null} nflTeam  Full team name, e.g. "Washington Commanders"
 * @returns {string|null}
 */
export function getNflTeamLogoUrl(nflTeam) {
  if (!nflTeam) return null;
  const abbrev = NFL_ABBREVS[nflTeam.trim()];
  return abbrev ? `https://a.espncdn.com/i/teamlogos/nfl/500/${abbrev}.png` : null;
}
