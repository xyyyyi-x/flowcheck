"""用例请求/响应模型。"""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import Field, StringConstraints

from app.core.schemas import ApiModel, UtcDatetime
from app.domain.contracts import StepContainerMixin, StepDefinition

CaseName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
CaseDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class CaseCreate(StepContainerMixin):
    name: CaseName
    description: CaseDescription = ""


class CaseUpdate(StepContainerMixin):
    name: CaseName
    description: CaseDescription = ""
    version: int = Field(ge=1)


class CaseRead(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    steps: list[StepDefinition]
    version: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
