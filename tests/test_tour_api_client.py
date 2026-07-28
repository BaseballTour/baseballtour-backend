import pytest

from app.core.exceptions import AppException
from app.external.tour_api.client import _validate_tour_api_response


def test_tour_api_business_error_is_rejected() -> None:
    data = {
        "response": {
            "header": {
                "resultCode": "99",
                "resultMsg": "LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS",
            }
        }
    }

    with pytest.raises(AppException) as exc_info:
        _validate_tour_api_response(data)

    assert exc_info.value.code == "TOUR_API_FAILED"
    assert exc_info.value.status_code == 502


def test_invalid_response_shape_is_rejected() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_tour_api_response({"unexpected": {}})

    assert exc_info.value.code == "EXTERNAL_API_INVALID_RESPONSE"
