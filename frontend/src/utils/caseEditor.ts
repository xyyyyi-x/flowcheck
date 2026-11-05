import type {
  AssertionDefinition,
  CaseWrite,
  HttpMethod,
  StepDefinition,
} from "../api/types";

export interface EditableAssertion {
  type: "status_code" | "json_equals" | "response_time_lt";
  selector: string;
  expectedText: string;
  expectedMsText: string;
}

export interface EditableExtractor {
  name: string;
  selector: string;
  is_secret: boolean;
}

export interface EditableStep {
  id: string;
  name: string;
  source_api_id: string | null;
  method: HttpMethod;
  path: string;
  path_params_text: string;
  query_text: string;
  headers_text: string;
  body_text: string;
  timeout_s: number;
  assertions: EditableAssertion[];
  extractors: EditableExtractor[];
  omit_response_body: boolean;
}

export function newStepId(): string {
  return crypto.randomUUID();
}

export function makeEditableStep(
  name = "新步骤",
  method: HttpMethod = "GET",
  path = "/",
  sourceApiId: string | null = null,
  pathParams: Record<string, string> = {},
): EditableStep {
  return {
    id: newStepId(),
    name,
    source_api_id: sourceApiId,
    method,
    path,
    path_params_text: JSON.stringify(pathParams, null, 2),
    query_text: "{}",
    headers_text: "{}",
    body_text: "",
    timeout_s: 10,
    assertions: [
      { type: "status_code", selector: "", expectedText: "200", expectedMsText: "" },
    ],
    extractors: [],
    omit_response_body: false,
  };
}

export function moveItem<T>(items: T[], index: number, delta: number): T[] {
  const target = index + delta;
  if (index < 0 || index >= items.length || target < 0 || target >= items.length) {
    return [...items];
  }
  const copy = [...items];
  const [item] = copy.splice(index, 1);
  copy.splice(target, 0, item);
  return copy;
}

export function parseJsonText(text: string, label: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${label} 不是合法 JSON`);
  }
}

export function parseObjectText(text: string, label: string): Record<string, unknown> {
  const value = text.trim() === "" ? {} : parseJsonText(text, label);
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return value as Record<string, unknown>;
}

export function buildAssertions(rows: EditableAssertion[]): AssertionDefinition[] {
  const result: AssertionDefinition[] = [];
  for (const row of rows) {
    if (row.type === "status_code") {
      const expected = Number(row.expectedText);
      if (!Number.isInteger(expected) || expected < 100 || expected > 599) {
        throw new Error("status_code 期望必须是 100-599 的整数");
      }
      result.push({ type: "status_code", expected });
    } else if (row.type === "response_time_lt") {
      const expectedMs = Number(row.expectedMsText);
      if (!Number.isInteger(expectedMs) || expectedMs < 1 || expectedMs > 30000) {
        throw new Error("耗时上限必须是 1-30000 的整数毫秒");
      }
      result.push({ type: "response_time_lt", expected_ms: expectedMs });
    } else {
      if (!row.selector.trim()) throw new Error("json_equals 必须填写选择器");
      result.push({
        type: "json_equals",
        selector: row.selector.trim(),
        expected: parseJsonText(row.expectedText, "期望值"),
      });
    }
  }
  if (result.filter((item) => item.type === "status_code").length !== 1) {
    throw new Error("每一步必须恰有一个 status_code 断言");
  }
  return result;
}

export function buildStep(step: EditableStep): StepDefinition {
  const pathParams = parseObjectText(step.path_params_text, "path_params");
  const query = parseObjectText(step.query_text, "query");
  const rawHeaders = parseObjectText(step.headers_text, "headers");
  const headers: Record<string, string> = {};
  for (const [key, value] of Object.entries(rawHeaders)) {
    if (typeof value !== "string") throw new Error("header 值必须是字符串");
    headers[key] = value;
  }
  const body = step.body_text.trim() === "" ? null : parseJsonText(step.body_text, "请求体");
  if (step.method !== "POST" && step.method !== "PUT" && step.method !== "PATCH" && body !== null) {
    throw new Error("只有 POST/PUT/PATCH 可以携带请求体");
  }
  const extractorNames = step.extractors.map((item) => item.name);
  if (new Set(extractorNames).size !== extractorNames.length) {
    throw new Error("同一步骤的提取器名称不能重复");
  }
  return {
    id: step.id,
    name: step.name.trim(),
    source_api_id: step.source_api_id,
    request: {
      method: step.method,
      path: step.path.trim(),
      path_params: pathParams as StepDefinition["request"]["path_params"],
      query: query as StepDefinition["request"]["query"],
      headers,
      json_body: body,
      timeout_s: Number(step.timeout_s),
    },
    assertions: buildAssertions(step.assertions),
    extractors: step.extractors
      .filter((item) => item.name.trim() && item.selector.trim())
      .map((item) => ({
        name: item.name.trim(),
        selector: item.selector.trim(),
        is_secret: item.is_secret,
      })),
    omit_response_body: step.omit_response_body,
  };
}

export function buildCasePayload(
  name: string,
  description: string,
  steps: EditableStep[],
  version?: number,
): CaseWrite {
  if (!name.trim()) throw new Error("用例名称不能为空");
  if (steps.length === 0) throw new Error("至少需要一个步骤");
  const payload: CaseWrite = {
    name: name.trim(),
    description: description.trim(),
    steps: steps.map(buildStep),
  };
  if (version !== undefined) payload.version = version;
  return payload;
}

export function editableFromDefinition(step: StepDefinition): EditableStep {
  const assertions: EditableAssertion[] = step.assertions.map((assertion) => {
    if (assertion.type === "status_code") {
      return {
        type: "status_code",
        selector: "",
        expectedText: String(assertion.expected),
        expectedMsText: "",
      };
    }
    if (assertion.type === "response_time_lt") {
      return {
        type: "response_time_lt",
        selector: "",
        expectedText: "",
        expectedMsText: String(assertion.expected_ms),
      };
    }
    return {
      type: "json_equals",
      selector: assertion.selector,
      expectedText: JSON.stringify(assertion.expected, null, 2),
      expectedMsText: "",
    };
  });
  return {
    id: step.id,
    name: step.name,
    source_api_id: step.source_api_id,
    method: step.request.method,
    path: step.request.path,
    path_params_text: JSON.stringify(step.request.path_params, null, 2),
    query_text: JSON.stringify(step.request.query, null, 2),
    headers_text: JSON.stringify(step.request.headers, null, 2),
    body_text:
      step.request.json_body === null ? "" : JSON.stringify(step.request.json_body, null, 2),
    timeout_s: step.request.timeout_s,
    assertions,
    extractors: step.extractors.map((item) => ({ ...item })),
    omit_response_body: step.omit_response_body,
  };
}
