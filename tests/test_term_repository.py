from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.repositories.term_repository import (
    TermRepository,
)
from app.schemas.term import TermCode


NOW = datetime(
    2026,
    8,
    19,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_term_snapshot(
    *,
    document_id: str,
    term_code: str,
    active: bool = True,
) -> MagicMock:
    snapshot = MagicMock()

    snapshot.id = document_id
    snapshot.exists = True

    snapshot.to_dict.return_value = {
        "termCode": term_code,
        "title": f"{term_code} 약관",
        "required": (
            term_code != "MARKETING"
        ),
        "version": "1.0",
        "content": "약관 본문",
        "effectiveAt": NOW,
        "active": active,
    }

    return snapshot


def test_get_active_terms_returns_active_terms() -> None:
    client = MagicMock()
    collection = MagicMock()

    client.collection.return_value = collection

    collection.stream.return_value = [
        make_term_snapshot(
            document_id="TERMS_OF_SERVICE_1.0",
            term_code="TERMS_OF_SERVICE",
        ),
        make_term_snapshot(
            document_id="PRIVACY_POLICY_1.0",
            term_code="PRIVACY_POLICY",
        ),
    ]

    repository = TermRepository(
        client=client,
    )

    result = repository.get_active_terms()

    assert len(result) == 2

    assert {
        term.term_code
        for term in result
    } == {
        TermCode.TERMS_OF_SERVICE,
        TermCode.PRIVACY_POLICY,
    }


def test_get_active_terms_excludes_inactive_terms() -> None:
    client = MagicMock()
    collection = MagicMock()

    client.collection.return_value = collection

    collection.stream.return_value = [
        make_term_snapshot(
            document_id="TERMS_OF_SERVICE_1.0",
            term_code="TERMS_OF_SERVICE",
            active=True,
        ),
        make_term_snapshot(
            document_id="MARKETING_0.9",
            term_code="MARKETING",
            active=False,
        ),
    ]

    repository = TermRepository(
        client=client,
    )

    result = repository.get_active_terms()

    assert len(result) == 1
    assert (
        result[0].term_code
        == TermCode.TERMS_OF_SERVICE
    )


def test_get_active_terms_uses_document_id() -> None:
    client = MagicMock()
    collection = MagicMock()

    client.collection.return_value = collection

    collection.stream.return_value = [
        make_term_snapshot(
            document_id="MARKETING_1.0",
            term_code="MARKETING",
        ),
    ]

    repository = TermRepository(
        client=client,
    )

    result = repository.get_active_terms()

    assert result[0].term_id == "MARKETING_1.0"


def test_get_active_terms_returns_signup_order() -> None:
    client = MagicMock()
    collection = MagicMock()

    client.collection.return_value = collection

    collection.stream.return_value = [
        make_term_snapshot(
            document_id="MARKETING_1.0",
            term_code="MARKETING",
        ),
        make_term_snapshot(
            document_id="LOCATION_BASED_SERVICE_1.0",
            term_code="LOCATION_BASED_SERVICE",
        ),
        make_term_snapshot(
            document_id="TERMS_OF_SERVICE_1.0",
            term_code="TERMS_OF_SERVICE",
        ),
        make_term_snapshot(
            document_id="PRIVACY_POLICY_1.0",
            term_code="PRIVACY_POLICY",
        ),
    ]

    repository = TermRepository(
        client=client,
    )

    result = repository.get_active_terms()

    assert [
        term.term_code
        for term in result
    ] == [
        TermCode.TERMS_OF_SERVICE,
        TermCode.PRIVACY_POLICY,
        TermCode.LOCATION_BASED_SERVICE,
        TermCode.MARKETING,
    ]
