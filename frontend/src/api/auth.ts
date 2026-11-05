import { apiFetch } from "./client";
import type { TokenResponse, User } from "./types";

export function register(username: string, password: string): Promise<User> {
  return apiFetch<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function me(): Promise<User> {
  return apiFetch<User>("/auth/me");
}
