import { apiFetch } from "./client";
import type { CaseRead, CaseWrite, Page } from "./types";

export function listCases(
  projectId: string,
  page = 1,
  pageSize = 20,
): Promise<Page<CaseRead>> {
  return apiFetch<Page<CaseRead>>(
    `/projects/${projectId}/cases?page=${page}&page_size=${pageSize}`,
  );
}

export function getCase(projectId: string, caseId: string): Promise<CaseRead> {
  return apiFetch<CaseRead>(`/projects/${projectId}/cases/${caseId}`);
}

export function createCase(projectId: string, payload: CaseWrite): Promise<CaseRead> {
  return apiFetch<CaseRead>(`/projects/${projectId}/cases`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCase(
  projectId: string,
  caseId: string,
  payload: CaseWrite & { version: number },
): Promise<CaseRead> {
  return apiFetch<CaseRead>(`/projects/${projectId}/cases/${caseId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
