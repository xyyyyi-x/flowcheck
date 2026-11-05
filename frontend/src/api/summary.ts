import { apiFetch } from "./client";
import type { ProjectSummary } from "./types";

export function getProjectSummary(projectId: string): Promise<ProjectSummary> {
  return apiFetch<ProjectSummary>(`/projects/${projectId}/summary`);
}
