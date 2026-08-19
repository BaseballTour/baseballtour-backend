from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.repositories.term_agreement_repository import (
    TermAgreementRepository,
)
from app.schemas.term import (
    TermAgreementDocument,
    TermCode,
)


NOW = datetime(
    2026,
    8,
    19,
    12,
    0,
    tzinfo=timezone.utc,
)


def test_save_all_stores_agreement_with_camel_case() -> None:
    client = MagicMock()
    users_collection = MagicMock()
    user_document = MagicMock()
    agreement_collection = MagicMock()
    agreement_document = MagicMock()
    batch = MagicMock()

    client.collection.return_value = (
        users_collection
    )

    users_collection.document.return_value = (
        user_document
    )

    user_document.collection.return_value = (
        agreement_collection
    )

    agreement_collection.document.return_value = (
        agreement_document
    )

    client.batch.return_value = batch

    repository = TermAgreementRepository(
        client=client,
    )

    agreement = TermAgreementDocument(
        version="1.0",
        agreed=True,
        agreed_at=NOW,
        updated_at=NOW,
    )

    repository.save_all(
        user_id="firebase-user-123",
        agreements={
            TermCode.TERMS_OF_SERVICE: agreement,
        },
    )

    users_collection.document.assert_called_once_with(
        "firebase-user-123"
    )

    user_document.collection.assert_called_once_with(
        "termAgreements"
    )

    agreement_collection.document.assert_called_once_with(
        "TERMS_OF_SERVICE"
    )

    batch.set.assert_called_once()

    stored = batch.set.call_args.args[1]

    assert stored["version"] == "1.0"
    assert stored["agreed"] is True
    assert stored["agreedAt"] == NOW
    assert stored["updatedAt"] == NOW

    batch.commit.assert_called_once_with()


def test_save_all_stores_multiple_agreements() -> None:
    client = MagicMock()
    users_collection = MagicMock()
    user_document = MagicMock()
    agreement_collection = MagicMock()
    batch = MagicMock()

    service_document = MagicMock()
    marketing_document = MagicMock()

    client.collection.return_value = (
        users_collection
    )

    users_collection.document.return_value = (
        user_document
    )

    user_document.collection.return_value = (
        agreement_collection
    )

    agreement_collection.document.side_effect = [
        service_document,
        marketing_document,
    ]

    client.batch.return_value = batch

    repository = TermAgreementRepository(
        client=client,
    )

    repository.save_all(
        user_id="firebase-user-123",
        agreements={
            TermCode.TERMS_OF_SERVICE: (
                TermAgreementDocument(
                    version="1.0",
                    agreed=True,
                    agreed_at=NOW,
                    updated_at=NOW,
                )
            ),
            TermCode.MARKETING: (
                TermAgreementDocument(
                    version="1.0",
                    agreed=False,
                    agreed_at=None,
                    updated_at=NOW,
                )
            ),
        },
    )

    assert batch.set.call_count == 2

    assert (
        agreement_collection
        .document.call_args_list[0]
        .args[0]
        == "TERMS_OF_SERVICE"
    )

    assert (
        agreement_collection
        .document.call_args_list[1]
        .args[0]
        == "MARKETING"
    )

    marketing_stored = (
        batch.set.call_args_list[1].args[1]
    )

    assert marketing_stored["agreed"] is False
    assert marketing_stored["agreedAt"] is None

    batch.commit.assert_called_once_with()
