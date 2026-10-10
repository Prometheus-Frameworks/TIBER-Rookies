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
