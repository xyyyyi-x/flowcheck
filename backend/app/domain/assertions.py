"""JSON 语义断言与期望值渲染。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.domain.contracts import AssertionOutcome, ResponseData
from app.domain.selectors import SelectorMissing, resolve_selector
from app.domain.template import render_value


def json_deep_equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(expected, bool) and isinstance(actual, bool) and expected == actual
    if expected is None or actual is None:
        return expected is None and actual is None
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    if isinstance(expected, str) or isinstance(actual, str):
        return isinstance(expected, str) and isinstance(actual, str) and expected == actual
    if isinstance(expected, list) or isinstance(actual, list):
        if not (isinstance(expected, list) and isinstance(actual, list)):
            return False
        if len(expected) != len(actual):
            return False
        return all(json_deep_equal(a, b) for a, b in zip(expected, actual, strict=True))
    if isinstance(expected, dict) or isinstance(actual, dict):
        if not (isinstance(expected, dict) and isinstance(actual, dict)):
            return False
        if set(expected) != set(actual):
            return False
        return all(json_deep_equal(expected[key], actual[key]) for key in expected)
    return type(expected) is type(actual) and expected == actual


def render_assertions(assertions, context: Mapping[str, Any]) -> list:
    """在发送请求前渲染全部期望值，确保缺变量在 HTTP 前失败。"""
    rendered = []
    for assertion in assertions:
        if assertion.type == "json_equals":
            rendered.append(
                assertion.model_copy(update={"expected": render_value(assertion.expected, context)})
            )
        else:
            rendered.append(assertion)
    return rendered


def evaluate_assertions(
    assertions, response: ResponseData, context: Mapping[str, Any]
) -> list[AssertionOutcome]:
    outcomes: list[AssertionOutcome] = []
    for assertion in assertions:
        if assertion.type == "status_code":
            outcomes.append(
                AssertionOutcome(
                    type="status_code",
                    passed=response.status_code == assertion.expected,
                    expected_safe=assertion.expected,
                    actual_safe=response.status_code,
                )
            )
        elif assertion.type == "response_time_lt":
            outcomes.append(
                AssertionOutcome(
                    type="response_time_lt",
                    passed=response.elapsed_ms < assertion.expected_ms,
                    expected_safe=assertion.expected_ms,
                    actual_safe=response.elapsed_ms,
                )
            )
        elif assertion.type == "json_equals":
            expected = render_value(assertion.expected, context)
            actual = None
            passed = False
            if response.is_json:
                try:
                    actual = resolve_selector(response.body_json, assertion.selector)
                    passed = json_deep_equal(expected, actual)
                except SelectorMissing:
                    actual = None
                    passed = False
            outcomes.append(
                AssertionOutcome(
                    type="json_equals",
                    passed=passed,
                    selector=assertion.selector,
                    expected_safe=expected,
                    actual_safe=actual,
                )
            )
    return outcomes
