from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.repositories.term_repository import TermRepository
from app.schemas.term import TermCode, TermDocument


KST = timezone(timedelta(hours=9))

EFFECTIVE_AT = datetime(
    2026,
    8,
    1,
    0,
    0,
    tzinfo=KST,
)


TERMS: dict[str, TermDocument] = {
    "TERMS_OF_SERVICE_1.0": TermDocument(
        term_code=TermCode.TERMS_OF_SERVICE,
        title="서비스 이용약관",
        required=True,
        version="1.0",
        content=(
            "[개발·스테이징 검증용] "
            "서비스 이용약관 전문은 출시 전 "
            "검토된 최종 문안으로 교체해야 합니다."
        ),
        effective_at=EFFECTIVE_AT,
        active=True,
    ),
    "PRIVACY_POLICY_1.0": TermDocument(
        term_code=TermCode.PRIVACY_POLICY,
        title="개인정보 수집·이용 동의",
        required=True,
        version="1.0",
        content=(
            "[개발·스테이징 검증용] "
            "개인정보 처리 관련 전문은 출시 전 "
            "검토된 최종 문안으로 교체해야 합니다."
        ),
        effective_at=EFFECTIVE_AT,
        active=True,
    ),
    "LOCATION_BASED_SERVICE_1.0": TermDocument(
        term_code=TermCode.LOCATION_BASED_SERVICE,
        title="위치기반 서비스 이용 동의",
        required=True,
        version="1.0",
        content=(
            "[개발·스테이징 검증용] "
            "위치기반 서비스 약관 전문은 출시 전 "
            "검토된 최종 문안으로 교체해야 합니다."
        ),
        effective_at=EFFECTIVE_AT,
        active=True,
    ),
    "MARKETING_1.0": TermDocument(
        term_code=TermCode.MARKETING,
        title="홍보 및 마케팅 이용 동의",
        required=False,
        version="1.0",
        content=(
            "[개발·스테이징 검증용] "
            "마케팅 수신 동의 전문은 출시 전 "
            "검토된 최종 문안으로 교체해야 합니다."
        ),
        effective_at=EFFECTIVE_AT,
        active=True,
    ),
}


def seed_terms() -> None:
    if settings.app_env.lower() in {
        "production",
        "prod",
    }:
        raise RuntimeError(
            "검토되지 않은 개발용 약관을 "
            "production에 저장할 수 없습니다."
        )

    repository = TermRepository()

    for term_id, term in TERMS.items():
        repository.set_term(
            term_id,
            term,
        )

        print(
            f"[저장 완료] terms/{term_id}: "
            f"{term.title}"
        )

    print(
        f"\n총 {len(TERMS)}개 약관 데이터 저장 완료"
    )


if __name__ == "__main__":
    seed_terms()
