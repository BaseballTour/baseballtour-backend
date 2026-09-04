from dataclasses import dataclass
from enum import Enum

from app.models.place import PlaceCategory


class TourFilterId(str, Enum):
    RESTAURANT = "RESTAURANT"
    CAFE = "CAFE"
    ACTIVITY = "ACTIVITY"
    TOURISM = "TOURISM"
    FESTIVAL = "FESTIVAL"
    EXHIBITION = "EXHIBITION"
    SHOPPING = "SHOPPING"

    KOREAN = "KOREAN"
    CHINESE = "CHINESE"
    JAPANESE = "JAPANESE"
    WESTERN = "WESTERN"
    GIMBAP_SNACK = "GIMBAP_SNACK"
    CHICKEN = "CHICKEN"
    PIZZA_FAST_FOOD = "PIZZA_FAST_FOOD"
    BAKERY = "BAKERY"
    BAR_PUB = "BAR_PUB"
    DRAFT_BEER = "DRAFT_BEER"
    TRADITIONAL_LIQUOR = "TRADITIONAL_LIQUOR"
    CAFE_ONLY = "CAFE_ONLY"
    TEA_HOUSE = "TEA_HOUSE"
    OTHER_BEVERAGE = "OTHER_BEVERAGE"

    SPORTS_CENTER = "SPORTS_CENTER"
    WATER_PARK = "WATER_PARK"
    ZOO = "ZOO"
    AQUARIUM = "AQUARIUM"
    OBSERVATORY = "OBSERVATORY"
    TRAIL = "TRAIL"
    INLINE_SKATING = "INLINE_SKATING"
    KART = "KART"
    GOLF = "GOLF"
    HORSE_RACING = "HORSE_RACING"
    HORSE_RIDING = "HORSE_RIDING"
    SKI_SNOWBOARD = "SKI_SNOWBOARD"
    ICE_SKATING = "ICE_SKATING"
    SLEDDING = "SLEDDING"
    SHOOTING_RANGE = "SHOOTING_RANGE"
    ROCK_CLIMBING = "ROCK_CLIMBING"
    BUNGEE_JUMPING = "BUNGEE_JUMPING"
    JET_SKI = "JET_SKI"
    KAYAK = "KAYAK"
    YACHT = "YACHT"
    SNORKELING = "SNORKELING"
    FISHING = "FISHING"
    WATER_BICYCLE = "WATER_BICYCLE"
    SKYDIVING = "SKYDIVING"
    PARAGLIDING = "PARAGLIDING"
    HOT_AIR_BALLOON = "HOT_AIR_BALLOON"

    TRADITIONAL_EXPERIENCE = "TRADITIONAL_EXPERIENCE"
    CRAFT_EXPERIENCE = "CRAFT_EXPERIENCE"
    RURAL_EXPERIENCE = "RURAL_EXPERIENCE"
    TEMPLE_STAY = "TEMPLE_STAY"
    WELLNESS = "WELLNESS"
    CRUISE = "CRUISE"
    HISTORIC_SITE = "HISTORIC_SITE"
    HISTORIC_RELIC = "HISTORIC_RELIC"
    NATURE = "NATURE"
    LANDMARK = "LANDMARK"
    PARK = "PARK"
    CULTURAL_STREET = "CULTURAL_STREET"

    CULTURAL_TOURISM_FESTIVAL = "CULTURAL_TOURISM_FESTIVAL"
    CULTURAL_ART_FESTIVAL = "CULTURAL_ART_FESTIVAL"
    LOCAL_SPECIALTY_FESTIVAL = "LOCAL_SPECIALTY_FESTIVAL"
    TRADITIONAL_HISTORY_FESTIVAL = "TRADITIONAL_HISTORY_FESTIVAL"
    ECO_NATURE_FESTIVAL = "ECO_NATURE_FESTIVAL"
    FAIR = "FAIR"
    MUSEUM = "MUSEUM"
    MEMORIAL_HALL = "MEMORIAL_HALL"
    EXHIBITION_HALL = "EXHIBITION_HALL"
    SCIENCE_MUSEUM = "SCIENCE_MUSEUM"
    ART_MUSEUM = "ART_MUSEUM"

    DEPARTMENT_STORE = "DEPARTMENT_STORE"
    SHOPPING_MALL = "SHOPPING_MALL"
    OUTLET = "OUTLET"
    LARGE_MART = "LARGE_MART"
    DOWNTOWN_DUTY_FREE = "DOWNTOWN_DUTY_FREE"
    CRAFT_SHOP = "CRAFT_SHOP"
    SOUVENIR = "SOUVENIR"
    MARKET = "MARKET"


@dataclass(frozen=True)
class ClassificationClause:
    lcls_system1: str
    lcls_system2: str | None = None
    lcls_system3: str | None = None


@dataclass(frozen=True)
class TourFilterDefinition:
    label: str
    group: str
    clauses: tuple[ClassificationClause, ...]
    allowed_categories: frozenset[PlaceCategory] | None = None


def _clause(code: str) -> ClassificationClause:
    if len(code) == 2:
        return ClassificationClause(code)
    if len(code) == 4:
        return ClassificationClause(code[:2], code)
    if len(code) == 8:
        return ClassificationClause(code[:2], code[:4], code)
    raise ValueError(f"지원하지 않는 TourAPI 신분류 코드입니다: {code}")


def _definition(
    label: str,
    group: str,
    *codes: str,
    categories: tuple[PlaceCategory, ...] | None = None,
) -> TourFilterDefinition:
    return TourFilterDefinition(
        label=label,
        group=group,
        clauses=tuple(_clause(code) for code in codes),
        allowed_categories=(
            frozenset(categories) if categories is not None else None
        ),
    )


FILTER_DEFINITIONS: dict[TourFilterId, TourFilterDefinition] = {
    TourFilterId.RESTAURANT: _definition(
        "음식점", "고정 카테고리", "FD",
        categories=(PlaceCategory.RESTAURANT,),
    ),
    TourFilterId.CAFE: _definition("카페", "고정 카테고리", "FD05"),
    TourFilterId.ACTIVITY: _definition(
        "액티비티", "고정 카테고리", "LS", "VE100200", "VE020200",
        "VE020300", "VE020400", "VE020500", "VE040300",
    ),
    TourFilterId.TOURISM: _definition(
        "관광지", "고정 카테고리", "EX", "HS", "NA", "VE01", "VE03",
        "VE040100",
    ),
    TourFilterId.FESTIVAL: _definition(
        "축제", "고정 카테고리", "EV01", "EV030100"
    ),
    TourFilterId.EXHIBITION: _definition(
        "전시", "고정 카테고리", "VE07"
    ),
    TourFilterId.SHOPPING: _definition(
        "쇼핑", "고정 카테고리", "SH"
    ),
}


_LEAF_FILTERS = {
    TourFilterId.KOREAN: ("한식", "음식", ("FD01",)),
    TourFilterId.CHINESE: ("중식", "음식", ("FD020100",)),
    TourFilterId.JAPANESE: ("일식", "음식", ("FD020200",)),
    TourFilterId.WESTERN: ("양식", "음식", ("FD020300",)),
    TourFilterId.GIMBAP_SNACK: ("김밥 분식", "음식", ("FD030400",)),
    TourFilterId.CHICKEN: ("치킨", "음식", ("FD030300",)),
    TourFilterId.PIZZA_FAST_FOOD: ("피자·패스트푸드", "음식", ("FD030200",)),
    TourFilterId.BAKERY: ("제과", "음식", ("FD030100",)),
    TourFilterId.BAR_PUB: ("바/펍", "음식", ("FD040100",)),
    TourFilterId.DRAFT_BEER: ("생맥주전문점", "음식", ("FD040200",)),
    TourFilterId.TRADITIONAL_LIQUOR: ("전통주", "음식", ("FD040400",)),
    TourFilterId.CAFE_ONLY: ("카페", "카페", ("FD050100",)),
    TourFilterId.TEA_HOUSE: ("찻집", "카페", ("FD050200",)),
    TourFilterId.OTHER_BEVERAGE: ("기타음료", "카페", ("FD050300",)),
    TourFilterId.SPORTS_CENTER: ("스포츠센터", "액티비티", ("VE100200",)),
    TourFilterId.WATER_PARK: ("워터파크", "액티비티", ("VE020200",)),
    TourFilterId.ZOO: ("동물원", "액티비티", ("VE020300",)),
    TourFilterId.AQUARIUM: ("수족관/아쿠아리움", "액티비티", ("VE020400",)),
    TourFilterId.OBSERVATORY: ("천문대", "액티비티", ("VE020500",)),
    TourFilterId.TRAIL: ("둘레길", "액티비티", ("VE040300",)),
    TourFilterId.INLINE_SKATING: ("인라인", "액티비티", ("LS010100",)),
    TourFilterId.KART: ("카트", "액티비티", ("LS010300",)),
    TourFilterId.GOLF: ("골프", "액티비티", ("LS010400",)),
    TourFilterId.HORSE_RACING: ("경마", "액티비티", ("LS010500",)),
    TourFilterId.HORSE_RIDING: ("승마", "액티비티", ("LS010700",)),
    TourFilterId.SKI_SNOWBOARD: ("스키/스노우보드", "액티비티", ("LS010800",)),
    TourFilterId.ICE_SKATING: ("스케이트", "액티비티", ("LS010900",)),
    TourFilterId.SLEDDING: ("썰매장", "액티비티", ("LS011000",)),
    TourFilterId.SHOOTING_RANGE: ("사격장", "액티비티", ("LS011200",)),
    TourFilterId.ROCK_CLIMBING: ("암벽등반", "액티비티", ("LS011300",)),
    TourFilterId.BUNGEE_JUMPING: ("번지점프", "액티비티", ("LS011800",)),
    TourFilterId.JET_SKI: ("제트스키", "액티비티", ("LS020100",)),
    TourFilterId.KAYAK: ("카약", "액티비티", ("LS020200",)),
    TourFilterId.YACHT: ("요트", "액티비티", ("LS020300",)),
    TourFilterId.SNORKELING: ("스노쿨링", "액티비티", ("LS020400",)),
    TourFilterId.FISHING: ("낚시", "액티비티", ("LS020500", "LS020600")),
    TourFilterId.WATER_BICYCLE: ("수상자전거", "액티비티", ("LS021000",)),
    TourFilterId.SKYDIVING: ("스카이다이빙", "액티비티", ("LS030100",)),
    TourFilterId.PARAGLIDING: ("패러글라이딩", "액티비티", ("LS030300",)),
    TourFilterId.HOT_AIR_BALLOON: ("열기구", "액티비티", ("LS030400",)),
    TourFilterId.TRADITIONAL_EXPERIENCE: ("전통체험", "관광지", ("EX01",)),
    TourFilterId.CRAFT_EXPERIENCE: ("공예체험", "관광지", ("EX02",)),
    TourFilterId.RURAL_EXPERIENCE: ("농어촌체험", "관광지", ("EX03",)),
    TourFilterId.TEMPLE_STAY: ("템플스테이", "관광지", ("EX040100",)),
    TourFilterId.WELLNESS: ("웰니스관광", "관광지", ("EX05",)),
    TourFilterId.CRUISE: ("유람선", "관광지", ("EX070100",)),
    TourFilterId.HISTORIC_SITE: ("역사 유적지", "관광지", ("HS01",)),
    TourFilterId.HISTORIC_RELIC: ("역사 유물", "관광지", ("HS02",)),
    TourFilterId.NATURE: ("자연관광", "관광지", ("NA",)),
    TourFilterId.LANDMARK: ("랜드마크", "관광지", ("VE01",)),
    TourFilterId.PARK: ("공원", "관광지", ("VE03",)),
    TourFilterId.CULTURAL_STREET: ("문화거리", "관광지", ("VE040100",)),
    TourFilterId.CULTURAL_TOURISM_FESTIVAL: ("문화관광", "축제", ("EV010100",)),
    TourFilterId.CULTURAL_ART_FESTIVAL: ("문화예술", "축제", ("EV010200",)),
    TourFilterId.LOCAL_SPECIALTY_FESTIVAL: ("지역특산물", "축제", ("EV010300",)),
    TourFilterId.TRADITIONAL_HISTORY_FESTIVAL: ("전통역사", "축제", ("EV010400",)),
    TourFilterId.ECO_NATURE_FESTIVAL: ("생태자연", "축제", ("EV010500",)),
    TourFilterId.FAIR: ("전시회", "축제", ("EV030100",)),
    TourFilterId.MUSEUM: ("박물관", "전시", ("VE070100",)),
    TourFilterId.MEMORIAL_HALL: ("기념관", "전시", ("VE070200",)),
    TourFilterId.EXHIBITION_HALL: ("전시관", "전시", ("VE070300",)),
    TourFilterId.SCIENCE_MUSEUM: ("과학관", "전시", ("VE070500",)),
    TourFilterId.ART_MUSEUM: ("미술관", "전시", ("VE070600",)),
    TourFilterId.DEPARTMENT_STORE: ("백화점", "쇼핑", ("SH010100",)),
    TourFilterId.SHOPPING_MALL: ("쇼핑몰", "쇼핑", ("SH020100",)),
    TourFilterId.OUTLET: ("아울렛", "쇼핑", ("SH020200",)),
    TourFilterId.LARGE_MART: ("대형마트", "쇼핑", ("SH030100",)),
    TourFilterId.DOWNTOWN_DUTY_FREE: ("면세점", "쇼핑", ("SH040200",)),
    TourFilterId.CRAFT_SHOP: ("공방", "쇼핑", ("SH050100",)),
    TourFilterId.SOUVENIR: ("기념품", "쇼핑", ("SH050300",)),
    TourFilterId.MARKET: ("시장", "쇼핑", ("SH06",)),
}

FILTER_DEFINITIONS.update(
    {
        filter_id: _definition(label, group, *codes)
        for filter_id, (label, group, codes) in _LEAF_FILTERS.items()
    }
)


def get_filter_definition(filter_id: TourFilterId) -> TourFilterDefinition:
    return FILTER_DEFINITIONS[filter_id]
