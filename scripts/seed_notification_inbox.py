"""테스트 계정의 알림함 시드."""

import argparse
from datetime import datetime, timezone

from firebase_admin import auth
from google.api_core.exceptions import AlreadyExists

from app.core.firebase import get_firestore_client
from app.schemas.notification_inbox import NotificationDocument


NOTICES = {
    "notification_test_001": (
        "TRIP_REMINDER",
        "[테스트] 여행 일정 안내",
        "예정된 원정 여행 일정을 확인해 주세요.",
    ),
    "notification_test_002": (
        "GAME_REMINDER",
        "[테스트] 경기 일정 안내",
        "선택한 경기 일정을 확인해 주세요.",
    ),
    "notification_test_003": (
        "SYSTEM",
        "[테스트] 알림함 안내",
        "홈 화면 알림 목록의 동작을 확인하기 위한 테스트 알림입니다.",
    ),
}


def seed(user_id: str, apply: bool = False) -> None:
    client = get_firestore_client()

    if client.project != "baseballtour":
        raise RuntimeError(
            f"예상하지 않은 Firebase 프로젝트입니다: {client.project}"
        )

    # 존재하는 테스트 계정인지 확인
    auth.get_user(user_id)

    collection = (
        client.collection("users")
        .document(user_id)
        .collection("notifications")
    )

    for notification_id, (type_, title, body) in NOTICES.items():
        notification = NotificationDocument(
            type=type_,
            title=title,
            body=body,
            created_at=datetime.now(timezone.utc),
            read_at=None,
        )

        if not apply:
            print(f"[미리보기] {notification_id}: {title}")
            continue

        try:
            collection.document(notification_id).create(
                notification.model_dump(
                    by_alias=True,
                    mode="python",
                    exclude_none=False,
                )
            )
        except AlreadyExists:
            print(f"[건너뜀] {notification_id}: 이미 존재")
        else:
            print(f"[저장 완료] {notification_id}: {title}")

    if not apply:
        print("\n실제 저장하려면 --apply 옵션을 사용하세요.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    seed(args.user_id, args.apply)
