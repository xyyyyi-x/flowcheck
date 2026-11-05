"""受限选择器解析器测试。"""

from __future__ import annotations

import pytest

from app.domain.selectors import SelectorError, parse_selector


@pytest.mark.parametrize(
    ("selector", "tokens"),
    [
        ("$", ()),
        ("$.items", ("items",)),
        ("$.items[0].id", ("items", 0, "id")),
        ("$.data.items[12].title", ("data", "items", 12, "title")),
        ("$[0]", (0,)),
    ],
)
def test_valid_selectors(selector: str, tokens: tuple[str | int, ...]) -> None:
    assert parse_selector(selector) == tokens


@pytest.mark.parametrize(
    "selector",
    [
        "items",
        "$..id",
        "$[-1]",
        "$[01]",
        "$[?(@.x)]",
        "$.*",
        "$['key']",
        "$.a.",
        "$[10001]",
        "$.a b",
        "$" + ".a" * 40,
        "$." + "a" * 300,
    ],
)
def test_invalid_selectors(selector: str) -> None:
    with pytest.raises(SelectorError):
        parse_selector(selector)
