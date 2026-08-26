from types import SimpleNamespace

import httpx
import pytest

from app.core.exceptions import AppException
from app.external.tour_api.client import _validate_tour_api_response


def _success_response(items=None) -> dict:
    return {
        "response": {
            "header": {"resultCode": "0000", "resultMsg": "OK"},
            "body": {"items": {"item": items or []}},
        }
    }


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


def test_root_business_error_is_mapped() -> None:
    data = {
        "resultCode": "10",
        "resultMsg": "INVALID_REQUEST_PARAMETER_ERROR",
    }

    with pytest.raises(AppException) as exc_info:
        _validate_tour_api_response(data)

    assert exc_info.value.code == "TOUR_API_FAILED"
    assert exc_info.value.details == {
        "resultCode": "10",
        "resultMessage": "INVALID_REQUEST_PARAMETER_ERROR",
    }


def test_gateway_service_error_is_mapped() -> None:
    data = {
        "OpenAPI_ServiceResponse": {
            "cmmMsgHeader": {
                "returnReasonCode": "30",
                "returnAuthMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
            }
        }
    }

    with pytest.raises(AppException) as exc_info:
        _validate_tour_api_response(data)

    assert exc_info.value.code == "TOUR_API_FAILED"
    assert exc_info.value.details["resultCode"] == "30"


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


@pytest.mark.anyio
async def test_http_timeout_is_mapped(monkeypatch) -> None:
    from app.external.tour_api import client as client_module

    monkeypatch.setattr(
        client_module,
        "get_settings",
        lambda: SimpleNamespace(tour_api_key="test-key"),
    )

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(timeout)
    ) as client:
        with pytest.raises(AppException) as exc_info:
            await client_module._request_tour_api(
                "locationBasedList2",
                {},
                client=client,
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "EXTERNAL_API_TIMEOUT"


@pytest.mark.anyio
async def test_http_rate_limit_is_mapped(monkeypatch) -> None:
    from app.external.tour_api import client as client_module

    monkeypatch.setattr(
        client_module,
        "get_settings",
        lambda: SimpleNamespace(tour_api_key="test-key"),
    )

    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(limited)
    ) as client:
        with pytest.raises(AppException) as exc_info:
            await client_module._request_tour_api(
                "locationBasedList2",
                {},
                client=client,
            )

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "EXTERNAL_API_RATE_LIMITED"


@pytest.mark.anyio
async def test_empty_provider_response_remains_successful(monkeypatch) -> None:
    from app.external.tour_api import client as client_module

    monkeypatch.setattr(
        client_module,
        "get_settings",
        lambda: SimpleNamespace(tour_api_key="test-key"),
    )

    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_success_response(),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(empty)
    ) as client:
        result = await client_module._request_tour_api(
            "searchKeyword2",
            {"keyword": "결과 없는 검색"},
            client=client,
        )

    assert client_module.extract_items(result) == []


@pytest.mark.anyio
async def test_nearby_forwards_category_and_pagination(
    monkeypatch,
) -> None:
    from app.external.tour_api import client as client_module

    received = {}

    async def fake_request(operation, params, *, client=None):
        received["operation"] = operation
        received["params"] = params
        return {"response": {"body": {"items": {"item": []}}}}

    monkeypatch.setattr(
        client_module,
        "_request_tour_api",
        fake_request,
    )

    await client_module.get_nearby_places(
        longitude=127.0719,
        latitude=37.5122,
        radius=2000,
        page_no=2,
        num_of_rows=10,
        content_type_id="39",
    )

    assert received["operation"] == "locationBasedList2"
    assert received["params"]["pageNo"] == 2
    assert received["params"]["numOfRows"] == 10
    assert received["params"]["contentTypeId"] == "39"


@pytest.mark.anyio
async def test_keyword_search_forwards_keyword_and_pagination(monkeypatch) -> None:
    from app.external.tour_api import client as client_module

    received = {}

    async def fake_request(operation, params, *, client=None):
        received.update(operation=operation, params=params)
        return {"response": {"body": {"items": {"item": []}}}}

    monkeypatch.setattr(client_module, "_request_tour_api", fake_request)
    await client_module.search_places_by_keyword(
        "잠실 맛집",
        page_no=2,
        num_of_rows=10,
        content_type_id="39",
        lcls_system1="FD",
        lcls_system2="FD02",
        lcls_system3="FD020200",
    )
    assert received["operation"] == "searchKeyword2"
    assert received["params"]["keyword"] == "잠실 맛집"
    assert received["params"]["contentTypeId"] == "39"
    assert received["params"]["lclsSystm1"] == "FD"
    assert received["params"]["lclsSystm2"] == "FD02"
    assert received["params"]["lclsSystm3"] == "FD020200"


@pytest.mark.anyio
async def test_classification_codes_forward_hierarchy(monkeypatch) -> None:
    from app.external.tour_api import client as client_module

    received = {}

    async def fake_request(operation, params, *, client=None):
        received.update(operation=operation, params=params)
        return {"response": {"body": {"items": {"item": []}}}}

    monkeypatch.setattr(
        client_module,
        "_request_tour_api",
        fake_request,
    )
    await client_module.get_classification_codes(
        lcls_system1="FD",
        lcls_system2="FD02",
        lcls_system3="FD020200",
    )
    assert received["operation"] == "lclsSystmCode2"
    assert received["params"]["lclsSystm1"] == "FD"
    assert received["params"]["lclsSystm2"] == "FD02"
    assert received["params"]["lclsSystm3"] == "FD020200"
