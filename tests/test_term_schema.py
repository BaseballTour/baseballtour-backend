from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.term import (
    TermAgreementItemRequest,
    TermAgreementsRequest,
    TermCode,
    TermDocument,
)


NOW = datetime(
    2026,
    8,
    19,
    12,
    0,
    tzinfo=timezone.utc,
)


def test_term_document_uses_camel_case_aliases() -> None:
    document = TermDocument(
        term_code=TermCode.TERMS_OF_SERVICE,
        title="서비스 이용 약관",
        required=True,
        version="1.0",
        content="서비스 이용 약관 본문",
        effective_at=NOW,
        active=True,
    )

    stored = document.model_dump(
        by_alias=True,
        mode="json",
    )

    assert stored["termCode"] == "TERMS_OF_SERVICE"
    assert stored["effectiveAt"] == (
        "2026-08-19T12:00:00Z"
    )


def test_term_agreements_accept_valid_request() -> None:
    request = TermAgreementsRequest(
        agreements=[
            TermAgreementItemRequest(
                term_code=TermCode.TERMS_OF_SERVICE,
                version="1.0",
                agreed=True,
            ),
            TermAgreementItemRequest(
                term_code=TermCode.MARKETING,
                version="1.0",
                agreed=False,
            ),
        ]
    )

    assert len(request.agreements) == 2
    assert request.agreements[1].agreed is False


def test_term_agreements_reject_duplicate_term_code() -> None:
    with pytest.raises(ValidationError):
        TermAgreementsRequest(
            agreements=[
                TermAgreementItemRequest(
                    term_code=(
                        TermCode.TERMS_OF_SERVICE
                    ),
                    version="1.0",
                    agreed=True,
                ),
                TermAgreementItemRequest(
                    term_code=(
                        TermCode.TERMS_OF_SERVICE
                    ),
                    version="1.0",
                    agreed=True,
                ),
            ]
        )


def test_term_agreement_rejects_invalid_code() -> None:
    with pytest.raises(ValidationError):
        TermAgreementItemRequest(
            term_code="UNKNOWN_TERM",
            version="1.0",
            agreed=True,
        )


def test_term_document_requires_content() -> None:
    with pytest.raises(ValidationError):
        TermDocument(
            term_code=TermCode.PRIVACY_POLICY,
            title="개인정보 수집·이용 동의",
            required=True,
            version="1.0",
            content="",
            effective_at=NOW,
            active=True,
        )
