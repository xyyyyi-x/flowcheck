"""JSON 语义断言与耗时边界。"""

from __future__ import annotations

import pytest

from app.domain.assertions import evaluate_assertions, json_deep_equal, render_assertions
from app.domain.contracts import (
    JsonEqualsAssertion,
    ResponseData,
    ResponseTimeAssertion,
    StatusCodeAssertion,
)
from app.domain.template import VariableUndefined


def response(status: int = 200, body=None, is_json: bool = True, elapsed: float = 10.0):
    return ResponseData(
        status_code=status,
        headers={"content-type": "application/json"},
        body_json=body,
        is_json=is_json,
        elapsed_ms=elapsed,
    )


def test_status_expectation_can_be_4xx() -> None:
    outcomes = evaluate_assertions(
        [StatusCodeAssertion(type="status_code", expected=404)], response(404), {}
    )
    assert outcomes[0].passed is True
    outcomes = evaluate_assertions(
        [StatusCodeAssertion(type="status_code", expected=200)], response(404), {}
    )
    assert outcomes[0].passed is False


def test_true_is_not_equal_to_one_but_numbers_compare_numerically() -> None:
    assert json_deep_equal(True, 1) is False
    assert json_deep_equal(1, True) is False
    assert json_deep_equal(1, 1.0) is True
    assert json_deep_equal({"a": 1, "b": [1, 2]}, {"b": [1, 2], "a": 1.0}) is True
    assert json_deep_equal([1, 2], [2, 1]) is False
    assert json_deep_equal(None, None) is True
    assert json_deep_equal(None, False) is False


def test_json_equals_missing_selector_fails_without_raising() -> None:
    assertions = [JsonEqualsAssertion(type="json_equals", selector="$.missing", expected=1)]
    outcomes = evaluate_assertions(assertions, response(body={"other": 1}), {})
    assert outcomes[0].passed is False
    assert outcomes[0].actual_safe is None
    assert outcomes[0].selector == "$.missing"


def test_non_json_response_fails_json_equals_but_status_still_evaluated() -> None:
    assertions = [
        StatusCodeAssertion(type="status_code", expected=200),
        JsonEqualsAssertion(type="json_equals", selector="$.id", expected=1),
    ]
    outcomes = evaluate_assertions(assertions, response(body=None, is_json=False), {})
    assert len(outcomes) == 2
    assert outcomes[0].passed is True
    assert outcomes[1].passed is False


def test_response_time_is_strictly_less() -> None:
    assertion = ResponseTimeAssertion(type="response_time_lt", expected_ms=100)
    assert evaluate_assertions([assertion], response(elapsed=99.9), {})[0].passed is True
    assert evaluate_assertions([assertion], response(elapsed=100.0), {})[0].passed is False


def test_expected_template_is_rendered_before_evaluation() -> None:
    assertions = [
        JsonEqualsAssertion(type="json_equals", selector="$.title", expected="smoke-{{run_id}}")
    ]
    rendered = render_assertions(assertions, {"run_id": "abc"})
    assert rendered[0].expected == "smoke-abc"
    outcomes = evaluate_assertions(
        rendered, response(body={"title": "smoke-abc"}), {"run_id": "abc"}
    )
    assert outcomes[0].passed is True


def test_missing_expected_variable_fails_before_http() -> None:
    assertions = [
        JsonEqualsAssertion(type="json_equals", selector="$.title", expected="{{run_id}}")
    ]
    with pytest.raises(VariableUndefined):
        render_assertions(assertions, {})


def test_all_assertions_are_evaluated_even_after_failure() -> None:
    assertions = [
        StatusCodeAssertion(type="status_code", expected=500),
        StatusCodeAssertion(type="status_code", expected=200),
    ]
    outcomes = evaluate_assertions(assertions, response(200), {})
    assert [item.passed for item in outcomes] == [False, True]
