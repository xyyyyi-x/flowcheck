"""选择器取值与提取器规则。"""

from __future__ import annotations

import pytest

from app.domain.contracts import ExtractorDefinition
from app.domain.selectors import (
    ExtractionInvalid,
    SelectorMissing,
    extract_variables,
    resolve_selector,
)


def test_resolve_nested_values_and_null() -> None:
    document = {"data": {"items": [{"id": 7, "title": None}]}}
    assert resolve_selector(document, "$.data.items[0].id") == 7
    assert resolve_selector(document, "$.data.items[0].title") is None
    assert resolve_selector(document, "$") == document


def test_missing_field_and_out_of_range_distinct_from_null() -> None:
    with pytest.raises(SelectorMissing):
        resolve_selector({"x": None}, "$.y")
    with pytest.raises(SelectorMissing):
        resolve_selector({"items": [1]}, "$.items[1]")
    with pytest.raises(SelectorMissing):
        resolve_selector({"x": 1}, "$.x.y")


def test_extract_scalars_and_secrets() -> None:
    extractors = [
        ExtractorDefinition(name="id", selector="$.id"),
        ExtractorDefinition(name="token", selector="$.token", is_secret=True),
        ExtractorDefinition(name="nullable", selector="$.nullable"),
    ]
    extracted = extract_variables(extractors, {"id": 3, "token": "abc", "nullable": None})
    assert extracted == {"id": 3, "token": "abc", "nullable": None}


def test_secret_extraction_requires_non_empty_string() -> None:
    for document in ({"token": None}, {"token": 1}, {"token": ""}):
        with pytest.raises(ExtractionInvalid):
            extract_variables(
                [ExtractorDefinition(name="token", selector="$.token", is_secret=True)],
                document,
            )


def test_normal_extraction_rejects_objects_and_arrays() -> None:
    for document in ({"value": {"a": 1}}, {"value": [1]}):
        with pytest.raises(ExtractionInvalid):
            extract_variables([ExtractorDefinition(name="value", selector="$.value")], document)


def test_missing_field_in_extraction_is_missing() -> None:
    with pytest.raises(SelectorMissing):
        extract_variables([ExtractorDefinition(name="value", selector="$.value")], {"other": 1})
