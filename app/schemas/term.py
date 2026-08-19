from enum import Enum

from pydantic import (
    AwareDatetime,
    Field,
    model_validator,
)

from app.schemas.base import ApiModel


class TermCode(str, Enum):
    """서비스에서 사용하는 약관 코드."""

    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    PRIVACY_POLICY = "PRIVACY_POLICY"
    LOCATION_BASED_SERVICE = "LOCATION_BASED_SERVICE"
    MARKETING = "MARKETING"


class TermDocument(ApiModel):
    """Firestore terms 문서."""

    term_code: TermCode

    title: str = Field(
        min_length=1,
        max_length=100,
    )

    required: bool

    version: str = Field(
        min_length=1,
        max_length=30,
    )

    content: str = Field(
        min_length=1,
    )

    effective_at: AwareDatetime

    active: bool = True


class TermRecord(TermDocument):
    """Firestore 문서 ID가 포함된 약관."""

    term_id: str


class TermResponse(ApiModel):
    """약관 조회 API 응답."""

    term_code: TermCode

    title: str

    required: bool

    version: str

    content: str

    effective_at: AwareDatetime


class TermAgreementItemRequest(ApiModel):
    """사용자 약관 동의 항목."""

    term_code: TermCode

    version: str = Field(
        min_length=1,
        max_length=30,
    )

    agreed: bool


class TermAgreementsRequest(ApiModel):
    """사용자 약관 동의 저장 요청."""

    agreements: list[TermAgreementItemRequest] = Field(
        min_length=1,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_unique_term_codes(
        self,
    ) -> "TermAgreementsRequest":
        term_codes = [
            agreement.term_code
            for agreement in self.agreements
        ]

        if len(term_codes) != len(set(term_codes)):
            raise ValueError(
                "동일한 약관을 중복해서 전달할 수 없습니다."
            )

        return self


class TermAgreementDocument(ApiModel):
    """사용자별 약관 동의 Firestore 문서."""

    version: str = Field(
        min_length=1,
        max_length=30,
    )

    agreed: bool

    agreed_at: AwareDatetime | None = None

    updated_at: AwareDatetime


class TermAgreementRecord(TermAgreementDocument):
    """약관 코드가 포함된 사용자 동의 기록."""

    term_code: TermCode


class TermAgreementResponse(ApiModel):
    """약관 동의 저장 결과."""

    term_code: TermCode

    version: str

    agreed: bool

    agreed_at: AwareDatetime | None


class TermAgreementsResponse(ApiModel):
    agreements: list[TermAgreementResponse]
