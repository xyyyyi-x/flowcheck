export interface User {
  id: string;
  username: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type JsonScalar = string | number | boolean | null;

export interface VariableInput {
  name: string;
  value: JsonScalar;
  is_secret: boolean;
}

export interface VariableRead {
  name: string;
  value: JsonScalar;
  is_secret: boolean;
  has_value: boolean;
}

export interface HeaderInput {
  name: string;
  value: string | null;
  is_secret: boolean;
}

export interface HeaderRead {
  name: string;
  value: string | null;
  is_secret: boolean;
  has_value: boolean;
}

export interface EnvironmentWrite {
  name: string;
  base_url: string;
  variables: VariableInput[];
  common_headers: HeaderInput[];
  version?: number;
}

export interface EnvironmentRead {
  id: string;
  project_id: string;
  name: string;
  base_url: string;
  variables: VariableRead[];
  common_headers: HeaderRead[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TargetOrigins {
  items: string[];
}

export interface ApiParameter {
  name: string;
  in: "path" | "query" | "header" | string;
  required: boolean;
  type: string;
}

export interface ApiDefinitionRead {
  id: string;
  project_id: string;
  method: string;
  path: string;
  summary: string;
  parameters: ApiParameter[];
  request_body_schema: Record<string, unknown> | null;
  created_at: string;
}

export interface ImportWarning {
  path: string;
  message: string;
}

export interface ImportResult {
  created_count: number;
  skipped_count: number;
  warnings: ImportWarning[];
}

export interface ErrorDetail {
  path: string;
  message: string;
}

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: ErrorDetail[];
  };
  request_id: string;
}

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestDefinition {
  method: HttpMethod;
  path: string;
  path_params: Record<string, JsonScalar>;
  query: Record<string, JsonScalar>;
  headers: Record<string, string>;
  json_body: unknown;
  timeout_s: number;
}

export type AssertionDefinition =
  | { type: "status_code"; expected: number }
  | { type: "json_equals"; selector: string; expected: unknown }
  | { type: "response_time_lt"; expected_ms: number };

export interface ExtractorDefinition {
  name: string;
  selector: string;
  is_secret: boolean;
}

export interface StepDefinition {
  id: string;
  name: string;
  source_api_id: string | null;
  request: RequestDefinition;
  assertions: AssertionDefinition[];
  extractors: ExtractorDefinition[];
  omit_response_body: boolean;
}

export interface CaseRead {
  id: string;
  project_id: string;
  name: string;
  description: string;
  steps: StepDefinition[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CaseWrite {
  name: string;
  description: string;
  steps: StepDefinition[];
  version?: number;
}

export type RunStatus =
  | "queued"
  | "running"
  | "passed"
  | "failed"
  | "error"
  | "interrupted";

export interface StepCounts {
  total: number;
  pending: number;
  running: number;
  passed: number;
  failed: number;
  error: number;
  skipped: number;
}

export interface RunSummary {
  id: string;
  project_id: string;
  case_id: string;
  environment_id: string;
  case_name: string;
  case_version: number;
  environment_name: string;
  environment_version: number;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  counts: StepCounts;
}

export interface StepResultRead {
  id: string;
  position: number;
  name: string;
  status: string;
  elapsed_ms: number | null;
  request_safe: Record<string, unknown> | null;
  response_safe: Record<string, unknown> | null;
  assertions_safe: Record<string, unknown>[];
  extracts_safe: Record<string, unknown>[];
  error_code: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunReport extends RunSummary {
  steps: StepResultRead[];
}

export interface RunCreated {
  run_id: string;
  status: RunStatus;
  reused: boolean;
}

export interface ProjectSummary {
  total_runs: number;
  passed_runs: number;
  failed_runs: number;
  error_runs: number;
  interrupted_runs: number;
  active_runs: number;
  pass_rate: number | null;
  computed_at: string;
  cache_hit: boolean;
}
