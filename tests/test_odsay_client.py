import pytest

from app.external.odsay import client as odsay_client


def test_parse_transit_minutes_uses_fastest_path() -> None:
    data = {
        "result": {
            "path": [
                {"info": {"totalTime": 48}},
                {"info": {"totalTime": 61}},
            ]
        }
    }

    assert odsay_client.parse_transit_minutes(data) == 48


def test_parse_transit_minutes_rejects_error_response() -> None:
    with pytest.raises(
        ValueError,
        match=r"code=500 message=\[ApiKeyAuthFailed\]",
    ):
        odsay_client.parse_transit_minutes(
            {
                "error": [
                    {
                        "code": "500",
                        "message": "[ApiKeyAuthFailed] authentication failed.",
                    }
                ]
            }
        )


def test_parse_transit_minutes_supports_object_error() -> None:
    with pytest.raises(
        ValueError,
        match="code=-1 message=컴포넌트 에러",
    ):
        odsay_client.parse_transit_minutes(
            {"error": {"code": "-1", "msg": "컴포넌트 에러"}}
        )


@pytest.mark.anyio
async def test_cached_transit_time_avoids_duplicate_call(monkeypatch) -> None:
    calls = 0
    odsay_client._transit_cache.clear()

    async def fake_get(*args, **kwargs) -> int:
        nonlocal calls
        calls += 1
        return 33

    monkeypatch.setattr(odsay_client, "get_transit_minutes", fake_get)

    first = await odsay_client.get_cached_transit_minutes(
        127.0, 37.5, 127.1, 37.6
    )
    second = await odsay_client.get_cached_transit_minutes(
        127.0, 37.5, 127.1, 37.6
    )

    assert first == second == 33
    assert calls == 1
