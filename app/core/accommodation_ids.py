from hashlib import sha256
import re


ACCOMMODATION_ID_PREFIX = "accommodation_"
ACCOMMODATION_ID_PATTERN = re.compile(
    r"^accommodation_(?:kakao_[0-9]+|map_[0-9a-f]{16})$"
)


def build_kakao_accommodation_id(kakao_place_id: str) -> str:
    normalized = str(kakao_place_id).strip()
    if not normalized.isdigit():
        raise ValueError("Kakao 숙소 ID는 숫자여야 합니다.")
    return f"{ACCOMMODATION_ID_PREFIX}kakao_{normalized}"


def build_map_accommodation_id(
    *,
    latitude: float,
    longitude: float,
    address: str,
) -> str:
    identity = f"{latitude:.6f}|{longitude:.6f}|{address.strip()}"
    digest = sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{ACCOMMODATION_ID_PREFIX}map_{digest}"


def is_valid_accommodation_id(value: str | None) -> bool:
    return bool(value and ACCOMMODATION_ID_PATTERN.fullmatch(value))
