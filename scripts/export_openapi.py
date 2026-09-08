"""현재 FastAPI 계약을 정적 OpenAPI 문서로 내보냅니다."""

import json
from pathlib import Path

from app.main import app


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "openapi-v1.0.json"


def main() -> None:
    OUTPUT_PATH.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI 문서 갱신: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
