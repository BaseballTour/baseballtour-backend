from app.main import app


def test_trip_swagger_lists_domain_error_examples() -> None:
    responses = app.openapi()["paths"][
        "/api/v1/trips/{tripId}/plan"
    ]["get"]["responses"]

    assert {"400", "401", "403", "404", "409", "422", "500"} <= set(
        responses
    )
    examples = responses["404"]["content"]["application/json"]["examples"]
    assert "trip_not_found" in examples
    assert "plan_not_found" in examples


def test_tour_swagger_lists_external_api_errors_without_auth() -> None:
    responses = app.openapi()["paths"]["/api/v1/tour/search"]["get"][
        "responses"
    ]

    assert "401" not in responses
    assert {"400", "422", "429", "500", "502", "503"} <= set(responses)
    examples = responses["503"]["content"]["application/json"]["examples"]
    assert {"timeout", "unavailable"} <= set(examples)


def test_favorite_swagger_lists_auth_and_collection_errors() -> None:
    responses = app.openapi()["paths"][
        "/api/v1/users/me/favorite-collections/{collectionId}"
    ]["get"]["responses"]

    assert {"401", "403", "404", "422", "500", "502", "503"} <= set(
        responses
    )
    examples = responses["404"]["content"]["application/json"]["examples"]
    assert "collection_not_found" in examples


def test_all_json_requests_and_success_responses_have_examples() -> None:
    schema = app.openapi()
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if "requestBody" in operation:
                media = operation["requestBody"]["content"]["application/json"]
                assert "examples" in media, f"missing request example: {method} {path}"
            for status_code, response in operation["responses"].items():
                if not status_code.startswith("2") or status_code == "204":
                    continue
                media = response["content"]["application/json"]
                assert "examples" in media, (
                    f"missing success example: {method} {path} {status_code}"
                )


def test_all_parameters_have_description_and_example() -> None:
    schema = app.openapi()
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            for parameter in operation.get("parameters", []):
                assert parameter.get("description"), (
                    f"missing parameter description: {method} {path} {parameter['name']}"
                )
                assert "example" in parameter, (
                    f"missing parameter example: {method} {path} {parameter['name']}"
                )


def test_datetime_examples_use_korea_timezone() -> None:
    schema_text = str(app.openapi())
    assert "2026-08-16T12:00:00+09:00" in schema_text
    assert "2026-08-17T14:00:00+09:00" in schema_text
