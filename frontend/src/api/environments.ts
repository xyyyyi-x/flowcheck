import { apiFetch } from "./client";
import type {
  EnvironmentRead,
  EnvironmentWrite,
  Page,
  TargetOrigins,
} from "./types";

export function listEnvironments(
  projectId: string,
  page = 1,
  pageSize = 20,
): Promise<Page<EnvironmentRead>> {
  return apiFetch<Page<EnvironmentRead>>(
    `/projects/${projectId}/environments?page=${page}&page_size=${pageSize}`,
  );
}

export function createEnvironment(
  projectId: string,
  payload: EnvironmentWrite,
): Promise<EnvironmentRead> {
  return apiFetch<EnvironmentRead>(`/projects/${projectId}/environments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateEnvironment(
  projectId: string,
  environmentId: string,
  payload: EnvironmentWrite & { version: number },
): Promise<EnvironmentRead> {
  return apiFetch<EnvironmentRead>(
    `/projects/${projectId}/environments/${environmentId}`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export function getTargetOrigins(): Promise<TargetOrigins> {
  return apiFetch<TargetOrigins>("/target-origins");
}
