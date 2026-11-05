import { describe, expect, it } from "vitest";

import type { StepDefinition } from "../../src/api/types";
import {
  buildCasePayload,
  buildStep,
  editableFromDefinition,
  makeEditableStep,
  moveItem,
  parseJsonText,
} from "../../src/utils/caseEditor";

describe("case editor helpers", () => {
  it("moves steps up and down without mutating the original array", () => {
    const list = ["a", "b", "c"];
    expect(moveItem(list, 0, 1)).toEqual(["b", "a", "c"]);
    expect(moveItem(list, 2, -1)).toEqual(["a", "c", "b"]);
    expect(moveItem(list, 0, -1)).toEqual(["a", "b", "c"]);
    expect(list).toEqual(["a", "b", "c"]);
  });

  it("rejects JSON syntax errors with a field label", () => {
    expect(() => parseJsonText("{bad", "请求体")).toThrow("请求体 不是合法 JSON");
    expect(parseJsonText('{"title": "{{run_id}}"}', "请求体")).toEqual({
      title: "{{run_id}}",
    });
  });

  it("keeps numeric expected values as numbers", () => {
    const step = makeEditableStep("数值断言");
    step.assertions.push({
      type: "json_equals",
      selector: "$.count",
      expectedText: "3",
      expectedMsText: "",
    });
    const built = buildStep(step);
    const assertion = built.assertions.find((item) => item.type === "json_equals");
    expect(assertion).toEqual({ type: "json_equals", selector: "$.count", expected: 3 });
    expect(typeof (assertion as { expected: unknown }).expected).toBe("number");
  });

  it("requires exactly one status assertion", () => {
    const step = makeEditableStep("无状态断言");
    step.assertions = [];
    expect(() => buildStep(step)).toThrow("恰有一个 status_code");
  });

  it("rejects bodies on GET and empty step lists", () => {
    const step = makeEditableStep("GET 带 body");
    step.body_text = '{"a":1}';
    expect(() => buildStep(step)).toThrow("请求体");
    expect(() =>
      buildCasePayload("空用例", "", []),
    ).toThrow("至少需要一个步骤");
  });

  it("roundtrips a valid definition", () => {
    const definition: StepDefinition = {
      id: crypto.randomUUID(),
      name: "查询",
      source_api_id: null,
      request: {
        method: "GET",
        path: "/articles/{id}",
        path_params: { id: "{{article_id}}" },
        query: {},
        headers: { Authorization: "Bearer {{token}}" },
        json_body: null,
        timeout_s: 10,
      },
      assertions: [
        { type: "status_code", expected: 200 },
        { type: "json_equals", selector: "$.title", expected: "smoke" },
      ],
      extractors: [{ name: "article_id", selector: "$.id", is_secret: false }],
      omit_response_body: false,
    };
    const built = buildStep(editableFromDefinition(definition));
    expect(built.request).toEqual(definition.request);
    expect(built.assertions).toEqual(definition.assertions);
    expect(built.extractors).toEqual(definition.extractors);
  });
});
