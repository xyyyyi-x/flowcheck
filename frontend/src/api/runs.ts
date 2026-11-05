import { apiFetch } from "./client";
import type { Page, RunCreated, RunReport, RunStatus, RunSummary } from "./types";

export function startRun(
  projectId: string,
  caseId: string,
  environmentId: string,
  idempotencyKey: string,
): Promise<RunCreated> {
  return apiFetch<RunCreated>(`/projects/${projectId}/runs`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ case_id: caseId, environment_id: environmentId }),
  });
}

export function listRuns(
  projectId: string,
  status: RunStatus | "",
  page = 1,
  pageSize = 20,
): Promise<Page<RunSummary>> {
  const filter = status ? `&status=${status}` : "";
  return apiFetch<Page<RunSummary>>(
    `/projects/${projectId}/runs?page=${page}&page_size=${pageSize}${filter}`,
  );
}

export function getRunReport(runId: string): Promise<RunReport> {
  return apiFetch<RunReport>(`/runs/${runId}`);
}
