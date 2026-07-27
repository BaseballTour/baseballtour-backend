from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.client import Client

from app.core.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def initialize_firebase() -> firebase_admin.App:
    """Firebase Admin SDK를 한 번만 초기화한다."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        credentials_path = Path(settings.firebase_credentials_path)

        if not credentials_path.is_absolute():
            credentials_path = PROJECT_ROOT / credentials_path

        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Firebase 서비스 계정 키를 찾을 수 없습니다: {credentials_path}"
            )

        firebase_credentials = credentials.Certificate(
            str(credentials_path)
        )

        return firebase_admin.initialize_app(firebase_credentials)


def get_firestore_client() -> Client:
    """초기화된 Firebase 앱을 사용하는 Firestore 클라이언트를 반환한다."""
    firebase_app = initialize_firebase()
    return firestore.client(app=firebase_app)
