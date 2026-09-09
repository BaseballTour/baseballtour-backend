"""선수 추천 장소 문서에 검수된 선수 포지션을 일괄 반영합니다."""

import argparse
from datetime import datetime, timezone

from app.core.firebase import get_firestore_client
from app.schemas.player_pick import PlayerPosition


P = PlayerPosition.PITCHER
C = PlayerPosition.CATCHER
I = PlayerPosition.INFIELDER
O = PlayerPosition.OUTFIELDER
COACH = PlayerPosition.COACH
STAFF = PlayerPosition.STAFF
GROUP = PlayerPosition.TEAM_GROUP


POSITIONS: dict[tuple[str, str], PlayerPosition] = {
    # NC 다이노스
    **{("changwon", name): P for name in (
        "구창모", "김시훈", "김진호", "송명기", "신민혁", "이용찬", "이재학", "하준영"
    )},
    **{("changwon", name): I for name in ("노진혁", "오영수", "오태양")},
    **{("changwon", name): O for name in ("마티니", "손아섭")},
    # 삼성 라이온즈
    **{("daegu", name): P for name in (
        "김대우", "이승민", "좌승현", "최지광", "최채흥"
    )},
    **{("daegu", name): I for name in ("김지찬", "류지혁")},
    **{("daegu", name): O for name in ("김현준", "윤정빈")},
    ("daegu", "이병헌"): C,
    ("daegu", "박찬도 코치"): COACH,
    # 한화 이글스
    **{("daejeon", name): P for name in (
        "김서현", "김종수", "류현진", "문동주", "박상원", "정우주", "주현상", "폰세"
    )},
    **{("daejeon", name): I for name in (
        "김태연", "문현빈", "이도윤", "하주석", "채은성"
    )},
    **{("daejeon", name): O for name in ("이원석", "이진영", "최인호")},
    ("daejeon", "윤규진"): COACH,
    # 키움 히어로즈
    ("gocheok", "원성준"): O,
    # KIA 타이거즈
    **{("gwangju", name): P for name in (
        "김건국", "동하", "송후섭", "양현종", "영철", "유승철", "이태규", "지민"
    )},
    **{("gwangju", name): O for name in ("김석환", "김호령", "나성범")},
    ("gwangju", "도현"): I,
    ("gwangju", "한승택"): C,
    # SSG 랜더스
    **{("incheon", name): P for name in ("김광현", "김택형", "백승건", "이건욱")},
    **{("incheon", name): I for name in (
        "고명준", "박성한", "안상현", "오태곤", "전의산", "최경모", "최정"
    )},
    **{("incheon", name): O for name in ("류효승", "최지훈", "한유섬")},
    ("incheon", "조형우"): C,
    **{("incheon", name): GROUP for name in (
        "선수단 공통 추천", "야수조", "포수조", "퓨처스 야수조"
    )},
    # LG 트윈스·두산 베어스
    **{("jamsil", name): P for name in (
        "김영우", "김윤식", "김진수", "이정용", "임찬규", "장현식", "이현승", "장원준"
    )},
    **{("jamsil", name): I for name in (
        "구본혁", "문보경", "문정빈", "송찬의", "신민재", "이영빈", "천성호"
    )},
    **{("jamsil", name): O for name in ("문성주", "박해민")},
    ("jamsil", "이주헌"): C,
    **{("jamsil", name): STAFF for name in ("준혁", "석우")},
    **{("jamsil", name): GROUP for name in ("LG 전체 선수", "두산 베어스 선수단")},
    # 롯데 자이언츠
    **{("sajik", name): P for name in (
        "구승민", "김진욱", "심재민", "진승현", "최준용"
    )},
    **{("sajik", name): C for name in ("손성빈", "유강남", "이정훈", "정보근")},
    **{("sajik", name): I for name in ("고승민", "노진혁", "이학주", "한동희")},
    **{("sajik", name): O for name in ("윤동희", "전준우", "황성빈")},
    # KT 위즈
    **{("suwon", name): P for name in ("김민", "김민수", "벤자민", "주권")},
    **{("suwon", name): I for name in ("강백호", "신본기")},
    ("suwon", "장성우"): C,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    collection = get_firestore_client().collection("playerPlaceRecommendations")
    updated = 0
    unresolved: set[tuple[str, str]] = set()

    for snapshot in collection.stream():
        data = snapshot.to_dict() or {}
        key = (str(data.get("stadiumId") or ""), str(data.get("playerName") or ""))
        position = POSITIONS.get(key)
        if position is None:
            unresolved.add(key)
            continue
        if args.write:
            snapshot.reference.update(
                {
                    "playerPosition": position.value,
                    "updatedAt": datetime.now(timezone.utc),
                }
            )
        updated += 1
        print(f"[{'저장' if args.write else 'DRY-RUN'}] {snapshot.id} / {key[1]} / {position.value}")

    print(f"완료: 반영 대상 {updated}, 미확정 이름 {len(unresolved)}")
    for stadium_id, player_name in sorted(unresolved):
        print(f"[미확정] {stadium_id} / {player_name}")


if __name__ == "__main__":
    main()
