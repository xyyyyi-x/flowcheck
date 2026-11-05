import type { HeaderInput, JsonScalar, VariableInput } from "./types";

export type SecretMode = "keep" | "replace" | "remove";

export interface EditableVariable {
  name: string;
  value: string;
  is_secret: boolean;
  has_value: boolean;
  mode: SecretMode;
}

export interface EditableHeader {
  name: string;
  value: string;
  is_secret: boolean;
  has_value: boolean;
  mode: SecretMode;
}

export function parseScalar(text: string): JsonScalar {
  if (text === "") return null;
  if (text === "true") return true;
  if (text === "false") return false;
  if (text === "null") return null;
  if (/^-?\d+$/.test(text)) return Number.parseInt(text, 10);
  if (/^-?\d+\.\d+$/.test(text)) return Number.parseFloat(text);
  return text;
}

export function stringifyScalar(value: JsonScalar): string {
  if (value === null) return "";
  if (value === true) return "true";
  if (value === false) return "false";
  return String(value);
}

export function buildVariable(row: EditableVariable): VariableInput | null {
  if (row.is_secret && row.mode === "remove") return null;
  if (row.is_secret && row.mode === "keep") {
    if (!row.has_value) throw new Error(`secret 变量 ${row.name} 必须提供值`);
    return { name: row.name, value: null, is_secret: true };
  }
  if (row.is_secret) {
    if (!row.value) throw new Error(`secret 变量 ${row.name} 不能为空`);
    return { name: row.name, value: row.value, is_secret: true };
  }
  return { name: row.name, value: parseScalar(row.value), is_secret: false };
}

export function buildHeader(row: EditableHeader): HeaderInput | null {
  if (row.is_secret && row.mode === "remove") return null;
  if (row.is_secret && row.mode === "keep") {
    if (!row.has_value) throw new Error(`secret header ${row.name} 必须提供值`);
    return { name: row.name, value: null, is_secret: true };
  }
  if (row.is_secret) {
    if (!row.value) throw new Error(`secret header ${row.name} 不能为空`);
    return { name: row.name, value: row.value, is_secret: true };
  }
  return { name: row.name, value: row.value, is_secret: false };
}
