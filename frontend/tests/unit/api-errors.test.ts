import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../src/router", () => ({
  router: {
    currentRoute: { value: { name: "login" } },
    replace: vi.fn(),
  },
}));

import { ApiError, apiFetch, describeError, setAuthToken } from "../../src/api/client";
import { useAuthStore } from "../../src/stores/auth";

function response(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    setAuthToken(null);
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("adds bearer token and parses validation details", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "请求参数不符合要求",
            details: [{ path: "body.name", message: "不能为空" }],
          },
          request_id: "req-1",
        },
        422,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    setAuthToken("token-1");

    await expect(apiFetch("/projects", { method: "POST", body: "{}" })).rejects.toMatchObject({
      status: 422,
      code: "VALIDATION_ERROR",
    });
    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer token-1");
  });

  it("clears token on 401 responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          {
            error: { code: "UNAUTHORIZED", message: "认证已失效，请重新登录" },
            request_id: "req-2",
          },
          401,
        ),
      ),
    );
    const auth = useAuthStore();
    auth.$patch({ token: "token-1" });
    setAuthToken("token-1");

    await expect(apiFetch("/projects")).rejects.toBeInstanceOf(ApiError);
    expect(auth.token).toBeNull();
  });

  it("does not expose raw response text for unknown errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("boom", { status: 500 })),
    );
    try {
      await apiFetch("/projects");
      expect.unreachable("should reject");
    } catch (error) {
      expect(describeError(error)).not.toContain("boom");
    }
  });

  it("maps status codes to actionable messages", () => {
    expect(describeError(new ApiError(404, "NOT_FOUND", "x"))).toBe(
      "资源不存在或无权访问",
    );
    expect(describeError(new ApiError(409, "CONFLICT", "已被修改"))).toContain(
      "重新加载",
    );
    expect(
      describeError(
        new ApiError(422, "VALIDATION_ERROR", "参数错误", [
          { path: "body.name", message: "不能为空" },
        ]),
      ),
    ).toContain("body.name");
  });
});
