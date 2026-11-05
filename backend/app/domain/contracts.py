"""用例 DSL 的固定契约：步骤、请求、断言、提取器。"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import (
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from app.core.schemas import ApiModel
from app.domain.selectors import SelectorError, parse_selector
from app.domain.template import TemplateError, is_full_template, validate_template

JsonScalar = StrictStr | StrictInt | StrictFloat | StrictBool | None
Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
PATH_PARAM = re.compile(r"\{([^{}]+)\}")
FORBIDDEN_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}
SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "secret",
}
REQUEST_MAX_BYTES = 65536


class DslValidationError(ValueError):
    pass


@dataclass
class RenderedRequest:
    method: str
    url: str
    headers: dict[str, str]
    json_body: Any
    path_template: str
    query_keys: list[str]
    timeout_s: int


@dataclass
class ResponseData:
    status_code: int
    headers: dict[str, str]
    body_json: Any
    is_json: bool
    elapsed_ms: float


@dataclass
class AssertionOutcome:
    type: str
    passed: bool
    selector: str | None = None
    expected_safe: Any = None
    actual_safe: Any = None


def _validate_name(name: str) -> str:
    if VARIABLE_NAME.fullmatch(name) is None:
        raise DslValidationError("名称必须匹配 [A-Za-z_][A-Za-z0-9_]{0,63}")
    if name == "run_id":
        raise DslValidationError("run_id 是保留变量名")
    return name


def _validate_text_templates(value: Any) -> None:
    if isinstance(value, str):
        try:
            validate_template(value)
        except TemplateError as exc:
            raise DslValidationError(str(exc)) from exc
    elif isinstance(value, dict):
        for item in value.values():
            _validate_text_templates(item)
    elif isinstance(value, list):
        for item in value:
            _validate_text_templates(item)


def _validate_sensitive_literals(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS and not (
                isinstance(item, str) and is_full_template(item)
            ):
                raise DslValidationError(f"字段 {key} 必须使用 secret 环境变量模板，不能保存字面量")
            _validate_sensitive_literals(item)
    elif isinstance(value, list):
        for item in value:
            _validate_sensitive_literals(item)


def _validate_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise DslValidationError("path 必须以单个 / 开头")
    if len(path) > 2048:
        raise DslValidationError("path 过长")
    if "{{" in path or "}}" in path:
        raise DslValidationError("path 模板不允许 {{}} 变量")
    if "?" in path or "#" in path or "://" in path:
        raise DslValidationError("path 不能包含 query、fragment 或 origin")
    if any(character.isspace() or ord(character) < 32 for character in path):
        raise DslValidationError("path 不能包含空白或控制字符")
    remaining = PATH_PARAM.sub("", path)
    if "{" in remaining or "}" in remaining:
        raise DslValidationError("path 花括号不完整")
    names = PATH_PARAM.findall(path)
    if len(names) != len(set(names)):
        raise DslValidationError("path 参数名不能重复")
    for name in names:
        if VARIABLE_NAME.fullmatch(name) is None:
            raise DslValidationError("path 参数名不合法")
    if ".." in path.split("/"):
        raise DslValidationError("path 不允许点路径")
    return path


def _validate_scalar_mapping(value: dict[str, JsonScalar], label: str, limit: int) -> None:
    if len(value) > limit:
        raise DslValidationError(f"{label} 最多 {limit} 项")
    for key, item in value.items():
        if not key:
            raise DslValidationError(f"{label} 的键不能为空")
        if isinstance(item, str):
            try:
                validate_template(item)
            except TemplateError as exc:
                raise DslValidationError(str(exc)) from exc


def _validate_headers(headers: dict[str, str]) -> None:
    if len(headers) > 30:
        raise DslValidationError("header 最多 30 项")
    for name, value in headers.items():
        if HEADER_NAME.fullmatch(name) is None:
            raise DslValidationError("header 名称不符合 HTTP token 语法")
        if name.lower() in FORBIDDEN_HEADERS:
            raise DslValidationError("该 header 由框架管理，不能配置")
        if not isinstance(value, str):
            raise DslValidationError("header 值必须是字符串")
        if "\r" in value or "\n" in value:
            raise DslValidationError("header 值不能包含换行")
        try:
            validate_template(value)
        except TemplateError as exc:
            raise DslValidationError(str(exc)) from exc


class RequestDefinition(ApiModel):
    method: Method
    path: str
    path_params: dict[str, JsonScalar] = Field(default_factory=dict)
    query: dict[str, JsonScalar] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    json_body: Any = None
    timeout_s: StrictInt = Field(default=10, ge=1, le=30)

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        return _validate_path(value)

    @field_validator("path_params")
    @classmethod
    def _path_params(cls, value: dict[str, JsonScalar]) -> dict[str, JsonScalar]:
        _validate_scalar_mapping(value, "path_params", 30)
        return value

    @field_validator("query")
    @classmethod
    def _query(cls, value: dict[str, JsonScalar]) -> dict[str, JsonScalar]:
        _validate_scalar_mapping(value, "query", 30)
        return value

    @field_validator("headers")
    @classmethod
    def _headers(cls, value: dict[str, str]) -> dict[str, str]:
        _validate_headers(value)
        return value

    @field_validator("json_body")
    @classmethod
    def _body(cls, value: Any) -> Any:
        if value is None:
            return None
        try:
            serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise DslValidationError("json_body 必须是合法 JSON") from exc
        if len(serialized.encode("utf-8")) > REQUEST_MAX_BYTES:
            raise DslValidationError("json_body 超过 64KiB")
        _validate_text_templates(value)
        _validate_sensitive_literals(value)
        return value

    @model_validator(mode="after")
    def _method_and_path_params(self) -> RequestDefinition:
        if self.json_body is not None and self.method not in {"POST", "PUT", "PATCH"}:
            raise DslValidationError("只有 POST/PUT/PATCH 可以携带 json_body")
        expected = set(PATH_PARAM.findall(self.path))
        if set(self.path_params) != expected:
            raise DslValidationError("path_params 的键必须恰好等于 path 中的花括号参数")
        return self


class StatusCodeAssertion(ApiModel):
    type: Literal["status_code"]
    expected: StrictInt = Field(ge=100, le=599)


class JsonEqualsAssertion(ApiModel):
    type: Literal["json_equals"]
    selector: str
    expected: Any

    @field_validator("selector")
    @classmethod
    def _selector(cls, value: str) -> str:
        try:
            parse_selector(value)
        except SelectorError as exc:
            raise DslValidationError(str(exc)) from exc
        return value

    @field_validator("expected")
    @classmethod
    def _expected(cls, value: Any) -> Any:
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise DslValidationError("expected 必须是合法 JSON") from exc
        _validate_text_templates(value)
        return value


class ResponseTimeAssertion(ApiModel):
    type: Literal["response_time_lt"]
    expected_ms: StrictInt = Field(ge=1, le=30000)


AssertionDefinition = Annotated[
    StatusCodeAssertion | JsonEqualsAssertion | ResponseTimeAssertion,
    Field(discriminator="type"),
]


class ExtractorDefinition(ApiModel):
    name: str
    selector: str
    is_secret: bool = False

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _validate_name(value)

    @field_validator("selector")
    @classmethod
    def _selector(cls, value: str) -> str:
        try:
            parse_selector(value)
        except SelectorError as exc:
            raise DslValidationError(str(exc)) from exc
        return value


class StepDefinition(ApiModel):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=80)
    source_api_id: uuid.UUID | None = None
    request: RequestDefinition
    assertions: list[AssertionDefinition] = Field(min_length=1, max_length=20)
    extractors: list[ExtractorDefinition] = Field(default_factory=list, max_length=10)
    omit_response_body: bool = False

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise DslValidationError("步骤名称不能为空")
        return value

    @model_validator(mode="after")
    def _assertion_and_extractor_rules(self) -> StepDefinition:
        status_assertions = [item for item in self.assertions if item.type == "status_code"]
        if len(status_assertions) != 1:
            raise DslValidationError("每一步必须恰有一个 status_code 断言")
        extractor_names = [item.name for item in self.extractors]
        if len(extractor_names) != len(set(extractor_names)):
            raise DslValidationError("同一步骤内提取器名称不能重复")
        return self


class StepContainerMixin(ApiModel):
    steps: list[StepDefinition] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _cross_step_rules(self) -> StepContainerMixin:
        step_ids = [str(step.id) for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise DslValidationError("步骤 id 不能重复")
        extractor_names = [item.name for step in self.steps for item in step.extractors]
        if len(extractor_names) != len(set(extractor_names)):
            raise DslValidationError("提取器名称跨步骤不能重复")
        return self
