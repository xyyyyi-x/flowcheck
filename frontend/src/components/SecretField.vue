<script setup lang="ts">
import type { SecretMode } from "../api/secretPayload";

const props = defineProps<{
  hasValue: boolean;
  mode: SecretMode;
  modelValue: string;
}>();

const emit = defineEmits<{
  (event: "update:mode", value: SecretMode): void;
  (event: "update:modelValue", value: string): void;
}>();

function changeMode(event: Event): void {
  emit("update:mode", (event.target as HTMLSelectElement).value as SecretMode);
}

function changeValue(event: Event): void {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}
</script>

<template>
  <div class="secret-field">
    <select
      v-if="props.hasValue"
      class="secret-mode"
      :value="props.mode"
      aria-label="secret 操作"
      @change="changeMode"
    >
      <option value="keep">保留已配置值</option>
      <option value="replace">替换为新值</option>
      <option value="remove">移除</option>
    </select>
    <input
      v-if="!props.hasValue || props.mode === 'replace'"
      class="secret-input"
      type="password"
      autocomplete="new-password"
      aria-label="secret 值"
      :value="props.modelValue"
      placeholder="输入新值（不会回显）"
      @input="changeValue"
    />
    <span v-else-if="props.mode === 'keep'" class="hint">已配置，将保留原值</span>
    <span v-else class="hint">保存后移除该项</span>
    <span
      v-if="(!props.hasValue || props.mode === 'replace') && !props.modelValue"
      class="hint warn"
    >
      必须填写非空值
    </span>
  </div>
</template>

<style scoped>
.secret-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.secret-mode,
.secret-input {
  height: 28px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 0 8px;
  font-size: 13px;
}
.hint {
  font-size: 12px;
  color: #909399;
}
.hint.warn {
  color: #e6a23c;
}
</style>
