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
