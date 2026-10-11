#!/usr/bin/env python3
"""Build an offline, unpromoted 2024 coverage candidate; never run Alpha defaults."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/historical/reconstruction_2024'
EXPECTED = {'QB': 11, 'RB': 20, 'WR': 35, 'TE': 12}
MHJ = 'wr-marvin-harrison-jr'
BASE_COMMIT = 'e78df9df32adb6568ccfbe8ff2b7210d9d99e8a6'
PRE_DRAFT_CUTOFF = '2024-04-24T23:59:59Z'
CANDIDATE_STATUS = 'unpromoted_candidate_pending_independent_review'
DRAFT_HANDOFF = {
    'status': 'unavailable',
    'note': ('Data has no inspected canonical 2024 draft-results handoff. '
             'Census facts are a separate candidate, not a replacement runtime file.'),
}
REPO_FILE_BINDING_PATHS = frozenset({
    'scripts/compute_rookie_alpha.py',
    'scripts/compute_production_scores.py',
    'data/raw/2024_real_seed_pool.json',
    'data/processed/2024_player_stats.json',
    'data/processed/2024_college_production.json',
    'data/processed/2024_draft_capital_proxy.json',
    'data/processed/2024_prospect_context.json',
    'data/raw/2024_combine_results.json',
    'exports/promoted/rookie-alpha/2024_rookie_alpha_predraft_v0.json',
    'data/historical/sporq_raw_wr.tsv',
})
MHJ_DRAFT_IDENTITY = {
    'player_name': 'Marvin Harrison Jr.',
    'position': 'WR',
    'school': 'Ohio State',
}
COHORT_FIELDS = ('definition', 'total', 'counts', 'udfa_rule')
DRAFT_RECORD_FIELDS = ('player_id', 'player_name', 'position', 'school', 'class_year',
                       'overall_pick', 'draft_round', 'draft_team', 'draft_team_name',
                       'gsis_id', 'pfr_id', 'source_refs', 'primary_locator',
                       'id_status', 'identity_note')
DRAFT_RECORD_BINDING_SHA256 = '8d6bda78fdffa9f4eb867c6b394fc36d2e08cfbc8bd2ffc7724c161e68a21547'
DRAFT_STRING_FIELDS = ('player_id', 'player_name', 'position', 'school', 'draft_team',
                       'draft_team_name', 'id_status', 'identity_note')
DRAFT_TEAM_NAMES = {
    'ARI': 'ARIZONA CARDINALS', 'ATL': 'ATLANTA FALCONS',
    'BAL': 'BALTIMORE RAVENS', 'BUF': 'BUFFALO BILLS',
    'CAR': 'CAROLINA PANTHERS', 'CHI': 'CHICAGO BEARS',
    'CIN': 'CINCINNATI BENGALS', 'CLE': 'CLEVELAND BROWNS',
    'DAL': 'DALLAS COWBOYS', 'DEN': 'DENVER BRONCOS',
    'DET': 'DETROIT LIONS', 'GB': 'GREEN BAY PACKERS',
    'HOU': 'HOUSTON TEXANS', 'IND': 'INDIANAPOLIS COLTS',
    'JAX': 'JACKSONVILLE JAGUARS', 'KC': 'KANSAS CITY CHIEFS',
    'LA': 'LOS ANGELES RAMS', 'LAC': 'LOS ANGELES CHARGERS',
    'LV': 'LAS VEGAS RAIDERS', 'MIA': 'MIAMI DOLPHINS',
    'MIN': 'MINNESOTA VIKINGS', 'NE': 'NEW ENGLAND PATRIOTS',
    'NO': 'NEW ORLEANS SAINTS', 'NYG': 'NEW YORK GIANTS',
    'NYJ': 'NEW YORK JETS', 'PHI': 'PHILADELPHIA EAGLES',
    'PIT': 'PITTSBURGH STEELERS', 'SEA': 'SEATTLE SEAHAWKS',
    'SF': 'SAN FRANCISCO 49ERS', 'TB': 'TAMPA BAY BUCCANEERS',
    'TEN': 'TENNESSEE TITANS', 'WAS': 'WASHINGTON COMMANDERS',
}
DRAFT_CORE_SOURCE_BINDINGS = {
    'nfl-draft-factbook': {
        'url': 'https://static.www.nfl.com/image/upload/league/apps/league-site/media-guides/2024/2024_Record_and_Fact_Book_incl_Supplemental.pdf',
        'sha256': 'ed58911ff56141c9bb7c31f7c5b46f59ef5fe70790f35f6a7c566b36c1ff7c88',
        'rights_scope': 'Factual draft/identity fields only; no copied prose or analyst data.',
    },
    'nflverse-draft-identity': {
        'url': 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/draft_picks.csv',
        'sha256': '6ef8dd337de2f4215bd9018922e5527b5832c5ec4dbd12e43d20663f2949f18d',
        'rights_scope': 'Factual draft/identity fields only; no copied prose or analyst data.',
    },
}
DRAFT_CORE_SOURCES = set(DRAFT_CORE_SOURCE_BINDINGS)
DRAFT_SUPPLEMENTAL_SOURCE_SUBJECT = {
    'college-mhj': MHJ,
    'draft-penix-name': 'qb-michael-penix-jr',
    'college-thomas': 'wr-brian-thomas-jr',
    'draft-tracy-name': 'rb-tyrone-tracy-jr',
    'draft-milton-name': 'qb-joe-milton-iii',
}
DRAFT_SUPPLEMENTAL_SOURCE_BINDINGS = {
    'draft-penix-name': {
        'url': 'https://www.atlantafalcons.com/news/michael-penix-jr-quarterback-washington-huskies-no-8-pick-overall-2024-nfl-draft',
        'retrieval_method': 'search_service_primary_record',
        'rights_scope': 'Factual name and draft identity only; no analyst commentary.',
    },
    'draft-tracy-name': {
        'url': 'https://www.giants.com/news/tyrone-tracy-jr-running-back-purdue-nfl-draft-2024',
        'retrieval_method': 'search_service_primary_record',
        'rights_scope': 'Factual name and draft identity only; no analyst commentary.',
    },
    'draft-milton-name': {
        'url': 'https://www.nfl.com/videos/patriots-select-joe-milton-iii-with-no-193-pick-in-2024-draft',
        'retrieval_method': 'search_service_primary_record',
        'rights_scope': 'Factual name and draft identity only; no analyst commentary.',
    },
}
SOURCE_REQUIRED = {'source_id', 'url', 'qualification', 'rights_scope'}
SOURCE_SCHEMAS = (
    frozenset(SOURCE_REQUIRED | {'retrieved_at', 'sha256', 'status', 'bytes', 'snapshot_note'}),
    frozenset(SOURCE_REQUIRED | {'retrieved_on', 'retrieval_method'}),
    frozenset(SOURCE_REQUIRED | {'retrieved_on', 'sha256', 'snapshot_note'}),
)
SOURCE_RECEIPT_BINDING_SHA256 = '5405d820cb854df366a98bda0caed6d7eb0162f0595efe19ca821800c82e38d0'
IDENTITY_RESOLUTION_FIELDS = ('pick', 'primary_name', 'secondary_name',
                              'candidate_display_name', 'primary_position',
                              'secondary_position', 'primary_printed_round',
                              'adopted_round', 'resolution', 'name_source_refs')
EXPECTED_IDENTITY_RESOLUTION_PICKS = {4, 8, 23, 37, 121, 132, 166, 193}
IDENTITY_RESOLUTION_BINDING_SHA256 = 'cd2677cf5c820480962cdfa8df899b09cc44235132cf019415144f00a71d0f22'
COLLEGE_SOURCE_SUBJECT = {
    'college-allen': 'rb-braelon-allen',
    'college-allen-pdf': 'rb-braelon-allen',
    'college-benson': 'rb-trey-benson',
    'college-benson-pdf': 'rb-trey-benson',
    'college-bowers': 'te-brock-bowers',
    'college-brooks': 'rb-jonathon-brooks',
    'college-caleb': 'qb-caleb-williams',
    'college-corum': 'rb-blake-corum',
    'college-daniels': 'qb-jayden-daniels',
    'college-lloyd': 'rb-marshawn-lloyd',
    'college-maye': 'qb-drake-maye',
    'college-mcconkey': 'wr-ladd-mcconkey',
    'college-mhj': MHJ,
    'college-mitchell': 'wr-adonai-mitchell',
    'college-nabers': 'wr-malik-nabers',
    'college-odunze': 'wr-rome-odunze',
    'college-thomas': 'wr-brian-thomas-jr',
    'college-worthy': 'wr-xavier-worthy',
    'nfl-mhj-bio': MHJ,
}
COLLEGE_SOURCE_BINDING_SHA256 = 'fdd0eb8134d5c73961f369b06f26841368d337c85f4b82ec52274d14b77e1c4e'
COLLEGE_OBSERVATION_BINDING_SHA256 = '4bf0316d1d1333bdbebf2a3e0cdc37e79022353caaf18c72ce38c737373d08cc'
SOURCE_CONFLICT_FIELDS = ('player_id', 'field', 'season', 'observations',
                          'candidate_value', 'resolution_status', 'note')
EXPECTED_BENSON_CONFLICT_OBSERVATIONS = [
    {'source_ref': 'college-benson', 'value': 906},
    {'source_ref': 'college-benson-pdf',
     'locator': 'PDF page 28, player career table', 'value': 905},
]
FORBIDDEN_COLLEGE_KEYS = {'actual_overall_pick', 'actual_draft_round', 'overall_pick', 'draft_round', 'draft_team', 'draft_team_name', 'nfl_outcomes', 'nfl_stats', 'fantasy_points'}
COLLEGE_OBSERVATION_KEYS = {'player_id', 'season', 'stats', 'source_refs', 'source_locators', 'evidence_lane', 'status'}
COLLEGE_OBSERVATION_REQUIRED = COLLEGE_OBSERVATION_KEYS - {'source_locators'}
MHJ_SEASON_KEYS = {'season', 'games', 'receptions', 'receiving_yards', 'receiving_tds', 'source_refs', 'evidence_lane', 'status'}
COLLEGE_STAT_KEYS = {'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions',
                     'rush_attempts', 'rush_yards', 'rush_tds',
                     'receptions', 'receiving_yards', 'receiving_tds'}
STAT_FAMILIES = (
    ({'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions'},
     {'completions', 'attempts', 'passing_yards'}, 'attempts'),
    ({'rush_attempts', 'rush_yards', 'rush_tds'},
     {'rush_attempts', 'rush_yards'}, 'rush_attempts'),
    ({'receptions', 'receiving_yards', 'receiving_tds'},
     {'receptions', 'receiving_yards'}, 'receptions'),
)
COLLEGE_STATUS = 'public_factual_candidate_pending_independent_review'
NORMALIZATION_FIELDS = ('status', 'required', 'observed_access', 'effect')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source_refs(refs: object, sources: set[str], label: str) -> None:
    if (type(refs) is not list or not refs
            or any(type(ref) is not str or not ref for ref in refs)
            or len(set(refs)) != len(refs) or not set(refs).issubset(sources)):
        raise ValueError('Unresolved ' + label + ' source')


def validate_facts(facts: dict, root: Path = ROOT) -> None:
    if (facts.get('class_year') != 2024
            or facts.get('status') != CANDIDATE_STATUS
            or facts.get('promotable') is not False):
        raise ValueError('Wrong class or promotion state')
    if facts.get('base_commit') != BASE_COMMIT:
        raise ValueError('Invalid base commit')
    if facts.get('pre_draft_cutoff') != PRE_DRAFT_CUTOFF:
        raise ValueError('Invalid pre-draft cutoff')
    handoff = facts.get('draft_handoff')
    if type(handoff) is not dict or handoff != DRAFT_HANDOFF:
        raise ValueError('Invalid unavailable draft handoff')
    normalization = facts.get('normalization_population')
    if (type(normalization) is not dict
            or tuple(normalization) != NORMALIZATION_FIELDS
            or normalization.get('status') != 'unavailable'
            or any(type(normalization.get(field)) is not str or not normalization[field]
                   for field in NORMALIZATION_FIELDS)):
        raise ValueError('Invalid normalization population')
    rows = facts['draft_day_records']
    if any(set(row) != set(DRAFT_RECORD_FIELDS) for row in rows):
        raise ValueError('Unexpected or missing draft record field')
    if len(rows) != 78 or Counter(x['position'] for x in rows) != EXPECTED:
        raise ValueError('Incomplete or misclassified 2024 skill census')
    cohort = facts.get('cohort')
    if (type(cohort) is not dict or set(cohort) != set(COHORT_FIELDS)
            or type(cohort['definition']) is not str or not cohort['definition']
            or type(cohort['total']) is not int or cohort['total'] != len(rows)
            or cohort['counts'] != EXPECTED
            or type(cohort['udfa_rule']) is not str or not cohort['udfa_rule']):
        raise ValueError('Invalid cohort metadata')
    for field in ['player_id', 'overall_pick']:
        if len({x[field] for x in rows}) != len(rows):
            raise ValueError('Duplicate census ' + field)
    source_ledger = facts['source_ledger']
    for source in source_ledger:
        if (frozenset(source) not in SOURCE_SCHEMAS
                or any(type(source[field]) is not str or not source[field]
                       for field in SOURCE_REQUIRED)
                or not source['url'].startswith('https://')
                or source['qualification'] != COLLEGE_STATUS
                or ('retrieved_at' in source) == ('retrieved_on' in source)):
            raise ValueError('Invalid source ledger entry')
        if 'retrieved_at' in source:
            if (not {'sha256', 'status', 'bytes', 'snapshot_note'}.issubset(source)
                    or source['status'] != 'retrieved'
                    or type(source['bytes']) is not int or source['bytes'] < 1):
                raise ValueError('Invalid source retrieval receipt')
        elif not ('retrieval_method' in source or {'sha256', 'snapshot_note'}.issubset(source)):
            raise ValueError('Invalid source retrieval receipt')
        for field in ['retrieved_at', 'retrieved_on', 'retrieval_method', 'snapshot_note']:
            if field in source and (type(source[field]) is not str or not source[field]):
                raise ValueError('Invalid source retrieval metadata')
        if 'sha256' in source and (type(source['sha256']) is not str
                                   or len(source['sha256']) != 64
                                   or any(char not in '0123456789abcdef' for char in source['sha256'])):
            raise ValueError('Invalid source digest')
    sources_by_id = {x['source_id']: x for x in source_ledger}
    sources = set(sources_by_id)
    if len(sources) != len(source_ledger):
        raise ValueError('Duplicate source identity')
    for source_id, expected in DRAFT_CORE_SOURCE_BINDINGS.items():
        source = sources_by_id.get(source_id)
        if (source is None
                or any(source.get(field) != value for field, value in expected.items())):
            raise ValueError('Invalid core draft source binding')
    for source_id, expected in DRAFT_SUPPLEMENTAL_SOURCE_BINDINGS.items():
        source = sources_by_id.get(source_id)
        if (source is None
                or any(source.get(field) != value for field, value in expected.items())):
            raise ValueError('Invalid supplemental draft source binding')
    college_source_bindings = [sources_by_id.get(source_id, {})
                               for source_id in sorted(COLLEGE_SOURCE_SUBJECT)]
    binding_digest = hashlib.sha256(json.dumps(
        college_source_bindings, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if binding_digest != COLLEGE_SOURCE_BINDING_SHA256:
        raise ValueError('Invalid college source binding')
    ids = {x['player_id'] for x in rows}
    draft_by_pick = {row['overall_pick']: row for row in rows}
    identity_resolutions = facts['identity_resolutions']
    seen_resolution_picks = set()
    for resolution in identity_resolutions:
        if set(resolution) != set(IDENTITY_RESOLUTION_FIELDS):
            raise ValueError('Unexpected or missing identity resolution field')
        if type(resolution['pick']) is not int:
            raise ValueError('Invalid identity resolution linkage')
        if resolution['pick'] in seen_resolution_picks:
            raise ValueError('Duplicate identity resolution pick')
        seen_resolution_picks.add(resolution['pick'])
        draft = draft_by_pick.get(resolution['pick'])
        if (draft is None
                or resolution['candidate_display_name'] != draft['player_name']
                or resolution['primary_position'] != draft['position']
                or type(resolution['adopted_round']) is not int
                or resolution['adopted_round'] != draft['draft_round']
                or type(resolution['primary_printed_round']) is not int
                or not 1 <= resolution['primary_printed_round'] <= 7
                or any(type(resolution[field]) is not str or not resolution[field]
                       for field in ['primary_name', 'secondary_name', 'candidate_display_name',
                                     'primary_position', 'resolution'])
                or (resolution['secondary_position'] is not None
                    and resolution['secondary_position'] not in EXPECTED)):
            raise ValueError('Invalid identity resolution linkage')
        validate_source_refs(resolution['name_source_refs'], sources, 'identity')
        if set(resolution['name_source_refs']) != set(draft['source_refs']):
            raise ValueError('Identity resolution sources do not match draft row')
    if seen_resolution_picks != EXPECTED_IDENTITY_RESOLUTION_PICKS:
        raise ValueError('Incomplete identity resolution set')
    resolution_binding = hashlib.sha256(json.dumps([
        {key: row[key] for key in IDENTITY_RESOLUTION_FIELDS}
        for row in sorted(identity_resolutions, key=lambda row: row['pick'])
    ], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if resolution_binding != IDENTITY_RESOLUTION_BINDING_SHA256:
        raise ValueError('Invalid identity resolution evidence binding')
    observations = facts['college_observations']
    if len({x['player_id'] for x in observations}) != len(observations):
        raise ValueError('Duplicate final-season college observation')
    lanes = [(observations, COLLEGE_OBSERVATION_KEYS, COLLEGE_OBSERVATION_REQUIRED, {2023}),
             (facts['mhj_college_seasons'], MHJ_SEASON_KEYS, MHJ_SEASON_KEYS, {2021, 2022, 2023})]
    for lane, allowed, required_fields, allowed_seasons in lanes:
        for obs in lane:
            if FORBIDDEN_COLLEGE_KEYS.intersection(obs) or FORBIDDEN_COLLEGE_KEYS.intersection(obs.get('stats', {})):
                raise ValueError('Draft/NFL evidence leaked into college observations')
            if set(obs) - allowed or required_fields - set(obs):
                raise ValueError('Unexpected or missing college observation field')
            if 'stats' in obs and (type(obs['stats']) is not dict or set(obs['stats']) - COLLEGE_STAT_KEYS):
                raise ValueError('Unexpected college statistic field')
            if type(obs['season']) is not int or obs['season'] not in allowed_seasons or obs['evidence_lane'] != 'college_production':
                raise ValueError('Ineligible college season/lane')
            if obs['status'] != COLLEGE_STATUS:
                raise ValueError('Unexpected college observation status')
            validate_source_refs(obs['source_refs'], sources, 'college')
            subject = obs.get('player_id', MHJ)
            if any(COLLEGE_SOURCE_SUBJECT.get(ref) != subject for ref in obs['source_refs']):
                raise ValueError('College source does not match observed player')
            if 'player_id' in obs and (type(obs['player_id']) is not str or obs['player_id'] not in ids):
                raise ValueError('Unresolved college identity')
            if 'source_locators' in obs:
                locators = obs['source_locators']
                if (type(locators) is not dict or not locators
                        or any(type(key) is not str or key not in obs['source_refs']
                               or type(value) is not str or not value
                               for key, value in locators.items())):
                    raise ValueError('Invalid college source locator')
            for key, value in obs.get('stats', {}).items():
                if type(value) is not int or value < 0:
                    raise ValueError('Non-factual count operand: ' + key)
            stats = obs.get('stats')
            if stats is not None:
                if not stats:
                    raise ValueError('Empty college statistic group')
                for family, required_operands, denominator in STAT_FAMILIES:
                    if family.intersection(stats) and (not required_operands.issubset(stats) or stats[denominator] == 0):
                        raise ValueError('Incomplete or zero-denominator statistic group: ' + denominator)
                if 'completions' in stats and stats['completions'] > stats['attempts']:
                    raise ValueError('Completions exceed attempts')
            if 'games' in obs:
                for key in ['games', 'receptions', 'receiving_yards', 'receiving_tds']:
                    if type(obs[key]) is not int or obs[key] < 0:
                        raise ValueError('Non-factual count operand: ' + key)
                if obs['games'] == 0:
                    raise ValueError('Zero-game college season')
    if Counter(row['season'] for row in facts['mhj_college_seasons']) != Counter({2021: 1, 2022: 1, 2023: 1}):
        raise ValueError('Incomplete or duplicate MHJ college seasons')
    mhj_final = next((obs for obs in observations if obs['player_id'] == MHJ), None)
    mhj_2023 = next(row for row in facts['mhj_college_seasons'] if row['season'] == 2023)
    receiving_fields = ('receptions', 'receiving_yards', 'receiving_tds')
    if (mhj_final is None
            or any(mhj_final['stats'].get(field) != mhj_2023[field]
                   for field in receiving_fields)):
        raise ValueError('MHJ final-season observations do not reconcile')
    source_conflicts = facts.get('source_conflicts')
    if type(source_conflicts) is not list or len(source_conflicts) != 1:
        raise ValueError('Missing retained source conflict')
    conflict = source_conflicts[0]
    benson = next((obs for obs in observations if obs['player_id'] == 'rb-trey-benson'), None)
    if (type(conflict) is not dict or set(conflict) != set(SOURCE_CONFLICT_FIELDS)
            or conflict['player_id'] != 'rb-trey-benson'
            or conflict['field'] != 'rush_yards'
            or conflict['season'] != 2023
            or conflict['observations'] != EXPECTED_BENSON_CONFLICT_OBSERVATIONS
            or benson is None
            or conflict['candidate_value'] != benson.get('stats', {}).get('rush_yards')
            or conflict['resolution_status'] != 'provisional_current_roster_value_pending_review'
            or type(conflict['note']) is not str or not conflict['note']):
        raise ValueError('Invalid retained source conflict')
    legacy_seed_ids = {row['player_id'] for row in json.loads(
        (root / 'data/raw/2024_real_seed_pool.json').read_text())}
    if not legacy_seed_ids.issubset({obs['player_id'] for obs in observations}):
        raise ValueError('Missing final-season observation for legacy seed')
    college_observation_binding = hashlib.sha256(json.dumps({
        'college_observations': sorted(observations, key=lambda row: row['player_id']),
        'mhj_college_seasons': sorted(facts['mhj_college_seasons'],
                                      key=lambda row: row['season']),
    }, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if college_observation_binding != COLLEGE_OBSERVATION_BINDING_SHA256:
        raise ValueError('Invalid college observation evidence binding')
    for row in rows:
        if (any(type(row[field]) is not str or not row[field] for field in DRAFT_STRING_FIELDS)
                or row['position'] not in EXPECTED
                or type(row['class_year']) is not int or row['class_year'] != 2024
                or type(row['draft_round']) is not int or not 1 <= row['draft_round'] <= 7
                or DRAFT_TEAM_NAMES.get(row['draft_team']) != row['draft_team_name']
                or any(value is not None and (type(value) is not str or not value)
                       for value in [row['gsis_id'], row['pfr_id']])
                or row['id_status'] not in {'existing_rookies_id', 'candidate_local_id'}):
            raise ValueError('Invalid draft record value')
        locator = row['primary_locator']
        if (type(locator) is not dict or set(locator) != {'pdf_page', 'column'}
                or type(locator['pdf_page']) is not int or locator['pdf_page'] < 1
                or locator['column'] not in {'left', 'right'}):
            raise ValueError('Invalid draft source locator')
        try:
            validate_source_refs(row['source_refs'], sources, 'draft')
        except ValueError:
            raise ValueError('Unresolved draft fact') from None
        draft_refs = set(row['source_refs'])
        if (not DRAFT_CORE_SOURCES.issubset(draft_refs)
                or any(DRAFT_SUPPLEMENTAL_SOURCE_SUBJECT.get(ref) != row['player_id']
                       for ref in draft_refs - DRAFT_CORE_SOURCES)):
            raise ValueError('Draft source does not match evidence role')
        if type(row['overall_pick']) is not int or not 1 <= row['overall_pick'] <= 257:
            raise ValueError('Unresolved draft fact')
    mhj_row = next(row for row in rows if row['player_id'] == MHJ)
    if any(mhj_row[field] != value for field, value in MHJ_DRAFT_IDENTITY.items()):
        raise ValueError('Invalid MHJ draft identity')
    draft_record_binding = hashlib.sha256(json.dumps([
        {key: row[key] for key in DRAFT_RECORD_FIELDS}
        for row in sorted(rows, key=lambda row: row['player_id'])
    ], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if draft_record_binding != DRAFT_RECORD_BINDING_SHA256:
        raise ValueError('Invalid draft record evidence binding')
    # Bind complete receipts across all source roles, including retrieval metadata.
    source_receipt_binding = hashlib.sha256(json.dumps(
        sorted(source_ledger, key=lambda row: row['source_id']),
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if source_receipt_binding != SOURCE_RECEIPT_BINDING_SHA256:
        raise ValueError('Invalid retained source receipt binding')
    bindings = facts.get('repo_file_bindings')
    if type(bindings) is not dict or set(bindings) != REPO_FILE_BINDING_PATHS:
        raise ValueError('Invalid repository binding set')
    for path, expected in bindings.items():
        if sha(root / path) != expected:
            raise ValueError('Pinned repository input changed: ' + path)


def derived_stats(stats: dict) -> dict:
    result = dict(stats)
    if 'attempts' in stats:
        result['completion_pct'] = round(100 * stats['completions'] / stats['attempts'], 1)
        result['yards_per_attempt'] = round(stats['passing_yards'] / stats['attempts'], 1)
    if 'rush_attempts' in stats:
        result['yards_per_carry'] = round(stats['rush_yards'] / stats['rush_attempts'], 1)
    if 'receptions' in stats:
        result['yards_per_reception'] = round(stats['receiving_yards'] / stats['receptions'], 1)
    return result


def build(facts: dict, root: Path = ROOT) -> dict[str, dict | str]:
    validate_facts(facts, root)
    source_bytes = (root / 'data/historical/reconstruction_2024/source_facts_v0.json').read_bytes()
    retained_facts = json.loads(source_bytes)
    if json.dumps(facts, sort_keys=True) != json.dumps(retained_facts, sort_keys=True):
        raise ValueError('Supplied facts do not match retained source ledger')
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    seed_path = 'data/raw/2024_real_seed_pool.json'
    stats_path = 'data/processed/2024_player_stats.json'
    alpha_path = 'exports/promoted/rookie-alpha/2024_rookie_alpha_predraft_v0.json'
    seed = {x['player_id']: x for x in json.loads((root / seed_path).read_text())}
    legacy_stats = {x['player_id']: x for x in json.loads((root / stats_path).read_text())}
    alpha = {x['player_id']: x for x in json.loads((root / alpha_path).read_text())['players']}
    observations = {x['player_id']: x for x in facts['college_observations']}
    observation_indices = {x['player_id']: i for i, x in enumerate(facts['college_observations'])}
    census_ids = {x['player_id'] for x in facts['draft_day_records']}
    if not set(seed).issubset(census_ids) or set(seed) != set(legacy_stats) or set(seed) != set(alpha):
        raise ValueError('Legacy identities do not reconcile to census')
    shared = {'class_year': 2024, 'status': 'unpromoted_candidate_pending_independent_review',
              'promotable': False, 'base_commit': facts['base_commit'],
              'source_facts_sha256': source_hash}
    cohort = {key: facts['cohort'][key] for key in COHORT_FIELDS}
    source_conflicts = [{key: conflict[key] for key in SOURCE_CONFLICT_FIELDS}
                        for conflict in facts['source_conflicts']]
    audit_rows = []
    coverage_rows = []
    for row in facts['draft_day_records']:
        pid = row['player_id']
        obs = observations.get(pid)
        conflicts = []
        if pid in seed:
            verified = derived_stats(obs['stats'])
            old = legacy_stats[pid]['stats']
            for key, value in verified.items():
                if key in old and old[key] != value:
                    conflicts.append({'field': key, 'legacy_value': old[key], 'candidate_value': value})
            audit_rows.append({'player_id': pid, 'legacy_input_paths': [seed_path, stats_path],
                               'legacy_production_score': seed[pid]['production_score_0_100'],
                               'legacy_source_claim': seed[pid]['production_score_source'],
                               'candidate_2023_stats': verified, 'source_refs': obs['source_refs'],
                               'raw_operand_status': 'contradicted' if conflicts else 'selected_raw_operands_reconciled',
                               'differences': conflicts, 'normalized_score_status': 'unqualified_manual_seed',
                               'note': 'Agreement on selected raw operands does not verify normalized scores, testing, context, consensus or expected draft capital.'})
        blockers = ['Full 2023 positional normalization population and retained producer receipt unavailable.',
                    'Pre-draft testing/context/expected-capital operands have not been qualified for a new reconstruction.']
        if not obs:
            blockers.insert(0, 'Public final-season college production has not been acquired for this subject in this bounded pass.')
        if conflicts:
            blockers.insert(0, 'Existing raw production operands conflict with primary school records; candidate correction requires review.')
        if pid == MHJ:
            blockers.append('No timed/jump testing in existing historical row (SPORQ DNQ); DNQ is missingness, not a low score.')
        coverage_rows.append({'player_id': pid, 'player_name': row['player_name'], 'position': row['position'],
                              'identity_profile_status': 'sourced_draft_identity',
                              'prospect_profile_status': 'sourced_college_candidate' if obs else 'identity_only_blocked',
                              'legacy_seed_present': pid in seed, 'legacy_alpha_row_present': pid in alpha,
                              'college_production_status': 'source_backed_candidate_pending_review' if obs else 'not_acquired',
                              'college_source_refs': obs['source_refs'] if obs else [],
                              'college_observation_ref': 'source_facts_v0.json#/college_observations/' + str(observation_indices[pid]) if obs else None,
                              'testing_status': 'existing_historical_DNQ_no_timed_or_jump_operands' if pid == MHJ else 'not_qualified_in_this_pass',
                              'expected_draft_capital_status': 'legacy_manual_input_unqualified' if pid in seed else 'unavailable',
                              'draft_facts_status': 'source_backed_candidate_not_canonical_Data_handoff',
                              'pre_draft_grade': {'value': None, 'status': 'unavailable', 'blockers': blockers},
                              'post_draft_grade': {'value': None, 'status': 'unavailable', 'blockers': ['Pre-draft operands not qualified.', 'Canonical Data 2024 draft-results handoff unavailable; coordinate #242.']},
                              'legacy_alpha_score': alpha[pid]['scores']['rookie_alpha_0_100'] if pid in alpha else None,
                              'legacy_alpha_qualification': 'unqualified_existing_output_preserved' if pid in alpha else 'no_existing_output',
                              'source_refs': row['source_refs']})
    conflicts_total = sum(x['raw_operand_status'] == 'contradicted' for x in audit_rows)
    coverage = {**shared, 'artifact': '2024_coverage_matrix_v0', 'cohort': cohort,
                'summary': {'census_subjects': 78, 'legacy_seed_subjects': 15, 'previously_absent_from_seed': 63,
                            'sourced_college_candidates': len(observations), 'identity_only_blocked': 78 - len(observations),
                            'legacy_rows_with_raw_conflicts': conflicts_total, 'qualified_pre_draft_grades': 0, 'qualified_post_draft_grades': 0},
                'model': {'producer_path': 'scripts/compute_rookie_alpha.py',
                          'producer_sha256': facts['repo_file_bindings']['scripts/compute_rookie_alpha.py'],
                          'existing_export_version': 'rookie-alpha-predraft-v0.5.0',
                          'base_weight_formula': {'athletic': 0.35, 'production': 0.45, 'expected_draft_capital': 0.20},
                          'qualification_note': 'Current producer also has contextual adjustments and neutral defaults. No Alpha pass executed: defaults would manufacture completeness without qualified operands.',
                          'normalization_status': {key: facts['normalization_population'][key]
                                                   for key in NORMALIZATION_FIELDS},
                          'formula_changed': False},
                'players': coverage_rows}
    audit = {**shared, 'artifact': '2024_input_integrity_audit_v0',
             'summary': {'legacy_rows': 15, 'raw_rows_contradicted': conflicts_total, 'legacy_normalized_scores_qualified': 0},
             'rows': audit_rows, 'source_conflicts': source_conflicts}
    mhj_row = next(x for x in facts['draft_day_records'] if x['player_id'] == MHJ)
    mhj_college = [{key: row[key] for key in
                    ['season', 'games', 'receptions', 'receiving_yards', 'receiving_tds',
                     'source_refs', 'evidence_lane', 'status']}
                   for row in facts['mhj_college_seasons']]
    card = {**shared, 'artifact': 'predraft_reconstruction_card_v0', 'reconstruction_mode': 'historical_factual_candidate',
            'pre_draft_cutoff': facts['pre_draft_cutoff'], 'input_separation_policy': 'Shared builder reads draft facts for census and identity; this card excludes actual draft fields and NFL outcomes by validation and explicit field selection. No structural input isolation is claimed.',
            'player_id': MHJ, 'player_name': mhj_row['player_name'], 'position': 'WR',
            'identity': {'school': mhj_row['school'], 'source_refs': ['college-mhj'], 'birth_date': None, 'age_at_entry': None},
            'college_production': mhj_college,
            'prospect_baseline': {'facts': ['2022 and 2023 unanimous All-American', '2023 Biletnikoff Award'], 'source_refs': ['college-mhj']},
            'athletic_testing': {'status': 'unavailable', 'ras_0_100': None, 'sporq_0_100': None,
                                 'note': 'In-repo SPORQ row is DNQ with no timed/jump operands; neither zero nor a measured low score.',
                                 'source_ref': {'path': 'data/historical/sporq_raw_wr.tsv', 'sha256': facts['repo_file_bindings']['data/historical/sporq_raw_wr.tsv'], 'use': 'missingness audit only; no third-party athletic value is ingested'}},
            'market_share_context': {'status': 'unavailable', 'note': 'No retained same-season Ohio State team denominator in this pass.'},
            'route_separation_alignment': {'status': 'unavailable', 'note': 'No qualified public charting or film sample admitted.'},
            'expected_draft_capital': {'status': 'unavailable', 'value': None},
            'grade': next(x['pre_draft_grade'] for x in coverage_rows if x['player_id'] == MHJ),
            'historical_warning': 'Reconstructed now from public historical facts, not an original TIBER forecast or immutable as-known-then receipt. Actual pick/team and all NFL outcomes are excluded.'}
    landing = {**shared, 'artifact': 'landing_context_reconstruction_v0', 'player_id': MHJ,
               'evidence_cutoff': '2024-04-27T23:59:59Z',
               'actual_draft_round': mhj_row['draft_round'],
               'actual_overall_pick': mhj_row['overall_pick'],
               'draft_team': mhj_row['draft_team'], 'source_refs': mhj_row['source_refs'],
               'status_note': 'Public factual candidate only; Data canonical draft handoff still unavailable. No grade or downstream runtime admission.'}
    census_rows = [{key: row[key] for key in DRAFT_RECORD_FIELDS} for row in facts['draft_day_records']]
    identity_rows = [{key: row[key] for key in IDENTITY_RESOLUTION_FIELDS}
                     for row in facts['identity_resolutions']]
    census = {**shared, 'artifact': '2024_skill_class_census_v0', 'cohort': cohort,
              'identity_resolutions': identity_rows, 'players': census_rows}
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=['player_id', 'player_name', 'position', 'school', 'class_year', 'draft_round', 'overall_pick', 'draft_team', 'gsis_id'], lineterminator='\n')
    writer.writeheader()
    writer.writerows({key: x[key] for key in writer.fieldnames} for x in facts['draft_day_records'])
    return {'2024_skill_class_census_v0.json': census, '2024_skill_class_census_v0.csv': buffer.getvalue(),
            'coverage_matrix_v0.json': coverage, 'input_integrity_audit_v0.json': audit,
            'predraft_cards/2024_wr_marvin_harrison_jr_predraft_v0.json': card,
            'landing_context/2024_wr_marvin_harrison_jr_landing_context_v0.json': landing}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify pinned inputs and byte-reproducible checked-in candidates without writing.')
    args = parser.parse_args()
    facts = json.loads((DEST / 'source_facts_v0.json').read_text())
    artifacts = build(facts)
    for filename, value in artifacts.items():
        serialized = value if isinstance(value, str) else json.dumps(value, indent=2) + '\n'
        path = DEST / filename
        if args.check:
            if not path.exists() or path.read_text() != serialized:
                raise ValueError('Candidate differs: ' + filename)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialized)
    print(json.dumps(artifacts['coverage_matrix_v0.json']['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
