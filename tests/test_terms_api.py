from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    AuthenticatedUser,
    get_current_user,
    get_current_user_id,
)
from app.core.exceptions import AppException
from app.main import app
from app.schemas.term import (
    TermAgreementResponse,
    TermAgreementsResponse,
    TermCode,
    TermResponse,
)


FIXED_TIME = datetime(
    2026,
    8,
    19,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_terms() -> list[TermResponse]:
    return [
        TermResponse(
            term_code=TermCode.TERMS_OF_SERVICE,
            title="서비스 이용 약관",
            required=True,
            version="1.0",
            content="서비스 이용 약관 본문",
            effective_at=FIXED_TIME,
        ),
        TermResponse(
            term_code=TermCode.PRIVACY_POLICY,
            title="개인정보 수집·이용 동의",
            required=True,
            version="1.0",
            content="개인정보 약관 본문",
            effective_at=FIXED_TIME,
        ),
        TermResponse(
            term_code=(
                TermCode.LOCATION_BASED_SERVICE
            ),
            title="위치기반 서비스 이용 동의",
            required=True,
            version="1.0",
            content="위치기반 서비스 약관 본문",
            effective_at=FIXED_TIME,
        ),
        TermResponse(
            term_code=TermCode.MARKETING,
            title="홍보 및 마케팅 이용 동의",
            required=False,
            version="1.0",
            content="마케팅 약관 본문",
            effective_at=FIXED_TIME,
        ),
    ]


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[
        get_current_user
    ] = lambda: AuthenticatedUser(
        uid="firebase-user-123",
        email="fan@example.com",
    )

    app.dependency_overrides[
        get_current_user_id
    ] = lambda: "firebase-user-123"

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_get_terms_does_not_require_authentication() -> None:
    service = Mock()
    service.get_active_terms.return_value = make_terms()

    with patch(
        "app.api.v1.endpoints.terms.TermService",
        return_value=service,
    ):
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/terms",
            )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["meta"]["count"] == 4

    assert [
        term["termCode"]
        for term in body["data"]
    ] == [
        "TERMS_OF_SERVICE",
        "PRIVACY_POLICY",
        "LOCATION_BASED_SERVICE",
        "MARKETING",
    ]

    assert body["data"][0]["required"] is True
    assert body["data"][3]["required"] is False

    service.get_active_terms.assert_called_once_with()


def test_save_term_agreements_returns_saved_result(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.save_agreements.return_value = (
        TermAgreementsResponse(
            agreements=[
                TermAgreementResponse(
                    term_code=(
                        TermCode.TERMS_OF_SERVICE
                    ),
                    version="1.0",
                    agreed=True,
                    agreed_at=FIXED_TIME,
                ),
                TermAgreementResponse(
                    term_code=(
                        TermCode.PRIVACY_POLICY
                    ),
                    version="1.0",
                    agreed=True,
                    agreed_at=FIXED_TIME,
                ),
                TermAgreementResponse(
                    term_code=(
                        TermCode.LOCATION_BASED_SERVICE
                    ),
                    version="1.0",
                    agreed=True,
                    agreed_at=FIXED_TIME,
                ),
                TermAgreementResponse(
                    term_code=TermCode.MARKETING,
                    version="1.0",
                    agreed=False,
                    agreed_at=None,
                ),
            ]
        )
    )

    with patch(
        "app.api.v1.endpoints.users.TermService",
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/users/me/term-agreements",
            json={
                "agreements": [
                    {
                        "termCode": (
                            "TERMS_OF_SERVICE"
                        ),
                        "version": "1.0",
                        "agreed": True,
                    },
                    {
                        "termCode": (
                            "PRIVACY_POLICY"
                        ),
                        "version": "1.0",
                        "agreed": True,
                    },
                    {
                        "termCode": (
                            "LOCATION_BASED_SERVICE"
                        ),
                        "version": "1.0",
                        "agreed": True,
                    },
                    {
                        "termCode": "MARKETING",
                        "version": "1.0",
                        "agreed": False,
                    },
                ]
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert len(body["data"]["agreements"]) == 4

    assert (
        body["data"]["agreements"][0][
            "termCode"
        ]
        == "TERMS_OF_SERVICE"
    )

    assert (
        body["data"]["agreements"][3][
            "agreed"
        ]
        is False
    )

    arguments = (
        service.save_agreements.call_args.kwargs
    )

    assert (
        arguments["user_id"]
        == "firebase-user-123"
    )

    assert len(
        arguments["request"].agreements
    ) == 4


def test_save_term_agreements_requires_authentication(
) -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/users/me/term-agreements",
            json={
                "agreements": [
                    {
                        "termCode": (
                            "TERMS_OF_SERVICE"
                        ),
                        "version": "1.0",
                        "agreed": True,
                    }
                ]
            },
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert (
        body["error"]["code"]
        == "AUTH_TOKEN_MISSING"
    )


def test_save_term_agreements_returns_required_error(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.save_agreements.side_effect = (
        AppException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            code="REQUIRED_TERM_NOT_AGREED",
            message=(
                "필수 약관에 모두 동의해야 합니다."
            ),
        )
    )

    with patch(
        "app.api.v1.endpoints.users.TermService",
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/users/me/term-agreements",
            json={
                "agreements": [
                    {
                        "termCode": (
                            "TERMS_OF_SERVICE"
                        ),
                        "version": "1.0",
                        "agreed": True,
                    }
                ]
            },
        )

    assert response.status_code == 400

    assert (
        response.json()["error"]["code"]
        == "REQUIRED_TERM_NOT_AGREED"
    )


def test_save_term_agreements_returns_version_mismatch(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.save_agreements.side_effect = (
        AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="TERM_VERSION_MISMATCH",
            message=(
                "현재 약관 버전과 "
                "요청한 버전이 일치하지 않습니다."
            ),
        )
    )

    with patch(
        "app.api.v1.endpoints.users.TermService",
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/users/me/term-agreements",
            json={
                "agreements": [
                    {
                        "termCode": (
                            "TERMS_OF_SERVICE"
                        ),
                        "version": "0.9",
                        "agreed": True,
                    }
                ]
            },
        )

    assert response.status_code == 409

    assert (
        response.json()["error"]["code"]
        == "TERM_VERSION_MISMATCH"
    )


def test_save_term_agreements_rejects_duplicate_term(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/users/me/term-agreements",
        json={
            "agreements": [
                {
                    "termCode": (
                        "TERMS_OF_SERVICE"
                    ),
                    "version": "1.0",
                    "agreed": True,
                },
                {
                    "termCode": (
                        "TERMS_OF_SERVICE"
                    ),
                    "version": "1.0",
                    "agreed": True,
                },
            ]
        },
    )

    assert response.status_code == 422

    assert (
        response.json()["error"]["code"]
        == "VALIDATION_ERROR"
    )


def test_save_term_agreements_rejects_unknown_term(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/users/me/term-agreements",
        json={
            "agreements": [
                {
                    "termCode": "UNKNOWN_TERM",
                    "version": "1.0",
                    "agreed": True,
                }
            ]
        },
    )

    assert response.status_code == 422

    assert (
        response.json()["error"]["code"]
        == "VALIDATION_ERROR"
    )
