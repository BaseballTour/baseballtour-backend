from uuid import uuid4


def new_prefixed_id(prefix: str) -> str:
    """내부 생성 문서에 사용할 접두사 기반 ID를 반환합니다."""

    normalized_prefix = prefix.strip().rstrip("_")
    if not normalized_prefix:
        raise ValueError("ID 접두사는 비어 있을 수 없습니다.")

    return f"{normalized_prefix}_{uuid4().hex}"
