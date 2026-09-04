from scripts.seed_teams import TEAMS


def test_seed_contains_all_kbo_teams() -> None:
    assert set(TEAMS) == {
        "doosan",
        "lg",
        "kiwoom",
        "ssg",
        "kt",
        "hanwha",
        "kia",
        "samsung",
        "lotte",
        "nc",
    }


def test_seed_does_not_use_placeholder_logo_urls() -> None:
    for team in TEAMS.values():
        assert team.logo_url is None
        assert team.logo_storage_path is None
