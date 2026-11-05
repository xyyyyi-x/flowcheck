"""OpenAPI 解析的有界性与元数据提取测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.imports.parser import OpenApiError, parse_openapi

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "openapi_minimal.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def encode(document: dict) -> bytes:
    return json.dumps(document).encode("utf-8")


def test_parse_minimal_fixture_extracts_metadata() -> None:
    result = parse_openapi(FIXTURE.read_bytes())
    operations = {(item.method, item.path): item for item in result.operations}
    assert set(operations) == {
        ("GET", "/articles"),
        ("POST", "/articles"),
        ("GET", "/articles/{id}"),
        ("DELETE", "/articles/{id}"),
    }

    listing = operations[("GET", "/articles")]
    parameters = {(item["name"], item["in"]): item for item in listing.parameters}
    assert parameters[("limit", "query")] == {
        "name": "limit",
        "in": "query",
        "required": True,
        "type": "number",
    }
    assert parameters[("X-Trace", "header")]["type"] == "string"

    detail = operations[("GET", "/articles/{id}")]
    assert [item["name"] for item in detail.parameters] == ["id"]
    assert detail.request_body_schema is None

    creation = operations[("POST", "/articles")]
    schema = creation.request_body_schema
    assert schema is not None
    assert "required" in schema
    title = schema["properties"]["title"]
    assert "example" not in title and "default" not in title
    assert "examples" not in schema["properties"]["content"]
    assert schema["properties"]["nested"] == {"$ref": "#/components/schemas/Nested"}

    messages = [warning.message for warning in result.warnings]
    assert any("cookie" in message for message in messages)
    assert any("method" in message for message in messages)
    assert any("鉴权" in message for message in messages)


def test_openapi_30_is_supported() -> None:
    document = load_fixture()
    document["openapi"] = "3.0.3"
    result = parse_openapi(encode(document))
    assert len(result.operations) == 4


@pytest.mark.parametrize(
    "content",
    [
        b"not-json",
        b"[]",
        json.dumps({"openapi": "2.0", "paths": {}}).encode(),
        json.dumps({"openapi": "3.1.0"}).encode(),
        json.dumps({"openapi": "3.1.0", "paths": []}).encode(),
    ],
)
def test_invalid_documents_rejected(content: bytes) -> None:
    with pytest.raises(OpenApiError):
        parse_openapi(content)


def test_external_ref_rejected_anywhere() -> None:
    document = load_fixture()
    document["components"]["schemas"]["Nested"] = {"$ref": "https://evil.example.com/schema.json"}
    with pytest.raises(OpenApiError, match="本地"):
        parse_openapi(encode(document))


def test_circular_parameter_ref_rejected() -> None:
    document = {
        "openapi": "3.1.0",
        "paths": {
            "/a": {
                "get": {
                    "parameters": [{"$ref": "#/components/parameters/Loop"}],
                    "responses": {},
                }
            }
        },
        "components": {"parameters": {"Loop": {"$ref": "#/components/parameters/Loop"}}},
    }
    with pytest.raises(OpenApiError, match="循环"):
        parse_openapi(encode(document))


def test_unresolved_ref_rejected() -> None:
    document = {
        "openapi": "3.1.0",
        "paths": {"/a": {"get": {"parameters": [{"$ref": "#/components/parameters/Missing"}]}}},
    }
    with pytest.raises(OpenApiError):
        parse_openapi(encode(document))


def test_oversized_file_rejected_before_parsing() -> None:
    with pytest.raises(OpenApiError, match="2MiB"):
        parse_openapi(b" " * (2 * 1024 * 1024 + 1))


def test_deep_schema_rejected() -> None:
    schema: dict = {"type": "string"}
    for _ in range(40):
        schema = {"type": "object", "properties": {"x": schema}}
    document = {
        "openapi": "3.1.0",
        "paths": {
            "/a": {"post": {"requestBody": {"content": {"application/json": {"schema": schema}}}}}
        },
    }
    with pytest.raises(OpenApiError, match="深度"):
        parse_openapi(encode(document))


def test_node_budget_enforced() -> None:
    document = {
        "openapi": "3.1.0",
        "paths": {},
        "components": {"schemas": {"Huge": {"enum": list(range(21000))}}},
    }
    with pytest.raises(OpenApiError, match="节点"):
        parse_openapi(encode(document))


def test_operation_limit_enforced() -> None:
    paths = {f"/p{index}": {"get": {"responses": {}}} for index in range(201)}
    document = {"openapi": "3.1.0", "paths": paths}
    with pytest.raises(OpenApiError, match="200"):
        parse_openapi(encode(document))
