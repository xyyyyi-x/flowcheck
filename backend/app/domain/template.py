"""模板标记 {{name}} 的静态校验。"""

from __future__ import annotations

import re

_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
FULL_TEMPLATE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}")


class TemplateError(ValueError):
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
