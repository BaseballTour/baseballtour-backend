"""선수 추천 근거 링크 전수 검수 결과를 Firestore에 반영합니다.

기본은 dry-run이며 ``--write``를 지정해야 실제 문서를 변경합니다.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone

from app.repositories.player_pick_repository import PlayerPickRepository


Identity = tuple[str, str, str]


@dataclass(frozen=True)
class EvidenceReplacement:
    url: str
    title: str
    publisher: str


LG_VIDEO = EvidenceReplacement(
    url="https://www.youtube.com/watch?v=2k_k7RhWe9I",
    title="아아📢ˎˊ˗ 잠실 마지막 올스타전 오시는 10개 구단 팬 여러분! 잠실 맛집 여기 있습니다🍴[LP]",
    publisher="LGTWINSTV",
)
KT_NC_VIDEO = EvidenceReplacement(
    url="https://www.youtube.com/watch?v=c3ZJRS1RHpk",
    title="진짜 꼭 가서 먹어보세요! 야구 선수들이 추천하는 맛집은?🍴 (with. NC다이노스) [호기심천당]",
    publisher="위즈TV",
)
DOOSAN_ARTICLE = EvidenceReplacement(
    url="https://www.esquirekorea.co.kr/article/68627",
    title="두산 베어스 선수들이 즐겨 찾는 맛집 4",
    publisher="에스콰이어 코리아",
)
KIA_ARTICLE = EvidenceReplacement(
    url=(
        "https://news.jeonnam-gwangju.go.kr/gallery.es?act=view&bid=0009"
        "&list_no=6903&mid=a50101000000&obid=0009&tab_type=data"
    ),
    title="먹산이 이 콘텐츠를 꼭 보면 좋겠다",
    publisher="전남광주통합특별시 온라인뉴스",
)


REPLACEMENTS: dict[Identity, EvidenceReplacement] = {
    ("gwangju", "양현종", "당산나무집 본점"): KIA_ARTICLE,
    ("jamsil", "두산 선수단", "삼미집 청담본점"): DOOSAN_ARTICLE,
    ("jamsil", "두산 선수단", "신천대도갈비"): DOOSAN_ARTICLE,
    ("jamsil", "두산 선수단", "일번지육개장"): DOOSAN_ARTICLE,
    ("jamsil", "구본혁", "장어의꿈"): LG_VIDEO,
    ("jamsil", "이정용", "마쯔가제"): LG_VIDEO,
    ("jamsil", "이정용", "초필살돼지구이 방이점"): LG_VIDEO,
    ("suwon", "김민", "가보정 1관"): KT_NC_VIDEO,
    ("suwon", "신본기", "오늘의초밥 본점"): KT_NC_VIDEO,
}


DISPUTED: set[Identity] = {
    ("changwon", "구창모", "돈92 마산본점"),
    ("changwon", "구창모", "라온하제"),
    ("changwon", "김시훈", "창원NC파크 구내식당"),
    ("changwon", "김진호", "토도스"),
    ("changwon", "노진혁", "스시혼"),
    ("changwon", "마티니", "토도스"),
    ("changwon", "송명기", "일레븐어클락 본점"),
    ("changwon", "오영수", "스시혼"),
    ("changwon", "신민혁", "사야카츠"),
    ("changwon", "오태양", "김형제고기의철학 창원상남점"),
    ("changwon", "오태양", "석꾼 본점"),
    ("changwon", "오태양", "조선의한우 창원 본점"),
    ("changwon", "하준영", "동양카츠 창원상남본점"),
    ("changwon", "하준영", "석정원숯불갈비 본점"),
    ("changwon", "하준영", "어린양양꼬치"),
    ("daejeon", "정우주", "달빛식탁"),
    ("gocheok", "원성준", "산아래"),
    ("incheon", "박성한", "스테이션"),
    ("incheon", "최정", "스테이션"),
    ("incheon", "최지훈", "스테이션"),
    ("incheon", "오태곤", "그릴나이트"),
    ("incheon", "한유섬", "그릴나이트"),
    ("jamsil", "두산 베어스 선수단", "부농정육식당"),
    ("sajik", "정보근", "화로우 명지국제신도시점"),
}


DELETE_DOCUMENT_IDS = {
    # 모든 필수 필드가 비어 있는 손상 문서
    "player_pick_32fdc44b129ba778119166ef",
}
DELETE_IDENTITIES: set[Identity] = {
    # 선수 추천이 아니라 고척돔 일반 인기 먹거리
    ("gocheok", "고척돔 명물", "쉬림프쉐프"),
}


def _identity(data: dict) -> Identity:
    return (
        str(data.get("stadiumId") or ""),
        str(data.get("playerName") or ""),
        str(data.get("placeName") or ""),
    )


def remediate(*, write: bool) -> tuple[int, int, int, int]:
    repository = PlayerPickRepository()
    replaced = disputed = deleted = untouched = 0
    now = datetime.now(timezone.utc)

    for snapshot in repository._collection.stream():
        data = snapshot.to_dict() or {}
        identity = _identity(data)

        if snapshot.id in DELETE_DOCUMENT_IDS or identity in DELETE_IDENTITIES:
            print(f"[{'삭제' if write else 'DRY-RUN 삭제'}] {snapshot.id} / {identity}")
            if write:
                snapshot.reference.delete()
            deleted += 1
            continue

        replacement = REPLACEMENTS.get(identity)
        if replacement is not None:
            update = {
                "recommendationEvidenceStatus": "VERIFIED",
                "recommendationSourceUrl": replacement.url,
                "recommendationSourceTitle": replacement.title,
                "recommendationSourcePublisher": replacement.publisher,
                "recommendationVerifiedAt": now,
                "updatedAt": now,
            }
            print(
                f"[{'교체' if write else 'DRY-RUN 교체'}] "
                f"{snapshot.id} / {identity} / {replacement.url}"
            )
            if write:
                snapshot.reference.update(update)
            replaced += 1
            continue

        if identity in DISPUTED:
            update = {
                "recommendationEvidenceStatus": "DISPUTED",
                "recommendationSourceUrl": None,
                "recommendationSourceTitle": None,
                "recommendationSourcePublisher": None,
                "recommendationVerifiedAt": None,
                "updatedAt": now,
            }
            print(f"[{'보류' if write else 'DRY-RUN 보류'}] {snapshot.id} / {identity}")
            if write:
                snapshot.reference.update(update)
            disputed += 1
            continue

        untouched += 1

    return replaced, disputed, deleted, untouched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    replaced, disputed, deleted, untouched = remediate(write=args.write)
    print(
        "완료: "
        f"근거 교체 {replaced}, 보류 {disputed}, 삭제 {deleted}, 유지 {untouched}"
    )


if __name__ == "__main__":
    main()
