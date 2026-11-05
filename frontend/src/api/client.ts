import type { ErrorEnvelope } from "./types";

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: { path: string; message: string }[];
  requestId: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details: { path: string; message: string }[] = [],
    requestId = "",
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

async function clearSessionAndRedirect(): Promise<void> {
  const { useAuthStore } = await import("../stores/auth");
  useAuthStore().clear();
  const { router } = await import("../router");
  if (router.currentRoute.value.name !== "login") {
    await router.replace({ name: "login" });
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  if (!response.ok) {
    let envelope: ErrorEnvelope | null = null;
    try {
      envelope = (await response.json()) as ErrorEnvelope;
    } catch {
      envelope = null;
    }
    const error = new ApiError(
      response.status,
      envelope?.error.code ?? "UNKNOWN_ERROR",
      envelope?.error.message ?? "请求失败，请稍后重试",
      envelope?.error.details ?? [],
      envelope?.request_id ?? "",
    );
    if (response.status === 401) {
      await clearSessionAndRedirect();
    }
    throw error;
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "资源不存在或无权访问";
    if (error.status === 409) return `${error.message}（请重新加载后再编辑）`;
    if (error.status === 422) {
      const field = error.details[0];
      return field ? `${error.message}：${field.path} ${field.message}` : error.message;
    }
    if (error.status === 500 && error.requestId) {
      return `服务器内部错误，请将请求编号 ${error.requestId} 提供给维护者`;
    }
    return error.message;
  }
  return "网络异常，请检查连接后重试";
}
