from app.repositories.team_repository import (
    TeamRepository,
)
from app.schemas.team import TeamDocument


def make_team(
    *,
    team_id: str,
    name: str,
    short_name: str,
    home_region: str,
    stadium_id: str,
) -> TeamDocument:
    return TeamDocument(
        name=name,
        short_name=short_name,
        logo_url=None,
        logo_storage_path=None,
        home_region=home_region,
        stadium_id=stadium_id,
    )


TEAMS: dict[str, TeamDocument] = {
    "doosan": make_team(
        team_id="doosan",
        name="두산 베어스",
        short_name="두산",
        home_region="서울",
        stadium_id="jamsil",
    ),
    "lg": make_team(
        team_id="lg",
        name="LG 트윈스",
        short_name="LG",
        home_region="서울",
        stadium_id="jamsil",
    ),
    "kiwoom": make_team(
        team_id="kiwoom",
        name="키움 히어로즈",
        short_name="키움",
        home_region="서울",
        stadium_id="gocheok",
    ),
    "ssg": make_team(
        team_id="ssg",
        name="SSG 랜더스",
        short_name="SSG",
        home_region="인천",
        stadium_id="incheon",
    ),
    "kt": make_team(
        team_id="kt",
        name="KT 위즈",
        short_name="KT",
        home_region="수원",
        stadium_id="suwon",
    ),
    "hanwha": make_team(
        team_id="hanwha",
        name="한화 이글스",
        short_name="한화",
        home_region="대전",
        stadium_id="daejeon",
    ),
    "kia": make_team(
        team_id="kia",
        name="KIA 타이거즈",
        short_name="KIA",
        home_region="광주",
        stadium_id="gwangju",
    ),
    "samsung": make_team(
        team_id="samsung",
        name="삼성 라이온즈",
        short_name="삼성",
        home_region="대구",
        stadium_id="daegu",
    ),
    "lotte": make_team(
        team_id="lotte",
        name="롯데 자이언츠",
        short_name="롯데",
        home_region="부산",
        stadium_id="sajik",
    ),
    "nc": make_team(
        team_id="nc",
        name="NC 다이노스",
        short_name="NC",
        home_region="창원",
        stadium_id="changwon",
    ),
}


def seed_teams() -> None:
    repository = TeamRepository()

    for team_id, team in TEAMS.items():
        repository.set_team(
            team_id,
            team,
        )

        print(
            f"[저장 완료] teams/{team_id}: "
            f"{team.name}"
        )

    print(
        f"\n총 {len(TEAMS)}개 "
        "구단 데이터 저장 완료"
    )


if __name__ == "__main__":
    seed_teams()
