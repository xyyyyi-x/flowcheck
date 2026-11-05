import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../../src/stores/auth";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("stores token in memory and loads current user", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: "token-123",
          token_type: "bearer",
          expires_in: 1800,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: "u1",
          username: "alice",
          created_at: "2026-11-05T00:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const auth = useAuthStore();
    await auth.login("alice", "password-123");

    expect(auth.token).toBe("token-123");
    expect(auth.user?.username).toBe("alice");
    expect(auth.isAuthenticated).toBe(true);
    const [, init] = fetchMock.mock.calls[1];
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer token-123");
    expect(localStorage.length).toBe(0);
  });

  it("logout clears token and user", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({
            access_token: "token-123",
            token_type: "bearer",
            expires_in: 1800,
          }),
        )
        .mockResolvedValueOnce(
          jsonResponse({
            id: "u1",
            username: "alice",
            created_at: "2026-11-05T00:00:00Z",
          }),
        ),
    );
    const auth = useAuthStore();
    await auth.login("alice", "password-123");
    auth.logout();
    expect(auth.token).toBeNull();
    expect(auth.user).toBeNull();
    expect(auth.isAuthenticated).toBe(false);
  });
});
