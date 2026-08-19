from datetime import datetime, timezone

from fastapi import status

from app.core.exceptions import AppException
from app.repositories.term_agreement_repository import (
    TermAgreementRepository,
)
from app.repositories.term_repository import TermRepository
from app.schemas.term import (
    TermAgreementDocument,
    TermAgreementResponse,
    TermAgreementsRequest,
    TermAgreementsResponse,
    TermCode,
    TermResponse,
)


class TermService:
    """약관 조회 및 사용자 동의 관련 비즈니스 로직."""

    def __init__(
        self,
        term_repository: TermRepository | None = None,
        term_agreement_repository: (
            TermAgreementRepository | None
        ) = None,
    ) -> None:
        self._term_repository = (
            term_repository or TermRepository()
        )
        self._term_agreement_repository = (
            term_agreement_repository
            or TermAgreementRepository()
        )

    def get_active_terms(
        self,
    ) -> list[TermResponse]:
        """현재 활성 상태인 약관을 반환합니다."""

        terms = self._term_repository.get_active_terms()

        return [
            TermResponse(
                term_code=term.term_code,
                title=term.title,
                required=term.required,
                version=term.version,
                content=term.content,
                effective_at=term.effective_at,
            )
            for term in terms
        ]

    def save_agreements(
        self,
        *,
        user_id: str,
        request: TermAgreementsRequest,
    ) -> TermAgreementsResponse:
        """사용자의 약관 동의를 검증하고 저장합니다."""

        active_terms = (
            self._term_repository.get_active_terms()
        )

        active_by_code = {
            term.term_code: term
            for term in active_terms
        }

        request_by_code = {
            agreement.term_code: agreement
            for agreement in request.agreements
        }

        self._validate_required_agreements(
            active_terms=active_terms,
            request_by_code=request_by_code,
        )

        for agreement in request.agreements:
            active_term = active_by_code.get(
                agreement.term_code
            )

            if active_term is None:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="TERM_NOT_ACTIVE",
                    message="현재 동의할 수 없는 약관입니다.",
                )

            if agreement.version != active_term.version:
                raise AppException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="TERM_VERSION_MISMATCH",
                    message=(
                        "현재 약관 버전과 "
                        "요청한 버전이 일치하지 않습니다."
                    ),
                )

        now = datetime.now(timezone.utc)

        documents: dict[
            TermCode,
            TermAgreementDocument,
        ] = {}

        responses: list[
            TermAgreementResponse
        ] = []

        for agreement in request.agreements:
            agreed_at = (
                now
                if agreement.agreed
                else None
            )

            documents[agreement.term_code] = (
                TermAgreementDocument(
                    version=agreement.version,
                    agreed=agreement.agreed,
                    agreed_at=agreed_at,
                    updated_at=now,
                )
            )

            responses.append(
                TermAgreementResponse(
                    term_code=agreement.term_code,
                    version=agreement.version,
                    agreed=agreement.agreed,
                    agreed_at=agreed_at,
                )
            )

        self._term_agreement_repository.save_all(
            user_id=user_id,
            agreements=documents,
        )

        return TermAgreementsResponse(
            agreements=responses,
        )

    @staticmethod
    def _validate_required_agreements(
        *,
        active_terms,
        request_by_code,
    ) -> None:
        """현재 필수 약관이 모두 동의되었는지 확인합니다."""

        for term in active_terms:
            if not term.required:
                continue

            agreement = request_by_code.get(
                term.term_code
            )

            if (
                agreement is None
                or not agreement.agreed
            ):
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="REQUIRED_TERM_NOT_AGREED",
                    message=(
                        "필수 약관에 모두 "
                        "동의해야 합니다."
                    ),
                )
