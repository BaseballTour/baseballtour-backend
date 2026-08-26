from fastapi.testclient import TestClient

from app.api.v1.endpoints import tour as tour_endpoint
from app.external.tour_api.adapter import ClassificationPage
from app.main import app
from app.schemas.tour import TourClassification


client = TestClient(app)


def test_classifications_return_korean_names_and_codes(monkeypatch) -> None:
    async def fake_get_classification_page(**kwargs) -> ClassificationPage:
        return ClassificationPage(
            classifications=[TourClassification(
                lcls_system1="FD",
                lcls_system1_name="음식",
                lcls_system2="FD02",
                lcls_system2_name="외국식",
                lcls_system3="FD020200",
                lcls_system3_name="일식",
            )],
            next_page_token=None,
        )

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "get_classification_page",
        fake_get_classification_page,
    )
    response = client.get("/api/v1/tour/classifications")
    assert response.status_code == 200
    assert response.json()["data"][0]["lclsSystem3Name"] == "일식"
