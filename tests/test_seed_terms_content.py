from scripts.seed_terms import (
    INACTIVE_TERM_IDS,
    MARKETING,
    PRIVACY_POLICY,
    SERVICE_NAME,
    TERMS,
    TERMS_OF_SERVICE,
)


def test_terms_use_actual_service_name() -> None:
    assert SERVICE_NAME == "야구원정대"

    for content in (
        TERMS_OF_SERVICE,
        PRIVACY_POLICY,
        MARKETING,
    ):
        assert "KBO Travel" not in content
        assert "야구원정대" in content


def test_privacy_policy_uses_correct_particle() -> None:
    assert "야구원정대는 서비스 제공을 위해" in PRIVACY_POLICY
    assert "야구원정대은" not in PRIVACY_POLICY


def test_active_terms_use_version_1_2() -> None:
    assert set(TERMS) == {
        "TERMS_OF_SERVICE_1.2",
        "PRIVACY_POLICY_1.2",
        "MARKETING_1.2",
    }

    assert all(
        term.version == "1.2"
        for term in TERMS.values()
    )


def test_previous_active_terms_are_inactive() -> None:
    assert "TERMS_OF_SERVICE_1.1" in INACTIVE_TERM_IDS
    assert "PRIVACY_POLICY_1.1" in INACTIVE_TERM_IDS
    assert "MARKETING_1.1" in INACTIVE_TERM_IDS


def test_terms_effective_date_is_2026_09_13() -> None:
    for term in TERMS.values():
        assert term.effective_at.year == 2026
        assert term.effective_at.month == 9
        assert term.effective_at.day == 13
