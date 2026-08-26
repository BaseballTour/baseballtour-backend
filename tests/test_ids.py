import pytest

from app.core.ids import new_prefixed_id


def test_new_prefixed_id_has_normalized_prefix() -> None:
    generated = new_prefixed_id("collection_")

    assert generated.startswith("collection_")
    assert len(generated.removeprefix("collection_")) == 32


def test_new_prefixed_id_rejects_empty_prefix() -> None:
    with pytest.raises(ValueError):
        new_prefixed_id("__")
