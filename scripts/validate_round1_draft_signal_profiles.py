import json
from pathlib import Path

REQUIRED_FIELDS = {
    "player_id",
    "player_name",
    "position",
    "pick",
    "team",
    "pre_draft_tiber_stance",
    "round1_signal_summary",
    "talent_confirmation_signal",
    "opportunity_insulation_signal",
    "short_term_fantasy_runway",
    "primary_risks",
    "translator_tags",
    "post_draft_handling",
    "notes",
}

TALENT_SIGNALS = {"elite", "strong", "moderate", "mixed", "uncertain"}
OPPORTUNITY_SIGNALS = {"elite", "strong", "moderate", "limited", "uncertain"}
RUNWAY_SIGNALS = {"immediate", "strong", "delayed", "blocked", "uncertain"}


def validate_profiles(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    if not isinstance(payload, list):
        return ["Profile file must be a JSON array."]

    for idx, profile in enumerate(payload):
        context = f"profiles[{idx}]"
        if not isinstance(profile, dict):
            errors.append(f"{context}: entry must be an object")
            continue

        missing = REQUIRED_FIELDS - set(profile.keys())
        if missing:
            errors.append(f"{context}: missing required fields: {sorted(missing)}")

        talent = profile.get("talent_confirmation_signal")
        if talent not in TALENT_SIGNALS:
            errors.append(f"{context}: invalid talent_confirmation_signal '{talent}'")

        opportunity = profile.get("opportunity_insulation_signal")
        if opportunity not in OPPORTUNITY_SIGNALS:
            errors.append(f"{context}: invalid opportunity_insulation_signal '{opportunity}'")

        runway = profile.get("short_term_fantasy_runway")
        if runway not in RUNWAY_SIGNALS:
            errors.append(f"{context}: invalid short_term_fantasy_runway '{runway}'")

        for list_field in ("primary_risks", "translator_tags"):
            value = profile.get(list_field)
            if not isinstance(value, list):
                errors.append(f"{context}: {list_field} must be a list")

    return errors


if __name__ == "__main__":
    profile_path = Path("data/processed/2026_round1_draft_signal_profiles.json")
    validation_errors = validate_profiles(profile_path)
    if validation_errors:
        print("Round 1 draft signal profile validation failed:")
        for err in validation_errors:
            print(f"- {err}")
        raise SystemExit(1)

    print(f"Validated {profile_path}")
