"""用例 DSL 的结构与安全校验。"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.domain.contracts import StepDefinition

BASE_STEP = {
    "id": str(uuid.uuid4()),
    "name": "步骤",
    "source_api_id": None,
    "request": {
        "method": "GET",
        "path": "/articles",
        "path_params": {},
        "query": {},
        "headers": {},
        "json_body": None,
        "timeout_s": 10,
    },
    "assertions": [{"type": "status_code", "expected": 200}],
    "extractors": [],
    "omit_response_body": False,
}


def step(**overrides):
    payload = {**BASE_STEP, "id": str(uuid.uuid4())}
    payload.update(overrides)
    return payload


def test_valid_step_parses() -> None:
    parsed = StepDefinition.model_validate(BASE_STEP)
    assert parsed.request.method == "GET"
    assert parsed.assertions[0].type == "status_code"


def test_multiple_assertions_with_one_status_is_valid() -> None:
    payload = step(
        assertions=[
            {"type": "status_code", "expected": 200},
            {"type": "json_equals", "selector": "$.id", "expected": 1},
            {"type": "response_time_lt", "expected_ms": 500},
        ]
    )
    StepDefinition.model_validate(payload)


@pytest.mark.parametrize(
    "assertions",
    [
        [{"type": "status_code", "expected": 200}, {"type": "status_code", "expected": 201}],
        [{"type": "json_equals", "selector": "$.id", "expected": 1}],
        [{"type": "unknown", "expected": 1}],
    ],
)
def test_assertion_contract_rejections(assertions) -> None:
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(step(assertions=assertions))


def test_duplicate_extractor_within_step_rejected() -> None:
    extractor = {"name": "token", "selector": "$.token", "is_secret": True}
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(step(extractors=[extractor, extractor]))


def test_bad_selector_in_assertion_and_extractor_rejected() -> None:
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(
            step(
                assertions=[
                    {"type": "status_code", "expected": 200},
                    {"type": "json_equals", "selector": "$..id", "expected": 1},
                ]
            )
        )
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(
            step(extractors=[{"name": "x", "selector": "$[01]", "is_secret": False}])
        )


@pytest.mark.parametrize(
    ("path", "path_params"),
    [
        ("http://evil.example.com/a", {}),
        ("//evil/a", {}),
        ("/a?b=1", {}),
        ("/a#frag", {}),
        ("/a/{id", {}),
        ("/a/{id}", {}),
        ("/a", {"id": "1"}),
        ("/a/{{x}}", {}),
        ("/a/../b", {}),
    ],
)
def test_path_contract_rejections(path: str, path_params: dict) -> None:
    payload = step(
        request={
            **BASE_STEP["request"],
            "path": path,
            "path_params": path_params,
        }
    )
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(payload)


def test_valid_path_template_with_params() -> None:
    payload = step(
        request={
            **BASE_STEP["request"],
            "path": "/articles/{id}",
            "path_params": {"id": "{{article_id}}"},
        }
    )
    parsed = StepDefinition.model_validate(payload)
    assert parsed.request.path == "/articles/{id}"


def test_header_rules() -> None:
    for headers in (
        {"Host": "evil"},
        {"X-Test": "a\r\nInjected: 1"},
        {"Bad Name": "x"},
        {"Content-Length": "1"},
    ):
        with pytest.raises(ValidationError):
            StepDefinition.model_validate(
                step(request={**BASE_STEP["request"], "headers": headers})
            )

    StepDefinition.model_validate(
        step(request={**BASE_STEP["request"], "headers": {"Authorization": "Bearer {{token}}"}})
    )


def test_sensitive_body_literal_rejected_but_template_allowed() -> None:
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(
            step(
                request={
                    **BASE_STEP["request"],
                    "method": "POST",
                    "path": "/auth/login",
                    "json_body": {"username": "demo", "password": "literal-password"},
                }
            )
        )
    StepDefinition.model_validate(
        step(
            request={
                **BASE_STEP["request"],
                "method": "POST",
                "path": "/auth/login",
                "json_body": {"username": "demo", "password": "{{demo_password}}"},
            }
        )
    )


def test_body_method_and_size_rules() -> None:
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(
            step(
                request={
                    **BASE_STEP["request"],
                    "method": "GET",
                    "json_body": {"a": 1},
                }
            )
        )
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(
            step(
                request={
                    **BASE_STEP["request"],
                    "method": "POST",
                    "json_body": {"a": "x" * 70000},
                }
            )
        )


def test_malformed_template_rejected() -> None:
    payload = step(
        request={
            **BASE_STEP["request"],
            "method": "POST",
            "path": "/articles",
            "json_body": {"title": "smoke-{{run_id"},
        }
    )
    with pytest.raises(ValidationError):
        StepDefinition.model_validate(payload)


def test_lowercase_method_and_timeout_bounds_rejected() -> None:
    for request in (
        {**BASE_STEP["request"], "method": "get"},
        {**BASE_STEP["request"], "timeout_s": 0},
        {**BASE_STEP["request"], "timeout_s": 31},
    ):
        with pytest.raises(ValidationError):
            StepDefinition.model_validate(step(request=request))
