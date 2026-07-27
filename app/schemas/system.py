from typing import Literal

from pydantic import BaseModel, Field


class RootData(BaseModel):
    name: str = Field(
        description="애플리케이션 이름",
    )
    environment: str = Field(
        description="현재 실행 환경",
    )
    status: Literal["running"] = Field(
        default="running",
        description="애플리케이션 실행 상태",
    )


class HealthData(BaseModel):
    status: Literal["healthy"] = Field(
        default="healthy",
        description="서버 상태",
    )
