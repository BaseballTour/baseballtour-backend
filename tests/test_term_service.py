from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppException
from app.schemas.term import (
    TermAgreementItemRequest,
    TermAgreementsRequest,
    TermCode,
    TermRecord,
)
from app.services.term_service import TermService


NOW = datetime(
    2026,
    8,
    19,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_term(
    term_code: TermCode,
    *,
    required: bool,
    version: str = "1.0",
) -> TermRecord:
    return TermRecord(
        term_id=f"{term_code.value}_{version}",
        term_code=term_code,
        title=f"{term_code.value} 약관",
        required=required,
        version=version,
        content="약관 본문",
        effective_at=NOW,
        active=True,
    )


def make_service():
    term_repository = MagicMock()
    agreement_repository = MagicMock()

    service = TermService(
        term_repository=term_repository,
        term_agreement_repository=(
            agreement_repository
        ),
    )

    return (
        service,
        term_repository,
        agreement_repository,
    )


def active_terms() -> list[TermRecord]:
    return [
        make_term(
            TermCode.TERMS_OF_SERVICE,
            required=True,
        ),
        make_term(
            TermCode.PRIVACY_POLICY,
            required=True,
        ),
        make_term(
            TermCode.LOCATION_BASED_SERVICE,
            required=True,
        ),
        make_term(
            TermCode.MARKETING,
            required=False,
        ),
    ]


def required_agreements():
    return [
        TermAgreementItemRequest(
            term_code=TermCode.TERMS_OF_SERVICE,
            version="1.0",
            agreed=True,
        ),
        TermAgreementItemRequest(
            term_code=TermCode.PRIVACY_POLICY,
            version="1.0",
            agreed=True,
        ),
        TermAgreementItemRequest(
            term_code=(
                TermCode.LOCATION_BASED_SERVICE
            ),
            version="1.0",
            agreed=True,
        ),
    ]


def test_get_active_terms_returns_response() -> None:
    (
        service,
        term_repository,
        _,
    ) = make_service()

    term_repository.get_active_terms.return_value = (
        active_terms()
    )

    result = service.get_active_terms()

    assert len(result) == 4

    assert (
        result[0].term_code
        == TermCode.TERMS_OF_SERVICE
    )

    assert result[0].version == "1.0"


def test_save_agreements_saves_required_terms() -> None:
    (
        service,
        term_repository,
        agreement_repository,
    ) = make_service()

    term_repository.get_active_terms.return_value = (
        active_terms()
    )

    request = TermAgreementsRequest(
        agreements=required_agreements(),
    )

    result = service.save_agreements(
        user_id="firebase-user-123",
        request=request,
    )

    assert len(result.agreements) == 3

    agreement_repository.save_all.assert_called_once()

    call = agreement_repository.save_all.call_args

    assert (
        call.kwargs["user_id"]
        == "firebase-user-123"
    )

    stored = call.kwargs["agreements"]

    assert (
        stored[
            TermCode.TERMS_OF_SERVICE
        ].agreed
        is True
    )

    assert (
        stored[
            TermCode.TERMS_OF_SERVICE
        ].agreed_at
        is not None
    )


def test_save_agreements_allows_marketing_false() -> None:
    (
        service,
        term_repository,
        agreement_repository,
    ) = make_service()

    term_repository.get_active_terms.return_value = (
        active_terms()
    )

    agreements = required_agreements()

    agreements.append(
        TermAgreementItemRequest(
            term_code=TermCode.MARKETING,
            version="1.0",
            agreed=False,
        )
    )

    result = service.save_agreements(
        user_id="firebase-user-123",
        request=TermAgreementsRequest(
            agreements=agreements,
        ),
    )

    marketing = next(
        agreement
        for agreement in result.agreements
        if agreement.term_code
        == TermCode.MARKETING
    )

    assert marketing.agreed is False
    assert marketing.agreed_at is None

    stored = (
        agreement_repository
        .save_all.call_args.kwargs[
            "agreements"
        ]
    )

    assert (
        stored[TermCode.MARKETING].agreed
        is False
    )


def test_save_agreements_allows_marketing_omitted() -> None:
    (
        service,
        term_repository,
        agreement_repository,
    ) = make_service()

    term_repository.get_active_terms.return_value = (
        active_terms()
    )

    service.save_agreements(
        user_id="firebase-user-123",
        request=TermAgreementsRequest(
            agreements=required_agreements(),
        ),
    )

    stored = (
        agreement_repository
        .save_all.call_args.kwargs[
            "agreements"
        ]
    )

    assert TermCode.MARKETING not in stored


def test_save_agreements_rejects_missing_required_term() -> None:
    (
        service,
        term_repository,
        agreement_repository,
    ) = make_service()

    term_repository.get_active_terms.return_value = (
        active_terms()
    )

    request = TermAgreementsRequest(
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
                    TermCode.PRIVACY_POLICY
                ),
                version="1.0",
                agreed=True,
            ),
        ]
    )

    with pytest.raises(AppException) as captured:
        service.save_agreements(
            user_id="firebase-user-123",
            request=request,
        )

    assert captured.value.status_code == 400

    assert captured.value.code == (
        "REQUIRED_TERM_NOT_AGREED"
    )

    agreement_repository.save_all.assert_not_called()


def test_save_agreements_rejects_required_false() -> None:
    (
        service,
        term_repository,
        agreement_repository,
    ) = make_service()

    term_repository.get_active_terms.return_value = (
        active_terms()
    )

    agreements = required_agreements()

    agreements[0] = TermAgreementItemRequest(
        term_code=TermCode.TERMS_OF_SERVICE,
        version="1.0",
        agreed=False,
    )

    with pytest.raises(AppException) as captured:
        service.save_agreements(
            user_id="firebase-user-123",
            request=TermAgreementsRequest(
                agreements=agreements,
            ),
        )

    assert captured.value.status_code == 400

    assert captured.value.code == (
        "REQUIRED_TERM_NOT_AGREED"
    )

    agreement_repository.save_all.assert_not_called()


def test_save_agreements_rejects_old_version() -> None:
    (
        service,
        term_repository,
        agreement_repository,
    ) = make_service()

    term_repository.get_active_terms.return_value = (
        active_terms()
    )

    agreements = required_agreements()

    agreements[0] = TermAgreementItemRequest(
        term_code=TermCode.TERMS_OF_SERVICE,
        version="0.9",
        agreed=True,
    )

    with pytest.raises(AppException) as captured:
        service.save_agreements(
            user_id="firebase-user-123",
            request=TermAgreementsRequest(
                agreements=agreements,
            ),
        )

    assert captured.value.status_code == 409

    assert captured.value.code == (
        "TERM_VERSION_MISMATCH"
    )

    agreement_repository.save_all.assert_not_called()


def test_save_agreements_rejects_inactive_term() -> None:
    (
        service,
        term_repository,
        agreement_repository,
    ) = make_service()

    current_terms = active_terms()

    current_terms = [
        term
        for term in current_terms
        if term.term_code
        != TermCode.MARKETING
    ]

    term_repository.get_active_terms.return_value = (
        current_terms
    )

    agreements = required_agreements()

    agreements.append(
        TermAgreementItemRequest(
            term_code=TermCode.MARKETING,
            version="1.0",
            agreed=True,
        )
    )

    with pytest.raises(AppException) as captured:
        service.save_agreements(
            user_id="firebase-user-123",
            request=TermAgreementsRequest(
                agreements=agreements,
            ),
        )

    assert captured.value.status_code == 400
    assert captured.value.code == "TERM_NOT_ACTIVE"

    agreement_repository.save_all.assert_not_called()
