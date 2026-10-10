import copy
import importlib.util
import json
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
