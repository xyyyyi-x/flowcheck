"""环境配置服务：加密存储、secret 保留/替换/移除与版本冲突。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, normalize_origin
from app.core.crypto import decrypt_json, encrypt_json
from app.core.errors import AppError
from app.db.models import Environment
from app.modules.environments.schemas import (
    EnvironmentCreate,
    EnvironmentRead,
    EnvironmentUpdate,
    HeaderInput,
    HeaderRead,
    VariableInput,
    VariableRead,
)


def _invalid(path: str, message: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        "请求参数不符合要求",
        422,
        details=[{"path": path, "message": message}],
    )


def _validated_origin(settings: Settings, base_url: str) -> str:
    try:
        origin = normalize_origin(base_url)
    except ValueError as exc:
        raise _invalid("body.base_url", "base_url 必须是合法的 http(s) origin") from exc
    if origin not in settings.allowed_origins:
        raise _invalid("body.base_url", "base_url 不在部署者允许的 origin 列表中")
    return origin


def _resolve_create(variables: list[VariableInput], headers: list[HeaderInput]) -> dict[str, Any]:
    variable_items = []
    for index, item in enumerate(variables):
        if item.is_secret and item.value is None:
            raise _invalid(f"body.variables.{index}.value", "首次创建 secret 必须提供值")
        variable_items.append({"name": item.name, "value": item.value, "is_secret": item.is_secret})
    header_items = []
    for index, item in enumerate(headers):
        if item.is_secret and item.value is None:
            raise _invalid(f"body.common_headers.{index}.value", "首次创建 secret 必须提供值")
        header_items.append({"name": item.name, "value": item.value, "is_secret": item.is_secret})
    return {"variables": variable_items, "common_headers": header_items}


def _resolve_update(
    variables: list[VariableInput],
    headers: list[HeaderInput],
    old_config: dict[str, Any],
) -> dict[str, Any]:
    old_variables = {item["name"]: item for item in old_config.get("variables", [])}
    old_headers = {item["name"].lower(): item for item in old_config.get("common_headers", [])}

    variable_items = []
    for index, item in enumerate(variables):
        value = item.value
        old_variable = old_variables.get(item.name)
        if (
            old_variable is not None
            and old_variable.get("is_secret")
            and not item.is_secret
            and value is None
        ):
            raise _invalid(f"body.variables.{index}.value", "secret 降级为非 secret 必须提供新值")
        if item.is_secret and value is None:
            old = old_variables.get(item.name)
            if old is None or not old.get("is_secret") or old.get("value") is None:
                raise _invalid(f"body.variables.{index}.value", "secret 必须提供新值或保留已有值")
            value = old["value"]
        elif item.is_secret:
            if not isinstance(value, str) or not value:
                raise _invalid(f"body.variables.{index}.value", "secret 变量必须是非空字符串")
        variable_items.append({"name": item.name, "value": value, "is_secret": item.is_secret})

    header_items = []
    for index, item in enumerate(headers):
        value = item.value
        old_header = old_headers.get(item.name.lower())
        if (
            old_header is not None
            and old_header.get("is_secret")
            and not item.is_secret
            and value is None
        ):
            raise _invalid(
                f"body.common_headers.{index}.value", "secret 降级为非 secret 必须提供新值"
            )
        if item.is_secret and value is None:
            old = old_headers.get(item.name.lower())
            if old is None or not old.get("is_secret") or old.get("value") is None:
                raise _invalid(
                    f"body.common_headers.{index}.value", "secret 必须提供新值或保留已有值"
                )
            value = old["value"]
        elif item.is_secret:
            if not isinstance(value, str) or not value:
                raise _invalid(f"body.common_headers.{index}.value", "secret header 值不能为空")
        header_items.append({"name": item.name, "value": value, "is_secret": item.is_secret})
    return {"variables": variable_items, "common_headers": header_items}


def _safe_variables(config: dict[str, Any]) -> list[VariableRead]:
    result = []
    for item in config.get("variables", []):
        is_secret = bool(item.get("is_secret"))
        raw_value = item.get("value")
        result.append(
            VariableRead(
                name=item["name"],
                value=None if is_secret else raw_value,
                is_secret=is_secret,
                has_value=raw_value is not None,
            )
        )
    return result


def _safe_headers(config: dict[str, Any]) -> list[HeaderRead]:
    result = []
    for item in config.get("common_headers", []):
        is_secret = bool(item.get("is_secret"))
        raw_value = item.get("value")
        result.append(
            HeaderRead(
                name=item["name"],
                value=None if is_secret else raw_value,
                is_secret=is_secret,
                has_value=raw_value is not None,
            )
        )
    return result


def environment_read(environment: Environment, settings: Settings) -> EnvironmentRead:
    config = decrypt_json(environment.config_ciphertext, settings.encryption_key)
    return EnvironmentRead(
        id=environment.id,
        project_id=environment.project_id,
        name=environment.name,
        base_url=environment.base_url,
        variables=_safe_variables(config),
        common_headers=_safe_headers(config),
        version=environment.version,
        created_at=environment.created_at,
        updated_at=environment.updated_at,
    )


async def create_environment(
    db: AsyncSession,
    project_id: uuid.UUID,
    payload: EnvironmentCreate,
    settings: Settings,
) -> Environment:
    origin = _validated_origin(settings, payload.base_url)
    config = _resolve_create(payload.variables, payload.common_headers)
    duplicate = await db.scalar(
        select(Environment.id).where(
            Environment.project_id == project_id, Environment.name == payload.name
        )
    )
    if duplicate is not None:
        raise AppError("CONFLICT", "环境名称已存在", 409)
    environment = Environment(
        project_id=project_id,
        name=payload.name,
        base_url=origin,
        config_ciphertext=encrypt_json(config, settings.encryption_key),
        version=1,
    )
    db.add(environment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("CONFLICT", "环境名称已存在", 409) from exc
    await db.refresh(environment)
    return environment


async def update_environment(
    db: AsyncSession,
    environment: Environment,
    payload: EnvironmentUpdate,
    settings: Settings,
) -> Environment:
    if payload.version != environment.version:
        raise AppError("CONFLICT", "环境已被修改，请重新加载", 409)
    origin = _validated_origin(settings, payload.base_url)
    old_config = decrypt_json(environment.config_ciphertext, settings.encryption_key)
    config = _resolve_update(payload.variables, payload.common_headers, old_config)
    environment.name = payload.name
    environment.base_url = origin
    environment.config_ciphertext = encrypt_json(config, settings.encryption_key)
    environment.version += 1
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("CONFLICT", "环境名称已存在", 409) from exc
    await db.refresh(environment)
    return environment


async def list_environments(
    db: AsyncSession, project_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[Environment], int]:
    total = await db.scalar(
        select(func.count()).select_from(Environment).where(Environment.project_id == project_id)
    )
    items = await db.scalars(
        select(Environment)
        .where(Environment.project_id == project_id)
        .order_by(Environment.created_at.desc(), Environment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(items), int(total or 0)


async def get_environment(
    db: AsyncSession, project_id: uuid.UUID, environment_id: uuid.UUID
) -> Environment | None:
    return await db.scalar(
        select(Environment).where(
            Environment.id == environment_id, Environment.project_id == project_id
        )
    )
