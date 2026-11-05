"""环境变量、公共 header 与 secret 编辑协议。"""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.core.schemas import ApiModel, UtcDatetime

VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
FORBIDDEN_HEADERS = {
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
}
AUTH_HEADERS = {"authorization", "proxy-authorization", "cookie", "x-api-key"}

JsonScalar = str | int | float | bool | None
VariableName = Annotated[str, StringConstraints(min_length=1, max_length=64)]
EnvironmentName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class VariableInput(ApiModel):
    name: VariableName
    value: JsonScalar = None
    is_secret: bool = False

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not VARIABLE_NAME.match(value):
            raise ValueError("变量名必须匹配 [A-Za-z_][A-Za-z0-9_]{0,63}")
        if value == "run_id":
            raise ValueError("run_id 是保留变量名")
        return value

    @field_validator("value")
    @classmethod
    def _scalar_only(cls, value: Any) -> Any:
        if isinstance(value, (list, dict)):
            raise ValueError("变量值只能是 JSON 标量")
        return value

    @model_validator(mode="after")
    def _secret_shape(self) -> VariableInput:
        if (
            self.is_secret
            and self.value is not None
            and (not isinstance(self.value, str) or not self.value)
        ):
            raise ValueError("secret 变量必须是非空字符串")
        return self


class HeaderInput(ApiModel):
    name: str
    value: str | None = None
    is_secret: bool = False

    @field_validator("name")
    @classmethod
    def _valid_header(cls, value: str) -> str:
        if not HEADER_NAME.match(value):
            raise ValueError("header 名称不符合 HTTP token 语法")
        if value.lower() in FORBIDDEN_HEADERS:
            raise ValueError("该 header 由框架管理，不能配置")
        return value

    @field_validator("value")
    @classmethod
    def _no_crlf(cls, value: str | None) -> str | None:
        if value is not None and ("\r" in value or "\n" in value):
            raise ValueError("header 值不能包含换行")
        return value

    @model_validator(mode="after")
    def _auth_headers_are_secret(self) -> HeaderInput:
        if self.name.lower() in AUTH_HEADERS:
            object.__setattr__(self, "is_secret", True)
        if not self.is_secret and self.value is None:
            raise ValueError("非 secret header 必须提供值")
        return self


class EnvironmentCreate(ApiModel):
    name: EnvironmentName
    base_url: str
    variables: list[VariableInput] = Field(default_factory=list, max_length=50)
    common_headers: list[HeaderInput] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def _unique_names(self) -> EnvironmentCreate:
        variable_names = [item.name for item in self.variables]
        if len(variable_names) != len(set(variable_names)):
            raise ValueError("变量名不能重复")
        header_names = [item.name.lower() for item in self.common_headers]
        if len(header_names) != len(set(header_names)):
            raise ValueError("header 名不能重复（大小写不敏感）")
        return self


class EnvironmentUpdate(EnvironmentCreate):
    version: int = Field(ge=1)


class VariableRead(ApiModel):
    name: str
    value: JsonScalar = None
    is_secret: bool
    has_value: bool


class HeaderRead(ApiModel):
    name: str
    value: str | None = None
    is_secret: bool
    has_value: bool


class EnvironmentRead(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    base_url: str
    variables: list[VariableRead]
    common_headers: list[HeaderRead]
    version: int
    created_at: UtcDatetime
    updated_at: UtcDatetime


class TargetOrigins(ApiModel):
    items: list[str]


SecretMode = Literal["keep", "replace", "remove"]
