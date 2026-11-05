"""导入落库：完整解析后单事务写入，使用 ON CONFLICT 跳过已存在接口。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import ApiDefinition
from app.modules.imports.parser import OpenApiError, limit_warnings, parse_openapi
from app.modules.imports.schemas import ImportResult, ImportWarningRead


async def import_openapi(db: AsyncSession, project_id: uuid.UUID, content: bytes) -> ImportResult:
    try:
        parsed = parse_openapi(content)
    except OpenApiError as exc:
        raise AppError(
            "VALIDATION_ERROR",
            "OpenAPI 文档不符合支持范围",
            422,
            details=[{"path": exc.path, "message": exc.message}],
        ) from exc

    rows = [
        {
            "id": uuid.uuid4(),
            "project_id": project_id,
            "method": operation.method,
            "path": operation.path,
            "summary": operation.summary,
            "parameters": operation.parameters,
            "request_body_schema": operation.request_body_schema,
        }
        for operation in parsed.operations
    ]
    created_count = 0
    if rows:
        statement = (
            insert(ApiDefinition)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["project_id", "method", "path"])
            .returning(ApiDefinition.id)
        )
        created = (await db.execute(statement)).scalars().all()
        created_count = len(created)
    skipped_count = len(rows) - created_count
    await db.commit()

    warnings = limit_warnings(parsed.warnings)
    return ImportResult(
        created_count=created_count,
        skipped_count=skipped_count,
        warnings=[ImportWarningRead(path=item.path, message=item.message) for item in warnings],
    )


async def list_api_definitions(
    db: AsyncSession, project_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[ApiDefinition], int]:
    total = await db.scalar(
        select(func.count())
        .select_from(ApiDefinition)
        .where(ApiDefinition.project_id == project_id)
    )
    items = await db.scalars(
        select(ApiDefinition)
        .where(ApiDefinition.project_id == project_id)
        .order_by(ApiDefinition.created_at.desc(), ApiDefinition.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(items), int(total or 0)


async def get_api_definition(
    db: AsyncSession, project_id: uuid.UUID, api_id: uuid.UUID
) -> ApiDefinition | None:
    return await db.scalar(
        select(ApiDefinition).where(
            ApiDefinition.id == api_id, ApiDefinition.project_id == project_id
        )
    )
