from datetime import datetime, timezone

from app.core.config import settings
from app.repositories.stadium_repository import StadiumRepository
from app.schemas.stadium import StadiumDocument


def build_stadiums() -> dict[str, StadiumDocument]:
    """개발 환경에서 사용할 KBO 구장 초기 데이터를 생성합니다."""

    now = datetime.now(timezone.utc)

    return {
        "jamsil": StadiumDocument(
            name="잠실야구장",
            address="서울특별시 송파구 올림픽로 25",
            latitude=37.5122,
            longitude=127.0719,
            region="서울",
            created_at=now,
            updated_at=now,
        ),
        "gocheok": StadiumDocument(
            name="고척스카이돔",
            address="서울특별시 구로구 경인로 430",
            latitude=37.4982,
            longitude=126.8671,
            region="서울",
            created_at=now,
            updated_at=now,
        ),
        "incheon": StadiumDocument(
            name="인천 SSG 랜더스필드",
            address="인천광역시 미추홀구 매소홀로 618",
            latitude=37.4370,
            longitude=126.6932,
            region="인천",
            created_at=now,
            updated_at=now,
        ),
        "suwon": StadiumDocument(
            name="수원 KT 위즈 파크",
            address="경기도 수원시 장안구 경수대로 893",
            latitude=37.2997,
            longitude=127.0097,
            region="경기",
            created_at=now,
            updated_at=now,
        ),
        "daejeon": StadiumDocument(
            name="대전 한화생명 볼파크",
            address="대전광역시 중구 대종로 373",
            latitude=36.3172,
            longitude=127.4292,
            region="대전",
            created_at=now,
            updated_at=now,
        ),
        "gwangju": StadiumDocument(
            name="광주-KIA 챔피언스 필드",
            address="광주광역시 북구 서림로 10",
            latitude=35.1681,
            longitude=126.8888,
            region="광주",
            created_at=now,
            updated_at=now,
        ),
        "daegu": StadiumDocument(
            name="대구 삼성 라이온즈 파크",
            address="대구광역시 수성구 야구전설로 1",
            latitude=35.8411,
            longitude=128.6817,
            region="대구",
            created_at=now,
            updated_at=now,
        ),
        "sajik": StadiumDocument(
            name="사직야구장",
            address="부산광역시 동래구 사직로 45",
            latitude=35.1940,
            longitude=129.0615,
            region="부산",
            created_at=now,
            updated_at=now,
        ),
        "changwon": StadiumDocument(
            name="창원NC파크",
            address="경상남도 창원시 마산회원구 삼호로 63",
            latitude=35.2225,
            longitude=128.5822,
            region="경남",
            created_at=now,
            updated_at=now,
        ),
    }


def seed_stadiums() -> None:
    """Firestore stadiums Collection에 구장 데이터를 저장합니다."""

    if settings.app_env.lower() == "production":
        raise RuntimeError(
            "운영 환경에서는 개발용 구장 Seed를 실행할 수 없습니다."
        )

    repository = StadiumRepository()
    stadiums = build_stadiums()

    for stadium_id, stadium in stadiums.items():
        repository.set_stadium(
            stadium_id,
            stadium,
        )
        print(
            f"[저장 완료] stadiums/{stadium_id}: "
            f"{stadium.name}"
        )

    print(
        f"\n총 {len(stadiums)}개 구장 데이터 저장 완료"
    )


if __name__ == "__main__":
    seed_stadiums()
