"""模板标记 {{name}} 的静态校验与确定性渲染。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING
from urllib.parse import quote, urlencode, urlsplit

if TYPE_CHECKING:
    from app.domain.contracts import JsonScalar, RenderedRequest, RequestDefinition

_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
FULL_TEMPLATE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}")
EMBEDDED_TEMPLATE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}")
PATH_TEMPLATE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]{0,63})\}")


class TemplateError(ValueError):
    pass


class VariableUndefined(TemplateError):
    def __init__(self, name: str) -> None:
        super().__init__(f"变量未定义: {name}")
        self.name = name


class RenderedOriginMismatch(TemplateError):
    pass


def template_name(text: str) -> str | None:
    match = FULL_TEMPLATE.fullmatch(text)
    return match.group(1) if match else None


def validate_template(text: str) -> None:
    if not isinstance(text, str):
        raise TemplateError("模板必须是字符串")
    position = 0
    length = len(text)
    while position < length:
        open_at = text.find("{{", position)
        close_at = text.find("}}", position)
        if open_at == -1 and close_at == -1:
            return
        if open_at == -1:
            raise TemplateError("模板标记不完整")
        if close_at != -1 and close_at < open_at:
            raise TemplateError("模板标记不完整")
        inner_end = text.find("}}", open_at + 2)
        if inner_end == -1:
            raise TemplateError("模板标记未闭合")
        inner = text[open_at + 2 : inner_end]
        if _VARIABLE_NAME.fullmatch(inner) is None:
            raise TemplateError("变量名不合法或包含空白")
        position = inner_end + 2


def contains_template(text: str) -> bool:
    return "{{" in text


def is_full_template(text: str) -> bool:
    return template_name(text) is not None


def stringify_scalar(value: JsonScalar) -> str:
    if isinstance(value, str):
        return value
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, float):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _lookup(name: str, context: Mapping[str, JsonScalar]) -> JsonScalar:
    if name not in context:
        raise VariableUndefined(name)
    return context[name]


def render_text(text: str, context: Mapping[str, JsonScalar]) -> str:
    validate_template(text)
    return EMBEDDED_TEMPLATE.sub(
        lambda match: stringify_scalar(_lookup(match.group(1), context)), text
    )


def render_value(value, context: Mapping[str, JsonScalar]):
    """递归渲染字符串叶子；整段模板保留原生标量，嵌入模板转字符串。"""
    if isinstance(value, str):
        name = template_name(value)
        if name is not None:
            return _lookup(name, context)
        return render_text(value, context)
    if isinstance(value, dict):
        return {key: render_value(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    return value


def _render_path(
    path: str, path_params: dict[str, JsonScalar], context: Mapping[str, JsonScalar]
) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in path_params:
            raise VariableUndefined(name)
        rendered = render_value(path_params[name], context)
        return quote(stringify_scalar(rendered), safe="")

    return PATH_TEMPLATE.sub(replace, path)


def _merge_headers(
    common_headers: Mapping[str, str], step_headers: Mapping[str, str]
) -> dict[str, str]:
    merged: dict[str, str] = dict(common_headers)
    lower_to_key = {name.lower(): name for name in merged}
    for name, value in step_headers.items():
        existing = lower_to_key.get(name.lower())
        if existing is not None:
            merged.pop(existing)
        merged[name] = value
        lower_to_key[name.lower()] = name
    return merged


def render_request(
    request: RequestDefinition,
    context: Mapping[str, JsonScalar],
    common_headers: Mapping[str, str],
    origin: str,
) -> RenderedRequest:
    from app.domain.contracts import RenderedRequest

    path = _render_path(request.path, request.path_params, context)
    query_pairs: list[tuple[str, str]] = []
    for key, value in request.query.items():
        rendered = render_value(value, context)
        query_pairs.append((key, stringify_scalar(rendered)))
    query_string = urlencode(query_pairs)
    url = origin.rstrip("/") + path
    if query_string:
        url = f"{url}?{query_string}"

    base = urlsplit(origin)
    final = urlsplit(url)
    if (final.scheme, final.netloc) != (base.scheme, base.netloc):
        raise RenderedOriginMismatch("渲染后的请求 origin 发生变化")

    headers: dict[str, str] = {}
    for name, value in _merge_headers(common_headers, request.headers).items():
        rendered = render_value(value, context)
        headers[name] = stringify_scalar(rendered)

    body = render_value(request.json_body, context)
    return RenderedRequest(
        method=request.method,
        url=url,
        headers=headers,
        json_body=body,
        path_template=request.path,
        query_keys=list(request.query),
        timeout_s=request.timeout_s,
    )
