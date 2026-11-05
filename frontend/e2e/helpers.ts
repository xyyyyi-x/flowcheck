import type { APIRequestContext, Page } from "@playwright/test";
import { expect } from "@playwright/test";

export const API_BASE =
  process.env.E2E_API_URL ??
  `http://127.0.0.1:${process.env.API_PORT ?? "8000"}/api/v1`;

export interface Session {
  token: string;
  username: string;
}

function headers(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function registerAndLogin(
  request: APIRequestContext,
  username: string,
): Promise<Session> {
  const password = "password-123";
  const registered = await request.post(`${API_BASE}/auth/register`, {
    data: { username, password },
  });
  expect([201, 409]).toContain(registered.status());
  const login = await request.post(`${API_BASE}/auth/login`, {
    data: { username, password },
  });
  expect(login.status()).toBe(200);
  return { token: (await login.json()).access_token, username };
}

export async function createProject(
  request: APIRequestContext,
  session: Session,
  name: string,
): Promise<{ id: string }> {
  const response = await request.post(`${API_BASE}/projects`, {
    headers: headers(session.token),
    data: { name, description: "Playwright 验收项目" },
  });
  expect(response.status()).toBe(201);
  return await response.json();
}

export async function createDemoEnvironment(
  request: APIRequestContext,
  session: Session,
  projectId: string,
): Promise<{ id: string }> {
  const origins = await request.get(`${API_BASE}/target-origins`, {
    headers: headers(session.token),
  });
  const baseUrl = (await origins.json()).items[0];
  const response = await request.post(`${API_BASE}/projects/${projectId}/environments`, {
    headers: headers(session.token),
    data: {
      name: "Compose Demo",
      base_url: baseUrl,
      variables: [
        {
          name: "demo_username",
          value: process.env.DEMO_USERNAME ?? "demo",
          is_secret: false,
        },
        {
          name: "demo_password",
          value: process.env.DEMO_PASSWORD,
          is_secret: true,
        },
      ],
      common_headers: [],
    },
  });
  expect(response.status()).toBe(201);
  return await response.json();
}

function step(
  name: string,
  method: string,
  path: string,
  extra: Record<string, unknown>,
): Record<string, unknown> {
  return {
    id: crypto.randomUUID(),
    name,
    source_api_id: null,
    request: {
      method,
      path,
      path_params: extra.path_params ?? {},
      query: {},
      headers: extra.headers ?? {},
      json_body: extra.json_body ?? null,
      timeout_s: 10,
    },
    assertions: extra.assertions,
    extractors: extra.extractors ?? [],
    omit_response_body: extra.omit_response_body ?? false,
  };
}

export function fiveSteps(expectedTitle = "smoke-{{run_id}}"): Record<string, unknown>[] {
  const auth = { Authorization: "Bearer {{auth_token}}" };
  return [
    step("1. 登录", "POST", "/auth/login", {
      json_body: { username: "{{demo_username}}", password: "{{demo_password}}" },
      assertions: [{ type: "status_code", expected: 200 }],
      extractors: [{ name: "auth_token", selector: "$.access_token", is_secret: true }],
      omit_response_body: true,
    }),
    step("2. 创建文章", "POST", "/articles", {
      headers: auth,
      json_body: { title: "smoke-{{run_id}}", content: "hello" },
      assertions: [{ type: "status_code", expected: 201 }],
      extractors: [{ name: "article_id", selector: "$.id", is_secret: false }],
    }),
    step("3. 查询文章", "GET", "/articles/{id}", {
      headers: auth,
      path_params: { id: "{{article_id}}" },
      assertions: [
        { type: "status_code", expected: 200 },
        { type: "json_equals", selector: "$.title", expected: expectedTitle },
      ],
    }),
    step("4. 删除文章", "DELETE", "/articles/{id}", {
      headers: auth,
      path_params: { id: "{{article_id}}" },
      assertions: [{ type: "status_code", expected: 204 }],
      omit_response_body: true,
    }),
    step("5. 再查应 404", "GET", "/articles/{id}", {
      headers: auth,
      path_params: { id: "{{article_id}}" },
      assertions: [{ type: "status_code", expected: 404 }],
      omit_response_body: true,
    }),
  ];
}

export async function createCase(
  request: APIRequestContext,
  session: Session,
  projectId: string,
  name: string,
  expectedTitle?: string,
): Promise<{ id: string }> {
  const response = await request.post(`${API_BASE}/projects/${projectId}/cases`, {
    headers: headers(session.token),
    data: { name, description: "五步回归", steps: fiveSteps(expectedTitle) },
  });
  expect(response.status()).toBe(201);
  return await response.json();
}

export async function startRun(
  request: APIRequestContext,
  session: Session,
  projectId: string,
  caseId: string,
  environmentId: string,
): Promise<{ run_id: string }> {
  const response = await request.post(`${API_BASE}/projects/${projectId}/runs`, {
    headers: {
      ...headers(session.token),
      "Idempotency-Key": crypto.randomUUID(),
    },
    data: { case_id: caseId, environment_id: environmentId },
  });
  expect(response.status()).toBe(202);
  return await response.json();
}

export async function waitForRun(
  request: APIRequestContext,
  session: Session,
  runId: string,
  expected: string,
): Promise<void> {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const response = await request.get(`${API_BASE}/runs/${runId}`, {
      headers: headers(session.token),
    });
    const report = await response.json();
    if (report.status === expected) return;
    if (["passed", "failed", "error", "interrupted"].includes(report.status)) {
      throw new Error(`run ended as ${report.status}, expected ${expected}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("timeout waiting for run");
}

export async function fillLogin(page: Page, username: string): Promise<void> {
  await page.getByPlaceholder("3-32 位字母数字下划线").fill(username);
  await page.getByPlaceholder("至少 8 位").fill("password-123");
  await page.getByRole("button", { name: "登录" }).click();
}

export async function loginUi(page: Page, username: string): Promise<void> {
  await page.goto("/auth/login");
  await fillLogin(page, username);
  await expect(page).toHaveURL(/\/projects/);
}

/** SPA 内导航（Token 只在内存，整页 goto 会触发重新登录）。 */
export async function gotoApp(page: Page, path: string): Promise<void> {
  await page.evaluate((target) => {
    window.history.pushState({}, "", target);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
  await page.waitForURL(`**${path}`);
}
