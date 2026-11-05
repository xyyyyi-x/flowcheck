import { apiFetch } from "./client";
import type { ApiDefinitionRead, ImportResult, Page } from "./types";

export function importOpenApi(projectId: string, file: File): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ImportResult>(`/projects/${projectId}/imports/openapi`, {
    method: "POST",
    body: form,
  });
}

export function listApiDefinitions(
  projectId: string,
  page = 1,
  pageSize = 20,
): Promise<Page<ApiDefinitionRead>> {
  return apiFetch<Page<ApiDefinitionRead>>(
    `/projects/${projectId}/api-definitions?page=${page}&page_size=${pageSize}`,
  );
}

export function getApiDefinition(
  projectId: string,
  apiId: string,
): Promise<ApiDefinitionRead> {
  return apiFetch<ApiDefinitionRead>(
    `/projects/${projectId}/api-definitions/${apiId}`,
  );
}
