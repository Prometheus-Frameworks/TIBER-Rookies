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
DRAFT_RECORD_FIELDS = ('player_id', 'player_name', 'position', 'school', 'class_year',
                       'overall_pick', 'draft_round', 'draft_team', 'draft_team_name',
                       'gsis_id', 'pfr_id', 'source_refs', 'primary_locator',
                       'id_status', 'identity_note')
DRAFT_STRING_FIELDS = ('player_id', 'player_name', 'position', 'school', 'draft_team',
                       'draft_team_name', 'id_status', 'identity_note')
SOURCE_REQUIRED = {'source_id', 'url', 'qualification', 'rights_scope'}
SOURCE_SCHEMAS = (
    frozenset(SOURCE_REQUIRED | {'retrieved_at', 'sha256', 'status', 'bytes', 'snapshot_note'}),
    frozenset(SOURCE_REQUIRED | {'retrieved_on', 'retrieval_method'}),
    frozenset(SOURCE_REQUIRED | {'retrieved_on', 'sha256', 'snapshot_note'}),
)
IDENTITY_RESOLUTION_FIELDS = ('pick', 'primary_name', 'secondary_name',
                              'candidate_display_name', 'primary_position',
                              'secondary_position', 'primary_printed_round',
                              'adopted_round', 'resolution', 'name_source_refs')
EXPECTED_IDENTITY_RESOLUTION_PICKS = {4, 8, 23, 37, 121, 132, 166, 193}
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source_refs(refs: object, sources: set[str], label: str) -> None:
    if (type(refs) is not list or not refs
            or any(type(ref) is not str or not ref for ref in refs)
            or len(set(refs)) != len(refs) or not set(refs).issubset(sources)):
        raise ValueError('Unresolved ' + label + ' source')


def validate_facts(facts: dict, root: Path = ROOT) -> None:
    if facts.get('class_year') != 2024 or facts.get('promotable') is not False:
        raise ValueError('Wrong class or promotion state')
    rows = facts['draft_day_records']
    if any(set(row) != set(DRAFT_RECORD_FIELDS) for row in rows):
        raise ValueError('Unexpected or missing draft record field')
    if len(rows) != 78 or Counter(x['position'] for x in rows) != EXPECTED:
        raise ValueError('Incomplete or misclassified 2024 skill census')
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
    sources = {x['source_id'] for x in source_ledger}
    if len(sources) != len(source_ledger):
        raise ValueError('Duplicate source identity')
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
    legacy_seed_ids = {row['player_id'] for row in json.loads(
        (root / 'data/raw/2024_real_seed_pool.json').read_text())}
    if not legacy_seed_ids.issubset({obs['player_id'] for obs in observations}):
        raise ValueError('Missing final-season observation for legacy seed')
    for row in rows:
        if (any(type(row[field]) is not str or not row[field] for field in DRAFT_STRING_FIELDS)
                or row['position'] not in EXPECTED
                or type(row['class_year']) is not int or row['class_year'] != 2024
                or type(row['draft_round']) is not int or not 1 <= row['draft_round'] <= 7
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
        if type(row['overall_pick']) is not int or not 1 <= row['overall_pick'] <= 257:
            raise ValueError('Unresolved draft fact')
    for path, expected in facts['repo_file_bindings'].items():
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
    coverage = {**shared, 'artifact': '2024_coverage_matrix_v0', 'cohort': facts['cohort'],
                'summary': {'census_subjects': 78, 'legacy_seed_subjects': 15, 'previously_absent_from_seed': 63,
                            'sourced_college_candidates': len(observations), 'identity_only_blocked': 78 - len(observations),
                            'legacy_rows_with_raw_conflicts': conflicts_total, 'qualified_pre_draft_grades': 0, 'qualified_post_draft_grades': 0},
                'model': {'producer_path': 'scripts/compute_rookie_alpha.py',
                          'producer_sha256': facts['repo_file_bindings']['scripts/compute_rookie_alpha.py'],
                          'existing_export_version': 'rookie-alpha-predraft-v0.5.0',
                          'base_weight_formula': {'athletic': 0.35, 'production': 0.45, 'expected_draft_capital': 0.20},
                          'qualification_note': 'Current producer also has contextual adjustments and neutral defaults. No Alpha pass executed: defaults would manufacture completeness without qualified operands.',
                          'normalization_status': facts['normalization_population'], 'formula_changed': False},
                'players': coverage_rows}
    audit = {**shared, 'artifact': '2024_input_integrity_audit_v0',
             'summary': {'legacy_rows': 15, 'raw_rows_contradicted': conflicts_total, 'legacy_normalized_scores_qualified': 0},
             'rows': audit_rows, 'source_conflicts': facts.get('source_conflicts', [])}
    mhj_row = next(x for x in facts['draft_day_records'] if x['player_id'] == MHJ)
    mhj_college = [{key: row[key] for key in
                    ['season', 'games', 'receptions', 'receiving_yards', 'receiving_tds',
                     'source_refs', 'evidence_lane', 'status']}
                   for row in facts['mhj_college_seasons']]
    card = {**shared, 'artifact': 'predraft_reconstruction_card_v0', 'reconstruction_mode': 'historical_factual_candidate',
            'pre_draft_cutoff': facts['pre_draft_cutoff'], 'input_separation_policy': 'Shared builder reads draft facts for census and identity; this card excludes actual draft fields and NFL outcomes by validation and explicit field selection. No structural input isolation is claimed.',
            'player_id': MHJ, 'player_name': mhj_row['player_name'], 'position': 'WR',
            'identity': {'school': 'Ohio State', 'source_refs': ['college-mhj'], 'birth_date': None, 'age_at_entry': None},
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
               'evidence_cutoff': '2024-04-27T23:59:59Z', 'actual_draft_round': 1, 'actual_overall_pick': 4,
               'draft_team': 'ARI', 'source_refs': mhj_row['source_refs'],
               'status_note': 'Public factual candidate only; Data canonical draft handoff still unavailable. No grade or downstream runtime admission.'}
    census_rows = [{key: row[key] for key in DRAFT_RECORD_FIELDS} for row in facts['draft_day_records']]
    identity_rows = [{key: row[key] for key in IDENTITY_RESOLUTION_FIELDS}
                     for row in facts['identity_resolutions']]
    census = {**shared, 'artifact': '2024_skill_class_census_v0', 'cohort': facts['cohort'],
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
