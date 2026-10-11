import copy
import importlib.util
import json
import hashlib
import shutil
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reconstruction', ROOT / 'scripts/build_2024_reconstruction.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReconstructionAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads((ROOT / 'data/historical/reconstruction_2024/source_facts_v0.json').read_text())

    def test_missing_subject_cannot_look_like_complete_class(self):
        facts = copy.deepcopy(self.facts)
        facts['draft_day_records'].pop()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            module.validate_facts(facts)

    def test_duplicate_identity_is_rejected(self):
        facts = copy.deepcopy(self.facts)
        facts['draft_day_records'][1]['player_id'] = facts['draft_day_records'][0]['player_id']
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            module.validate_facts(facts)

    def test_future_draft_operand_cannot_enter_college_lane(self):
        facts = copy.deepcopy(self.facts)
        facts['college_observations'][0]['stats']['overall_pick'] = 1
        with self.assertRaisesRegex(ValueError, 'leaked'):
            module.validate_facts(facts)

    def test_actual_draft_aliases_are_rejected_in_both_college_lanes(self):
        for lane in ['college_observations', 'mhj_college_seasons']:
            for field in ['actual_overall_pick', 'actual_draft_round', 'draft_team_name']:
                for nested in [False, True]:
                    with self.subTest(lane=lane, field=field, nested=nested):
                        facts = copy.deepcopy(self.facts)
                        row = facts[lane][0]
                        (row.setdefault('stats', {}) if nested else row)[field] = 4
                        with self.assertRaisesRegex(ValueError, 'leaked'):
                            module.validate_facts(facts)

    def test_arbitrary_college_free_text_is_rejected(self):
        facts = copy.deepcopy(self.facts)
        facts['mhj_college_seasons'][0]['note'] = 'Drafted fourth overall by Arizona'
        with self.assertRaisesRegex(ValueError, 'college observation field'):
            module.validate_facts(facts)

    def test_arbitrary_nested_college_object_is_rejected(self):
        facts = copy.deepcopy(self.facts)
        facts['mhj_college_seasons'][0]['landing'] = {'actual_overall_pick': 4}
        with self.assertRaisesRegex(ValueError, 'college observation field'):
            module.validate_facts(facts)

    def test_empty_draft_sources_are_rejected(self):
        facts = copy.deepcopy(self.facts)
        facts['draft_day_records'][0]['source_refs'] = []
        with self.assertRaisesRegex(ValueError, 'Unresolved draft fact'):
            module.validate_facts(facts)

    def test_mutated_facts_cannot_claim_retained_source_hash(self):
        for mutation in ['cutoff', 'statistic']:
            with self.subTest(mutation=mutation):
                facts = copy.deepcopy(self.facts)
                if mutation == 'cutoff':
                    facts['pre_draft_cutoff'] = '2024-04-23T23:59:59Z'
                else:
                    row = facts['college_observations'][0]['stats']
                    key = next(iter(row))
                    row[key] += 1
                with self.assertRaisesRegex(ValueError, 'do not match retained source ledger'):
                    module.build(facts)

    def test_staging_source_hash_uses_supplied_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in self.facts['repo_file_bindings']:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            relative = 'data/historical/reconstruction_2024/source_facts_v0.json'
            source = root / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(json.dumps(self.facts, indent=4) + '\n')
            facts = json.loads(source.read_text())
            artifacts = module.build(facts, root=root)
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertNotEqual(expected, module.sha(ROOT / relative))
            for artifact in artifacts.values():
                if isinstance(artifact, dict):
                    self.assertEqual(artifact['source_facts_sha256'], expected)

    def test_shared_builder_does_not_claim_structural_input_isolation(self):
        card = module.build(self.facts)['predraft_cards/2024_wr_marvin_harrison_jr_predraft_v0.json']
        self.assertNotIn('nfl_outcome_fields_available_to_card_builder', card)
        self.assertIn('No structural input isolation', card['input_separation_policy'])

    def test_card_projects_only_allowlisted_college_fields(self):
        card = module.build(self.facts)['predraft_cards/2024_wr_marvin_harrison_jr_predraft_v0.json']
        self.assertTrue(all(set(row) == module.MHJ_SEASON_KEYS for row in card['college_production']))

    def test_unresolved_provenance_is_rejected(self):
        facts = copy.deepcopy(self.facts)
        facts['college_observations'][0]['source_refs'] = ['invented-source']
        with self.assertRaisesRegex(ValueError, 'Unresolved college source'):
            module.validate_facts(facts)

    def test_college_source_refs_require_a_string_list(self):
        for lane in ['college_observations', 'mhj_college_seasons']:
            with self.subTest(lane=lane):
                facts = copy.deepcopy(self.facts)
                source = facts[lane][0]['source_refs'][0]
                facts[lane][0]['source_refs'] = {source: {'actual_overall_pick': 4}}
                with self.assertRaisesRegex(ValueError, 'Unresolved college source'):
                    module.validate_facts(facts)

    def test_allowlisted_college_values_reject_nested_objects(self):
        facts = copy.deepcopy(self.facts)
        facts['mhj_college_seasons'][0]['games'] = {'count': 13}
        with self.assertRaisesRegex(ValueError, 'Non-factual count operand'):
            module.validate_facts(facts)
        facts = copy.deepcopy(self.facts)
        facts['college_observations'][-1]['source_locators'] = {
            facts['college_observations'][-1]['source_refs'][0]: {'page': 4}
        }
        with self.assertRaisesRegex(ValueError, 'Invalid college source locator'):
            module.validate_facts(facts)

    def test_derived_stat_groups_must_be_complete_and_nonzero(self):
        mutations = [
            {'attempts': 10},
            {'passing_tds': 10},
            {'completions': 0, 'attempts': 0, 'passing_yards': 0},
            {'rush_attempts': 0, 'rush_yards': 0},
            {'receptions': 0, 'receiving_yards': 0},
        ]
        for stats in mutations:
            with self.subTest(stats=stats):
                facts = copy.deepcopy(self.facts)
                facts['college_observations'][0]['stats'] = stats
                with self.assertRaisesRegex(ValueError, 'Incomplete or zero-denominator'):
                    module.validate_facts(facts)

    def test_final_season_observations_are_2023_only(self):
        facts = copy.deepcopy(self.facts)
        facts['college_observations'][0]['season'] = 2022
        with self.assertRaisesRegex(ValueError, 'Ineligible college season'):
            module.validate_facts(facts)
        module.validate_facts(self.facts)

    def test_mhj_history_requires_exactly_one_row_per_season(self):
        facts = copy.deepcopy(self.facts)
        facts['mhj_college_seasons'][0]['season'] = 2022
        with self.assertRaisesRegex(ValueError, 'Incomplete or duplicate MHJ'):
            module.validate_facts(facts)

    def test_draft_census_rejects_and_projects_unadmitted_fields(self):
        facts = copy.deepcopy(self.facts)
        facts['draft_day_records'][0]['fantasy_points'] = 100
        with self.assertRaisesRegex(ValueError, 'draft record field'):
            module.validate_facts(facts)
        census = module.build(self.facts)['2024_skill_class_census_v0.json']
        self.assertTrue(all(tuple(row) == module.DRAFT_RECORD_FIELDS for row in census['players']))

    def test_draft_census_validates_admitted_field_values(self):
        mutations = [
            ('class_year', 2025, 'draft record value'),
            ('draft_round', True, 'draft record value'),
            ('primary_locator', {'pdf_page': {'fantasy_points': 100}, 'column': 'left'}, 'draft source locator'),
        ]
        for field, value, message in mutations:
            with self.subTest(field=field):
                facts = copy.deepcopy(self.facts)
                facts['draft_day_records'][0][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    module.validate_facts(facts)

    def test_legacy_seed_rows_require_final_season_observations(self):
        facts = copy.deepcopy(self.facts)
        facts['college_observations'] = facts['college_observations'][1:]
        with self.assertRaisesRegex(ValueError, 'Missing final-season observation'):
            module.validate_facts(facts)

    def test_source_ledger_requires_qualified_retrieval_metadata(self):
        facts = copy.deepcopy(self.facts)
        facts['source_ledger'].append({'source_id': 'new-source'})
        facts['college_observations'][0]['source_refs'] = ['new-source']
        with self.assertRaisesRegex(ValueError, 'Invalid source ledger entry'):
            module.validate_facts(facts)

    def test_identity_resolutions_are_validated_and_projected(self):
        mutations = [
            ('fantasy_points', 100, 'identity resolution field'),
            ('pick', 5, 'identity resolution linkage'),
            ('name_source_refs', ['invented-source'], 'Unresolved identity source'),
            ('name_source_refs', ['college-caleb'], 'sources do not match draft row'),
        ]
        for field, value, message in mutations:
            with self.subTest(field=field):
                facts = copy.deepcopy(self.facts)
                facts['identity_resolutions'][0][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    module.validate_facts(facts)
        census = module.build(self.facts)['2024_skill_class_census_v0.json']
        self.assertTrue(all(tuple(row) == module.IDENTITY_RESOLUTION_FIELDS
                            for row in census['identity_resolutions']))

    def test_identity_resolution_set_is_complete(self):
        facts = copy.deepcopy(self.facts)
        facts['identity_resolutions'] = facts['identity_resolutions'][1:]
        with self.assertRaisesRegex(ValueError, 'Incomplete identity resolution set'):
            module.validate_facts(facts)

    def test_receiving_efficiency_does_not_require_touchdown_field(self):
        audit = module.build(self.facts)['input_integrity_audit_v0.json']
        brooks = next(row for row in audit['rows'] if row['player_id'] == 'rb-jonathon-brooks')
        self.assertEqual(brooks['candidate_2023_stats']['yards_per_reception'], 11.4)

    def test_missing_operands_do_not_emit_fallback_grade(self):
        artifacts = module.build(self.facts)
        rows = artifacts['coverage_matrix_v0.json']['players']
        self.assertTrue(all(x['pre_draft_grade']['value'] is None and x['post_draft_grade']['value'] is None for x in rows))
        mhj = artifacts['predraft_cards/2024_wr_marvin_harrison_jr_predraft_v0.json']
        self.assertNotIn('actual_overall_pick', mhj)
        self.assertNotIn('draft_team', mhj)
        self.assertIsNone(mhj['athletic_testing']['sporq_0_100'])


if __name__ == '__main__':
    unittest.main()
