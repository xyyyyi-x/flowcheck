"""受限 JSON 选择器：只支持 $、.field 与 [非负整数]。"""

from __future__ import annotations

import re

_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INDEX = re.compile(r"0|[1-9][0-9]*")
MAX_LENGTH = 256
MAX_TOKENS = 32
MAX_INDEX = 10000


class SelectorError(ValueError):
    pass


def parse_selector(selector: str) -> tuple[str | int, ...]:
    if not isinstance(selector, str) or not selector:
        raise SelectorError("选择器不能为空")
    if len(selector) > MAX_LENGTH:
        raise SelectorError("选择器过长")
    if not selector.startswith("$"):
        raise SelectorError("选择器必须以 $ 开头")

    tokens: list[str | int] = []
    position = 1
    length = len(selector)
    while position < length:
        character = selector[position]
        if character == ".":
            position += 1
            match = _FIELD.match(selector, position)
            if match is None:
                raise SelectorError("字段名不合法")
            tokens.append(match.group(0))
            position = match.end()
        elif character == "[":
            end = selector.find("]", position + 1)
            if end == -1:
                raise SelectorError("索引缺少右括号")
            raw_index = selector[position + 1 : end]
            if _INDEX.fullmatch(raw_index) is None:
                raise SelectorError("索引必须是非负整数且无前导零")
            index = int(raw_index)
            if index > MAX_INDEX:
                raise SelectorError("索引超出上限")
            tokens.append(index)
            position = end + 1
        else:
            raise SelectorError("选择器包含不支持的分隔符")
        if len(tokens) > MAX_TOKENS:
            raise SelectorError("选择器 token 过多")
    return tuple(tokens)


def is_valid_selector(selector: str) -> bool:
    try:
        parse_selector(selector)
        return True
    except SelectorError:
        return False
