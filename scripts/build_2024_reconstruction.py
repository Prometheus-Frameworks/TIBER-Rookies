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
FORBIDDEN_COLLEGE_KEYS = {'actual_overall_pick', 'actual_draft_round', 'overall_pick', 'draft_round', 'draft_team', 'draft_team_name', 'nfl_outcomes', 'nfl_stats', 'fantasy_points'}
COLLEGE_OBSERVATION_KEYS = {'player_id', 'season', 'stats', 'source_refs', 'source_locators', 'evidence_lane', 'status'}
COLLEGE_OBSERVATION_REQUIRED = COLLEGE_OBSERVATION_KEYS - {'source_locators'}
MHJ_SEASON_KEYS = {'season', 'games', 'receptions', 'receiving_yards', 'receiving_tds', 'source_refs', 'evidence_lane', 'status'}
COLLEGE_STAT_KEYS = {'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions',
                     'rush_attempts', 'rush_yards', 'rush_tds',
                     'receptions', 'receiving_yards', 'receiving_tds'}
COLLEGE_STATUS = 'public_factual_candidate_pending_independent_review'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_facts(facts: dict, root: Path = ROOT) -> None:
    if facts.get('class_year') != 2024 or facts.get('promotable') is not False:
        raise ValueError('Wrong class or promotion state')
    rows = facts['draft_day_records']
    if len(rows) != 78 or Counter(x['position'] for x in rows) != EXPECTED:
        raise ValueError('Incomplete or misclassified 2024 skill census')
    for field in ['player_id', 'overall_pick']:
        if len({x[field] for x in rows}) != len(rows):
            raise ValueError('Duplicate census ' + field)
    sources = {x['source_id'] for x in facts['source_ledger']}
    if len(sources) != len(facts['source_ledger']):
        raise ValueError('Duplicate source identity')
    ids = {x['player_id'] for x in rows}
    observations = facts['college_observations']
    if len({x['player_id'] for x in observations}) != len(observations):
        raise ValueError('Duplicate final-season college observation')
    lanes = [(observations, COLLEGE_OBSERVATION_KEYS, COLLEGE_OBSERVATION_REQUIRED),
             (facts['mhj_college_seasons'], MHJ_SEASON_KEYS, MHJ_SEASON_KEYS)]
    for lane, allowed, required in lanes:
        for obs in lane:
            if FORBIDDEN_COLLEGE_KEYS.intersection(obs) or FORBIDDEN_COLLEGE_KEYS.intersection(obs.get('stats', {})):
                raise ValueError('Draft/NFL evidence leaked into college observations')
            if set(obs) - allowed or required - set(obs):
                raise ValueError('Unexpected or missing college observation field')
            if 'stats' in obs and (type(obs['stats']) is not dict or set(obs['stats']) - COLLEGE_STAT_KEYS):
                raise ValueError('Unexpected college statistic field')
            if obs['season'] not in [2021, 2022, 2023] or obs['evidence_lane'] != 'college_production':
                raise ValueError('Ineligible college season/lane')
            if obs['status'] != COLLEGE_STATUS:
                raise ValueError('Unexpected college observation status')
            if not obs['source_refs'] or not set(obs['source_refs']).issubset(sources):
                raise ValueError('Unresolved college source')
            if 'player_id' in obs and obs['player_id'] not in ids:
                raise ValueError('Unresolved college identity')
            for key, value in obs.get('stats', {}).items():
                if type(value) is not int or value < 0:
                    raise ValueError('Non-factual count operand: ' + key)
    for row in rows:
        if not row['source_refs'] or not set(row['source_refs']).issubset(sources) or not 1 <= row['overall_pick'] <= 257:
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
    if 'receiving_tds' in stats:
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
    census = {**shared, 'artifact': '2024_skill_class_census_v0', 'cohort': facts['cohort'],
              'identity_resolutions': facts['identity_resolutions'], 'players': facts['draft_day_records']}
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
