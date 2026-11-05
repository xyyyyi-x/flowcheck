<script setup lang="ts">
import type { StepResultRead } from "../api/types";
import { errorLabel, statusLabel } from "../utils/labels";

defineProps<{ result: StepResultRead }>();

function pretty(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return JSON.stringify(value, null, 2);
}
</script>

<template>
  <el-card class="step-result" shadow="never">
    <template #header>
      <div class="head">
        <span class="position">{{ result.position }}</span>
        <span class="name">{{ result.name }}</span>
        <span class="status" :data-status="result.status">
          {{ statusLabel(result.status) }}
        </span>
        <span v-if="result.elapsed_ms !== null" class="elapsed">{{ result.elapsed_ms }} ms</span>
        <span v-if="result.error_code" class="error">{{ errorLabel(result.error_code) }}</span>
      </div>
    </template>
    <div class="grid">
      <div>
        <h4>请求（脱敏）</h4>
        <pre>{{ pretty(result.request_safe) }}</pre>
      </div>
      <div>
        <h4>响应（脱敏）</h4>
        <pre>{{ pretty(result.response_safe) }}</pre>
      </div>
    </div>
    <div v-if="result.assertions_safe.length > 0">
      <h4>断言</h4>
      <ul>
        <li v-for="(assertion, index) in result.assertions_safe" :key="index">
          <span :class="assertion.passed ? 'ok' : 'bad'">
            {{ assertion.passed ? "通过" : "失败" }}
          </span>
          {{ assertion.type }}
          <span v-if="assertion.selector" class="hint">选择器 {{ assertion.selector }}</span>
          <span class="hint">期望 {{ pretty(assertion.expected_safe) }}</span>
          <span class="hint">实际 {{ pretty(assertion.actual_safe) }}</span>
        </li>
      </ul>
    </div>
    <div v-if="result.extracts_safe.length > 0">
      <h4>提取</h4>
      <ul>
        <li v-for="(item, index) in result.extracts_safe" :key="index">
          {{ item.name }}{{ item.is_secret ? "（secret）" : "" }}：
          {{ item.success ? pretty(item.value_safe) : "未取到值" }}
        </li>
      </ul>
    </div>
  </el-card>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}
.position {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #f0f2f5;
  text-align: center;
  line-height: 22px;
  font-size: 12px;
}
.name {
  font-weight: 600;
}
.status[data-status="passed"] {
  color: #67c23a;
}
.status[data-status="failed"],
.error {
  color: #f56c6c;
}
.status[data-status="error"] {
  color: #e6a23c;
}
.status[data-status="skipped"] {
  color: #909399;
}
.elapsed {
  color: #909399;
  font-size: 12px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
h4 {
  margin: 8px 0 4px;
  font-size: 13px;
  color: #606266;
}
pre {
  margin: 0;
  background: #f7f8fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
ul {
  margin: 4px 0;
  padding-left: 18px;
  font-size: 12px;
}
.ok {
  color: #67c23a;
}
.bad {
  color: #f56c6c;
}
.hint {
  color: #909399;
  margin-left: 6px;
}
@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
