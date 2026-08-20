from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from firebase_admin import auth as firebase_auth

from app.api.dependencies import auth as auth_dependency
from app.core.exception_handlers import register_exception_handlers


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected_endpoint(
        user_id: Annotated[
            str,
            Depends(auth_dependency.get_current_user_id),
        ],
    ) -> dict[str, str]:
        return {
            "userId": user_id,
        }

    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_firebase_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth_dependency,
        "initialize_firebase",
        lambda: object(),
    )


def test_missing_authorization_header_returns_401(
    client: TestClient,
) -> None:
    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "error": {
            "code": "AUTH_TOKEN_MISSING",
            "message": "인증 토큰이 필요합니다.",
            "details": [],
        },
    }
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_authorization_scheme_returns_401(
    client: TestClient,
) -> None:
    response = client.get(
        "/protected",
        headers={"Authorization": "Basic test-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_invalid_firebase_token_returns_401(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_invalid_token(*args: object, **kwargs: object) -> None:
        raise firebase_auth.InvalidIdTokenError("invalid token")

    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        raise_invalid_token,
    )

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_expired_firebase_token_returns_401(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_expired_token(*args: object, **kwargs: object) -> None:
        raise firebase_auth.ExpiredIdTokenError(
            "expired token",
            None,
        )

    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        raise_expired_token,
    )

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"


def test_revoked_firebase_token_returns_401(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_revoked_token(*args: object, **kwargs: object) -> None:
        raise firebase_auth.RevokedIdTokenError(
            "revoked token",
        )

    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        raise_revoked_token,
    )

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer revoked-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_REVOKED"


def test_token_without_uid_returns_401(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        lambda *args, **kwargs: {"email": "fan@example.com"},
    )

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_valid_token_returns_user_uid(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def verify_token(
        token: str,
        *,
        app: object,
        check_revoked: bool,
    ) -> dict[str, str]:
        received["token"] = token
        received["app"] = app
        received["check_revoked"] = check_revoked

        return {
            "uid": "firebase-user-123",
        }

    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        verify_token,
    )

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "userId": "firebase-user-123",
    }
    assert received["token"] == "valid-token"
    assert received["check_revoked"] is True


def test_openapi_exposes_bearer_authorization(
    client: TestClient,
) -> None:
    schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "description": (
            "Firebase Authentication에서 발급받은 ID Token을 입력합니다. "
            "Swagger에서는 Bearer 접두사 없이 토큰 값만 입력합니다."
        ),
        "scheme": "bearer",
        "bearerFormat": "Firebase ID Token",
    }
    assert schema["paths"]["/protected"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]


@pytest.fixture
def authenticated_user_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected-user")
    async def protected_user_endpoint(
        current_user: Annotated[
            auth_dependency.AuthenticatedUser,
            Depends(auth_dependency.get_current_user),
        ],
    ) -> dict[str, str | None]:
        return {
            "userId": current_user.uid,
            "email": current_user.email,
        }

    return TestClient(app)


def test_valid_token_returns_authenticated_user(
    authenticated_user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        lambda *args, **kwargs: {
            "uid": "firebase-user-123",
            "email": "fan@example.com",
        },
    )

    response = authenticated_user_client.get(
        "/protected-user",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "userId": "firebase-user-123",
        "email": "fan@example.com",
    }


def test_valid_token_without_email_returns_none(
    authenticated_user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        lambda *args, **kwargs: {
            "uid": "firebase-user-123",
        },
    )

    response = authenticated_user_client.get(
        "/protected-user",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "userId": "firebase-user-123",
        "email": None,
    }


@pytest.fixture
def active_user_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/active-user")
    async def active_user_endpoint(
        user_id: Annotated[
            str,
            Depends(
                auth_dependency.get_current_active_user_id
            ),
        ],
    ) -> dict[str, str]:
        return {
            "userId": user_id,
        }

    return TestClient(app)


def make_user_document(
    *,
    deleted_at=None,
):
    from datetime import datetime, timezone

    from app.schemas.user import UserDocument

    now = datetime.now(timezone.utc)

    return UserDocument(
        email="fan@example.com",
        nickname="테스트사용자",
        birth_year=2002,
        support_team_id="doosan",
        profile_image_url=None,
        onboarding_completed=True,
        created_at=now,
        updated_at=now,
        deleted_at=deleted_at,
    )


def test_active_user_dependency_allows_active_user(
    active_user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        lambda *args, **kwargs: {
            "uid": "firebase-user-123",
        },
    )

    repository = type(
        "StubUserRepository",
        (),
        {
            "get_by_id": lambda self, user_id: (
                make_user_document()
            ),
        },
    )

    monkeypatch.setattr(
        auth_dependency,
        "UserRepository",
        repository,
    )

    response = active_user_client.get(
        "/active-user",
        headers={
            "Authorization": "Bearer valid-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "userId": "firebase-user-123",
    }


def test_active_user_dependency_rejects_deleted_user(
    active_user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timezone

    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        lambda *args, **kwargs: {
            "uid": "firebase-user-123",
        },
    )

    deleted_at = datetime.now(timezone.utc)

    repository = type(
        "StubUserRepository",
        (),
        {
            "get_by_id": lambda self, user_id: (
                make_user_document(
                    deleted_at=deleted_at,
                )
            ),
        },
    )

    monkeypatch.setattr(
        auth_dependency,
        "UserRepository",
        repository,
    )

    response = active_user_client.get(
        "/active-user",
        headers={
            "Authorization": "Bearer valid-token",
        },
    )

    assert response.status_code == 403
    assert (
        response.json()["error"]["code"]
        == "USER_DELETED"
    )


def test_active_user_dependency_rejects_missing_profile(
    active_user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_dependency.firebase_auth,
        "verify_id_token",
        lambda *args, **kwargs: {
            "uid": "firebase-user-123",
        },
    )

    repository = type(
        "StubUserRepository",
        (),
        {
            "get_by_id": lambda self, user_id: None,
        },
    )

    monkeypatch.setattr(
        auth_dependency,
        "UserRepository",
        repository,
    )

    response = active_user_client.get(
        "/active-user",
        headers={
            "Authorization": "Bearer valid-token",
        },
    )

    assert response.status_code == 404
    assert (
        response.json()["error"]["code"]
        == "USER_NOT_FOUND"
    )
