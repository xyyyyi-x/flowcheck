export const RUN_STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  passed: "通过",
  failed: "断言失败",
  error: "执行错误",
  interrupted: "执行中断",
  pending: "待执行",
  skipped: "已跳过",
};

export function statusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? status;
}

export const ERROR_CODE_LABELS: Record<string, string> = {
  ASSERTION_FAILED: "断言未通过",
  VARIABLE_UNDEFINED: "变量未定义",
  SELECTOR_MISSING: "选择器未取到值",
  EXTRACTION_INVALID: "提取值类型不符合要求",
  REQUEST_TIMEOUT: "请求超时",
  NETWORK_ERROR: "网络错误",
  RESPONSE_TOO_LARGE: "响应超过 1MiB",
  RESPONSE_NOT_JSON: "响应不是 JSON",
  TARGET_NOT_ALLOWED: "目标 origin 不允许",
  DISPATCH_TIMEOUT: "排队超时未执行",
  RUN_TIMEOUT: "运行超时",
  WORKER_INTERRUPTED: "Worker 中断",
  INTERNAL_ERROR: "内部错误",
};

export function errorLabel(code: string | null | undefined): string {
  if (!code) return "";
  return ERROR_CODE_LABELS[code] ?? code;
}
