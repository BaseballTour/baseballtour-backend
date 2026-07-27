from typing import Annotated

from fastapi import Header, status
from firebase_admin import auth as firebase_auth

from app.core.exceptions import AppException
from app.core.firebase import initialize_firebase


AUTHENTICATE_HEADERS = {
    "WWW-Authenticate": "Bearer",
}


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


async def get_current_user_id(
    authorization: Annotated[
        str | None,
        Header(alias="Authorization"),
    ] = None,
) -> str:
    """Firebase ID Token을 검증하고 사용자 UID를 반환한다."""

    if authorization is None:
        raise create_auth_exception(
            code="AUTH_TOKEN_MISSING",
            message="인증 토큰이 필요합니다.",
        )

    scheme, separator, token = authorization.partition(" ")

    if (
        scheme.lower() != "bearer"
        or not separator
        or not token.strip()
    ):
        raise create_auth_exception(
            code="AUTH_TOKEN_INVALID",
            message="인증 토큰 형식이 올바르지 않습니다.",
        )

    try:
        decoded_token = firebase_auth.verify_id_token(
            token.strip(),
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

    return uid
