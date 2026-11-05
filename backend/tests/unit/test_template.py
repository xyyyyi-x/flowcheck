"""模板渲染与请求构造的确定性语义。"""

from __future__ import annotations

import pytest

from app.domain.contracts import RequestDefinition
from app.domain.template import (
    VariableUndefined,
    render_request,
    render_value,
    validate_template,
)


def test_full_template_preserves_scalar_type() -> None:
    assert render_value("{{n}}", {"n": 3}) == 3
    assert render_value("{{n}}", {"n": 3.5}) == 3.5
    assert render_value("{{n}}", {"n": True}) is True
    assert render_value("{{n}}", {"n": None}) is None
    assert render_value("{{n}}", {"n": "text"}) == "text"


def test_embedded_template_stringifies() -> None:
    assert render_value("x-{{n}}", {"n": 3}) == "x-3"
    assert render_value("{{flag}}/{{empty}}", {"flag": False, "empty": None}) == "false/null"


def test_render_does_not_mutate_and_not_recursive() -> None:
    original = {"title": "smoke-{{run_id}}", "count": "{{n}}"}
    rendered = render_value(original, {"run_id": "abc", "n": 2})
    assert rendered == {"title": "smoke-abc", "count": 2}
    assert original["title"] == "smoke-{{run_id}}"
    assert render_value("{{a}}", {"a": "{{b}}", "b": 1}) == "{{b}}"
    assert render_value({"{{key}}": 1}, {}) == {"{{key}}": 1}


def test_missing_variable_fails() -> None:
    with pytest.raises(VariableUndefined) as error:
        render_value("{{missing}}", {})
    assert error.value.name == "missing"


def test_validate_template_rejects_malformed() -> None:
    for bad in ("{{}}", "{{ a }}", "{{a", "a}}", "{{{a}}}"):
        with pytest.raises(ValueError):
            validate_template(bad)
    validate_template("plain {text} and {{name}} and } inside")


def test_render_request_encodes_path_query_and_headers() -> None:
    request = RequestDefinition(
        method="GET",
        path="/articles/{id}",
        path_params={"id": "{{article_id}}"},
        query={"q": "a b", "flag": "{{flag}}", "missing_ok": None},
        headers={"Authorization": "Bearer {{token}}", "X-Common": "step"},
        json_body=None,
        timeout_s=5,
    )
    rendered = render_request(
        request,
        {"article_id": "a/b c", "flag": True, "token": "secret-token", "run_id": "r1"},
        {"Authorization": "Bearer common", "x-common": "common", "X-Trace": "{{run_id}}"},
        "http://demo-api:8001",
    )
    assert rendered.url.startswith("http://demo-api:8001/articles/a%2Fb%20c?")
    assert "q=a+b" in rendered.url
    assert "flag=true" in rendered.url
    assert "missing_ok=null" in rendered.url
    assert rendered.headers["Authorization"] == "Bearer secret-token"
    assert rendered.headers["X-Common"] == "step"
    assert "x-common" not in rendered.headers
    assert rendered.query_keys == ["q", "flag", "missing_ok"]
    assert rendered.path_template == "/articles/{id}"
    assert rendered.timeout_s == 5


def test_render_request_body_preserves_types() -> None:
    request = RequestDefinition(
        method="POST",
        path="/articles",
        json_body={
            "title": "smoke-{{run_id}}",
            "count": "{{count}}",
            "nested": ["{{count}}", {"ok": "{{flag}}"}],
        },
    )
    rendered = render_request(
        request, {"run_id": "r1", "count": 4, "flag": False}, {}, "http://demo-api:8001"
    )
    assert rendered.json_body == {
        "title": "smoke-r1",
        "count": 4,
        "nested": [4, {"ok": False}],
    }


def test_missing_path_param_variable_raises_before_transport() -> None:
    request = RequestDefinition(
        method="GET", path="/articles/{id}", path_params={"id": "{{article_id}}"}
    )
    with pytest.raises(VariableUndefined):
        render_request(request, {}, {}, "http://demo-api:8001")
