"""有界、离线的 OpenAPI 元数据解析。

只接受本地 JSON（3.0.x / 3.1.x），不访问网络、不读取外部文件。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

MAX_BYTES = 2 * 1024 * 1024
MAX_OPERATIONS = 200
MAX_SCHEMA_DEPTH = 32
MAX_NODES = 20000
MAX_REF_DEPTH = 8
SUPPORTED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
ALLOWED_PARAM_TYPES = {
    "string",
    "number",
    "integer",
    "boolean",
    "array",
    "object",
    "unknown",
}
IGNORED_SCHEMA_KEYS = {"example", "examples", "default"}


class OpenApiError(ValueError):
    def __init__(self, message: str, path: str = "file") -> None:
        super().__init__(message)
        self.message = message
        self.path = path


@dataclass
class OperationDraft:
    method: str
    path: str
    summary: str
    parameters: list[dict[str, Any]]
    request_body_schema: dict[str, Any] | None


@dataclass
class ImportWarning:
    path: str
    message: str


@dataclass
class ImportParseResult:
    operations: list[OperationDraft] = field(default_factory=list)
    warnings: list[ImportWarning] = field(default_factory=list)


def _walk_document(value: Any, path: str, depth: int, counter: list[int]) -> None:
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise OpenApiError("文档节点数超过 20000", path)
    if depth > MAX_SCHEMA_DEPTH:
        raise OpenApiError("文档嵌套深度超过 32", path)
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and (not isinstance(item, str) or not item.startswith("#/")):
                raise OpenApiError("只允许本地 $ref（以 #/ 开头）", f"{path}.$ref")
            _walk_document(item, f"{path}.{key}", depth + 1, counter)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_document(item, f"{path}[{index}]", depth + 1, counter)


def _resolve_pointer(root: Any, ref: str, depth: int, seen: set[str]) -> Any:
    if depth > MAX_REF_DEPTH:
        raise OpenApiError("本地 $ref 解析深度超过 8", "file.$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise OpenApiError("只允许本地 $ref（以 #/ 开头）", "file.$ref")
    if ref in seen:
        raise OpenApiError("检测到循环 $ref", "file.$ref")
    seen = seen | {ref}
    current = root
    for raw_token in ref[2:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise OpenApiError("$ref 指向不存在的节点", "file.$ref")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise OpenApiError("$ref 索引越界", "file.$ref")
            current = current[int(token)]
        else:
            raise OpenApiError("$ref 无法解析", "file.$ref")
    if isinstance(current, dict) and "$ref" in current:
        return _resolve_pointer(root, current["$ref"], depth + 1, seen)
    return current


def _sanitize_schema(value: Any, path: str, depth: int = 0) -> Any:
    if depth > MAX_SCHEMA_DEPTH:
        raise OpenApiError("schema 深度超过 32", path)
    if isinstance(value, dict):
        if "$ref" in value:
            ref = value["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/"):
                raise OpenApiError("只允许本地 $ref", path)
            return {"$ref": ref}
        result = {}
        for key, item in value.items():
            if key in IGNORED_SCHEMA_KEYS:
                continue
            result[key] = _sanitize_schema(item, f"{path}.{key}", depth + 1)
        return result
    if isinstance(value, list):
        return [
            _sanitize_schema(item, f"{path}[{index}]", depth + 1)
            for index, item in enumerate(value)
        ]
    return value


def _operation_parameters(
    root: dict[str, Any],
    raw_parameters: Any,
    operation_path: str,
    warnings: list[ImportWarning],
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    if raw_parameters is None:
        return result
    if not isinstance(raw_parameters, list):
        raise OpenApiError("parameters 必须是数组", operation_path)
    for raw in raw_parameters:
        parameter = (
            _resolve_pointer(root, raw["$ref"], 1, set())
            if isinstance(raw, dict) and "$ref" in raw
            else raw
        )
        if not isinstance(parameter, dict):
            raise OpenApiError("parameter 必须是对象", operation_path)
        name = parameter.get("name")
        location = parameter.get("in")
        if not isinstance(name, str) or not name:
            raise OpenApiError("parameter.name 缺失", operation_path)
        if location not in {"path", "query", "header", "cookie"}:
            raise OpenApiError("parameter.in 不合法", operation_path)
        if location == "cookie":
            warnings.append(
                ImportWarning(
                    path=f"{operation_path}.{name}", message="cookie 参数已跳过，不被支持"
                )
            )
            continue
        required = bool(parameter.get("required", False))
        schema = parameter.get("schema")
        parameter_type = "unknown"
        if isinstance(schema, dict) and "type" in schema:
            candidate = schema["type"]
            if candidate in ALLOWED_PARAM_TYPES:
                parameter_type = candidate
        result[(name, location)] = {
            "name": name,
            "in": location,
            "required": required,
            "type": parameter_type,
        }
    return result


def _request_body_schema(
    root: dict[str, Any], raw_body: Any, operation_path: str
) -> dict[str, Any] | None:
    if raw_body is None:
        return None
    if not isinstance(raw_body, dict):
        raise OpenApiError("requestBody 必须是对象", operation_path)
    if "$ref" in raw_body:
        raw_body = _resolve_pointer(root, raw_body["$ref"], 1, set())
        if not isinstance(raw_body, dict):
            raise OpenApiError("requestBody $ref 未指向对象", operation_path)
    content = raw_body.get("content")
    if content is None:
        return None
    if not isinstance(content, dict):
        raise OpenApiError("requestBody.content 必须是对象", operation_path)
    media = content.get("application/json")
    if not isinstance(media, dict):
        return None
    schema = media.get("schema")
    if schema is None:
        return None
    return _sanitize_schema(schema, f"{operation_path}.requestBody")


def parse_openapi(content: bytes) -> ImportParseResult:
    if len(content) > MAX_BYTES:
        raise OpenApiError("文件超过 2MiB")
    try:
        document = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenApiError("文件必须是 UTF-8 编码的 JSON") from exc
    if not isinstance(document, dict):
        raise OpenApiError("OpenAPI 文档必须是 JSON 对象")
    version = document.get("openapi")
    if not isinstance(version, str) or not (
        version.startswith("3.0.") or version.startswith("3.1.")
    ):
        raise OpenApiError("只支持 OpenAPI 3.0.x 或 3.1.x")

    _walk_document(document, "file", 0, [0])

    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise OpenApiError("paths 必须是对象", "file.paths")

    result = ImportParseResult()
    supported_count = 0
    for raw_path, path_item in paths.items():
        if isinstance(raw_path, str) and raw_path.startswith("x-"):
            continue
        if not isinstance(raw_path, str) or not raw_path.startswith("/"):
            raise OpenApiError("path 必须以 / 开头", "file.paths")
        if len(raw_path) > 2048:
            raise OpenApiError("path 超过 2048 字符", "file.paths")
        if not isinstance(path_item, dict):
            raise OpenApiError("path item 必须是对象", f"file.paths.{raw_path}")
        path_parameters = _operation_parameters(
            document, path_item.get("parameters"), f"file.paths.{raw_path}", result.warnings
        )
        for raw_method, operation in path_item.items():
            if raw_method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            method = raw_method.upper()
            if not isinstance(operation, dict):
                raise OpenApiError("operation 必须是对象", f"file.paths.{raw_path}.{raw_method}")
            supported_count += 1
            if supported_count > MAX_OPERATIONS:
                raise OpenApiError("支持的 operation 超过 200 个", "file.paths")
            operation_warnings: list[ImportWarning] = []
            operation_parameters = _operation_parameters(
                document,
                operation.get("parameters"),
                f"file.paths.{raw_path}.{raw_method}",
                operation_warnings,
            )
            merged = {**path_parameters, **operation_parameters}
            summary = operation.get("summary")
            summary_text = summary[:500] if isinstance(summary, str) else ""
            result.operations.append(
                OperationDraft(
                    method=method,
                    path=raw_path,
                    summary=summary_text,
                    parameters=list(merged.values()),
                    request_body_schema=_request_body_schema(
                        document,
                        operation.get("requestBody"),
                        f"file.paths.{raw_path}.{raw_method}",
                    ),
                )
            )
            result.warnings.extend(operation_warnings)

    for raw_path, path_item in paths.items():
        if isinstance(path_item, dict):
            for raw_method in path_item:
                if raw_method.lower() in SUPPORTED_METHODS:
                    continue
                if raw_method.lower() in {
                    "parameters",
                    "summary",
                    "description",
                    "servers",
                    "$ref",
                }:
                    continue
                if raw_method.upper() in {"HEAD", "OPTIONS", "TRACE", "CONNECT"}:
                    result.warnings.append(
                        ImportWarning(
                            path=f"{raw_method.upper()} {raw_path}",
                            message="不支持的 method 已忽略",
                        )
                    )

    result.warnings.append(
        ImportWarning(
            path="file",
            message="不会自动配置鉴权；请在用例中显式设置 header 与 secret 环境变量",
        )
    )
    result.warnings.append(
        ImportWarning(
            path="file",
            message="不会生成业务参数或断言；请求值与预期状态码需要人工确认",
        )
    )
    return result


def limit_warnings(warnings: list[ImportWarning], limit: int = 100) -> list[ImportWarning]:
    if len(warnings) <= limit:
        return warnings
    return warnings[: limit - 1] + [
        ImportWarning(path="file", message=f"警告过多，其余 {len(warnings) - limit + 1} 条已截断")
    ]
