from app.repositories.team_repository import TeamRepository
from app.schemas.team import TeamDocument


TEAMS: dict[str, TeamDocument] = {
    "doosan": TeamDocument(
        name="두산 베어스",
        short_name="두산",
        logo_url="https://example.com/teams/doosan.png",
        home_region="서울",
        stadium_id="jamsil",
    ),
    "lg": TeamDocument(
        name="LG 트윈스",
        short_name="LG",
        logo_url="https://example.com/teams/lg.png",
        home_region="서울",
        stadium_id="jamsil",
    ),
    "kiwoom": TeamDocument(
        name="키움 히어로즈",
        short_name="키움",
        logo_url="https://example.com/teams/kiwoom.png",
        home_region="서울",
        stadium_id="gocheok",
    ),
    "ssg": TeamDocument(
        name="SSG 랜더스",
        short_name="SSG",
        logo_url="https://example.com/teams/ssg.png",
        home_region="인천",
        stadium_id="incheon",
    ),
    "kt": TeamDocument(
        name="KT 위즈",
        short_name="KT",
        logo_url="https://example.com/teams/kt.png",
        home_region="수원",
        stadium_id="suwon",
    ),
    "hanwha": TeamDocument(
        name="한화 이글스",
        short_name="한화",
        logo_url="https://example.com/teams/hanwha.png",
        home_region="대전",
        stadium_id="daejeon",
    ),
    "kia": TeamDocument(
        name="KIA 타이거즈",
        short_name="KIA",
        logo_url="https://example.com/teams/kia.png",
        home_region="광주",
        stadium_id="gwangju",
    ),
    "samsung": TeamDocument(
        name="삼성 라이온즈",
        short_name="삼성",
        logo_url="https://example.com/teams/samsung.png",
        home_region="대구",
        stadium_id="daegu",
    ),
    "lotte": TeamDocument(
        name="롯데 자이언츠",
        short_name="롯데",
        logo_url="https://example.com/teams/lotte.png",
        home_region="부산",
        stadium_id="sajik",
    ),
    "nc": TeamDocument(
        name="NC 다이노스",
        short_name="NC",
        logo_url="https://example.com/teams/nc.png",
        home_region="창원",
        stadium_id="changwon",
    ),
}


def seed_teams() -> None:
    repository = TeamRepository()

    for team_id, team in TEAMS.items():
        repository.set_team(team_id, team)
        print(f"[저장 완료] teams/{team_id}: {team.name}")

    print(f"\n총 {len(TEAMS)}개 구단 데이터 저장 완료")


if __name__ == "__main__":
    seed_teams()
