"""线性执行器：渲染、发送、断言、提取、脱敏、落库。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.domain.assertions import evaluate_assertions, render_assertions
from app.domain.contracts import (
    AssertionOutcome,
    RunOutcome,
    RunSnapshot,
    SafeStepResult,
)
from app.domain.ports import (
    HttpTransport,
    RunBudgetExceeded,
    RunSink,
    TransportFailure,
)
from app.domain.redaction import (
    REDACTED,
    SecretRegistry,
    assertions_safe,
    redact_json,
    request_safe,
    response_safe,
)
from app.domain.selectors import SelectorMissing, resolve_selector
from app.domain.template import VariableUndefined, render_request


def _extract_step(step, response, registry: SecretRegistry) -> tuple[dict[str, Any], str | None]:
    extracted: dict[str, Any] = {}
    error: str | None = None
    for extractor in step.extractors:
        if not response.is_json:
            error = error or "RESPONSE_NOT_JSON"
            continue
        try:
            value = resolve_selector(response.body_json, extractor.selector)
        except SelectorMissing:
            error = error or "SELECTOR_MISSING"
            continue
        if extractor.is_secret:
            if not isinstance(value, str) or not value:
                error = error or "EXTRACTION_INVALID"
                continue
            registry.add(value)
        elif isinstance(value, (dict, list)):
            error = error or "EXTRACTION_INVALID"
            continue
        extracted[extractor.name] = value
    return extracted, error


def _build_extracts(
    step, extracted: Mapping[str, Any], registry: SecretRegistry
) -> list[dict[str, Any]]:
    result = []
    for extractor in step.extractors:
        success = extractor.name in extracted
        if extractor.is_secret:
            value_safe = REDACTED if success else None
        else:
            value_safe = redact_json(extracted[extractor.name], registry) if success else None
        result.append(
            {
                "name": extractor.name,
                "is_secret": extractor.is_secret,
                "success": success,
                "value_safe": value_safe,
            }
        )
    return result


def execute_snapshot(
    snapshot: RunSnapshot,
    transport: HttpTransport,
    sink: RunSink,
    monotonic: Callable[[], float],
) -> RunOutcome:
    if snapshot.schema_version != 1:
        outcome = RunOutcome(status="error", error_code="INTERNAL_ERROR", last_completed_position=0)
        sink.finish(outcome)
        return outcome

    context: dict[str, Any] = {}
    registry = SecretRegistry()
    for variable in snapshot.variables:
        context[variable["name"]] = variable["value"]
        if variable["is_secret"]:
            registry.add(variable["value"])
    context["run_id"] = str(snapshot.run_id)

    common_headers: dict[str, str] = {}
    for header in snapshot.common_headers:
        common_headers[header["name"]] = header["value"]
        if header["is_secret"]:
            registry.add(header["value"])

    budget = float(snapshot.limits.get("run_budget_s", 300))
    started = monotonic()
    last_completed = 0
    total_steps = len(snapshot.steps)

    for position, step in enumerate(snapshot.steps, start=1):
        if monotonic() - started >= budget:
            outcome = RunOutcome(
                status="interrupted",
                error_code="RUN_TIMEOUT",
                last_completed_position=last_completed,
            )
            sink.finish(outcome)
            return outcome

        sink.start_step(position)
        try:
            rendered = render_request(step.request, context, common_headers, snapshot.target_origin)
            rendered_assertions = render_assertions(step.assertions, context)
        except VariableUndefined:
            result = SafeStepResult(
                status="error",
                elapsed_ms=None,
                request_safe=None,
                response_safe=None,
                assertions_safe=[],
                extracts_safe=[],
                error_code="VARIABLE_UNDEFINED",
            )
            sink.save_step(position, result)
            outcome = RunOutcome("error", "VARIABLE_UNDEFINED", position)
            sink.finish(outcome)
            return outcome

        remaining = budget - (monotonic() - started)
        try:
            response = transport.send(rendered, step.request.timeout_s, remaining)
        except TransportFailure as exc:
            result = SafeStepResult(
                status="error",
                elapsed_ms=None,
                request_safe=request_safe(rendered, registry),
                response_safe=None,
                assertions_safe=[],
                extracts_safe=[],
                error_code=exc.code,
            )
            sink.save_step(position, result)
            if isinstance(exc, RunBudgetExceeded):
                outcome = RunOutcome("interrupted", "RUN_TIMEOUT", position)
            else:
                outcome = RunOutcome("error", exc.code, position)
            sink.finish(outcome)
            return outcome

        outcomes: list[AssertionOutcome] = evaluate_assertions(
            rendered_assertions, response, context
        )
        assertions_failed = not all(item.passed for item in outcomes)

        # 即使断言失败，也为脱敏收集 secret 提取值；但不发布到执行上下文。
        extracted, extraction_error = _extract_step(step, response, registry)

        if assertions_failed:
            status = "failed"
            error_code = "ASSERTION_FAILED"
        elif extraction_error is not None:
            status = "error"
            error_code = extraction_error
        else:
            status = "passed"
            error_code = None
            context.update(extracted)

        result = SafeStepResult(
            status=status,
            elapsed_ms=round(response.elapsed_ms),
            request_safe=request_safe(rendered, registry),
            response_safe=response_safe(response, registry, step.omit_response_body),
            assertions_safe=assertions_safe(outcomes, registry),
            extracts_safe=_build_extracts(step, extracted, registry),
            error_code=error_code,
        )
        sink.save_step(position, result)
        last_completed = position

        if status != "passed":
            outcome = RunOutcome(
                status=status, error_code=error_code, last_completed_position=position
            )
            sink.finish(outcome)
            return outcome

        if monotonic() - started >= budget:
            outcome = RunOutcome("interrupted", "RUN_TIMEOUT", last_completed)
            sink.finish(outcome)
            return outcome

    outcome = RunOutcome(status="passed", error_code=None, last_completed_position=total_steps)
    sink.finish(outcome)
    return outcome
