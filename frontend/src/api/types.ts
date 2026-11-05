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
