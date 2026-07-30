import pytest

from app.core.exceptions import AppException
from app.external.tour_api.client import _validate_tour_api_response


def test_tour_api_rate_limit_error_is_mapped() -> None:
    data = {
        "response": {
            "header": {
                "resultCode": "22",
                "resultMsg": (
                    "LIMITED NUMBER OF "
                    "SERVICE REQUESTS EXCEEDS"
                ),
            }
        }
    }

    with pytest.raises(AppException) as exc_info:
        _validate_tour_api_response(data)

    assert exc_info.value.status_code == 429
    assert (
        exc_info.value.code
        == "EXTERNAL_API_RATE_LIMITED"
    )


def test_invalid_response_shape_is_rejected() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_tour_api_response({"unexpected": {}})

    assert exc_info.value.code == "EXTERNAL_API_INVALID_RESPONSE"


def test_tour_api_business_error_is_rejected() -> None:
    data = {
        "response": {
            "header": {
                "resultCode": "99",
                "resultMsg": "UNKNOWN ERROR",
            }
        }
    }

    with pytest.raises(AppException) as exc_info:
        _validate_tour_api_response(data)

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "TOUR_API_FAILED"