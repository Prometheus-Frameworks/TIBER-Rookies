import unittest
from pathlib import Path

from scripts.validate_round1_draft_signal_profiles import validate_profiles


class Round1DraftSignalProfilesTests(unittest.TestCase):
    def test_profiles_validate(self) -> None:
        profile_path = Path("data/processed/2026_round1_draft_signal_profiles.json")
        errors = validate_profiles(profile_path)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
