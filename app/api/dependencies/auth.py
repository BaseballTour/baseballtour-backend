from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Security, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from firebase_admin import auth as firebase_auth

from app.core.exceptions import AppException
from app.core.firebase import initialize_firebase


AUTHENTICATE_HEADERS = {
    "WWW-Authenticate": "Bearer",
}

bearer_auth = HTTPBearer(
    auto_error=False,
    bearerFormat="Firebase ID Token",
    description=(
        "Firebase Authentication에서 발급받은 ID Token을 입력합니다. "
        "Swagger에서는 Bearer 접두사 없이 토큰 값만 입력합니다."
    ),
)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Firebase 인증 토큰에서 추출한 사용자 정보."""

    uid: str
    email: str | None


def create_auth_exception(
    *,
    code: str,
    message: str,
) -> AppException:
    return AppException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=code,
        message=message,
        headers=AUTHENTICATE_HEADERS,
    )


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_auth),
    ] = None,
) -> AuthenticatedUser:
    """Firebase ID Token을 검증하고 인증 사용자 정보를 반환한다."""

    authorization = request.headers.get("Authorization")

    if authorization is None:
        raise create_auth_exception(
            code="AUTH_TOKEN_MISSING",
            message="인증 토큰이 필요합니다.",
        )

    if credentials is None:
        raise create_auth_exception(
            code="AUTH_TOKEN_INVALID",
            message="인증 토큰 형식이 올바르지 않습니다.",
        )

    token = credentials.credentials.strip()

    if credentials.scheme.lower() != "bearer" or not token:
        raise create_auth_exception(
            code="AUTH_TOKEN_INVALID",
            message="인증 토큰 형식이 올바르지 않습니다.",
        )

    try:
        decoded_token = firebase_auth.verify_id_token(
            token,
            app=initialize_firebase(),
            check_revoked=True,
        )

    except firebase_auth.ExpiredIdTokenError as exc:
        raise create_auth_exception(
            code="AUTH_TOKEN_EXPIRED",
            message="인증 토큰이 만료되었습니다.",
        ) from exc

    except firebase_auth.RevokedIdTokenError as exc:
        raise create_auth_exception(
            code="AUTH_TOKEN_REVOKED",
            message="취소된 인증 토큰입니다.",
        ) from exc

    except firebase_auth.UserDisabledError as exc:
        raise create_auth_exception(
            code="AUTH_TOKEN_INVALID",
            message="사용할 수 없는 사용자 계정입니다.",
        ) from exc

    except (
        firebase_auth.InvalidIdTokenError,
        ValueError,
    ) as exc:
        raise create_auth_exception(
            code="AUTH_TOKEN_INVALID",
            message="유효하지 않은 인증 토큰입니다.",
        ) from exc

    except firebase_auth.CertificateFetchError as exc:
        raise AppException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="EXTERNAL_API_UNAVAILABLE",
            message="Firebase 인증 서비스를 일시적으로 사용할 수 없습니다.",
        ) from exc

    uid = decoded_token.get("uid")

    if not isinstance(uid, str) or not uid.strip():
        raise create_auth_exception(
            code="AUTH_TOKEN_INVALID",
            message="인증 토큰에 사용자 정보가 없습니다.",
        )

    email = decoded_token.get("email")

    normalized_email = (
        email.strip()
        if isinstance(email, str) and email.strip()
        else None
    )

    return AuthenticatedUser(
        uid=uid.strip(),
        email=normalized_email,
    )


async def get_current_user_id(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(get_current_user),
    ],
) -> str:
    """인증된 사용자의 Firebase UID만 반환한다."""

    return current_user.uid
