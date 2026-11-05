import { apiFetch } from "./client";
import type { Page, Project } from "./types";

export function listProjects(page = 1, pageSize = 20): Promise<Page<Project>> {
  return apiFetch<Page<Project>>(`/projects?page=${page}&page_size=${pageSize}`);
}

export function createProject(name: string, description: string): Promise<Project> {
  return apiFetch<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export function getProject(projectId: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`);
}

export function updateProject(
  projectId: string,
  name: string,
  description: string,
): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`, {
    method: "PUT",
    body: JSON.stringify({ name, description }),
  });
}
