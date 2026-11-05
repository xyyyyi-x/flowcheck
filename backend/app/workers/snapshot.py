"""Worker 侧快照解密与类型恢复。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.config import Settings
from app.core.crypto import decrypt_json
from app.domain.contracts import RunSnapshot, StepDefinition


class InvalidSnapshot(Exception):
    pass


def decode_snapshot(ciphertext: str, settings: Settings) -> RunSnapshot:
    try:
        payload = decrypt_json(ciphertext, settings.encryption_key)
        if payload["schema_version"] != 1:
            raise InvalidSnapshot("unsupported schema_version")
        captured_at = datetime.fromisoformat(str(payload["captured_at"]).replace("Z", "+00:00"))
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        steps = [StepDefinition.model_validate(item) for item in payload["steps"]]
        return RunSnapshot(
            schema_version=1,
            run_id=uuid.UUID(payload["run_id"]),
            case_id=uuid.UUID(payload["case_id"]),
            case_name=payload["case_name"],
            case_version=payload["case_version"],
            environment_id=uuid.UUID(payload["environment_id"]),
            environment_name=payload["environment_name"],
            environment_version=payload["environment_version"],
            target_origin=payload["target_origin"],
            variables=payload["variables"],
            common_headers=payload["common_headers"],
            steps=steps,
            limits=payload["limits"],
            captured_at=captured_at,
        )
    except InvalidSnapshot:
        raise
    except Exception as exc:
        raise InvalidSnapshot("snapshot cannot be decoded") from exc
