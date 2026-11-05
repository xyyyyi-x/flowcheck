<script setup lang="ts">
import type { EditableAssertion, EditableStep } from "../utils/caseEditor";

defineProps<{ step: EditableStep }>();

function add(step: EditableStep): void {
  step.assertions.push({
    type: "json_equals",
    selector: "$.id",
    expectedText: "1",
    expectedMsText: "",
  });
}
</script>

<template>
  <div class="assertions">
    <div class="head">
      <h4>断言</h4>
      <el-button size="small" @click="add(step)">添加断言</el-button>
    </div>
    <div v-for="(row, index) in step.assertions" :key="index" class="row">
      <el-select v-model="row.type" style="width: 160px">
        <el-option label="status_code" value="status_code" />
        <el-option label="json_equals" value="json_equals" />
        <el-option label="response_time_lt" value="response_time_lt" />
      </el-select>
      <template v-if="row.type === 'status_code'">
        <el-input v-model="row.expectedText" placeholder="期望状态码，如 404" style="width: 160px" />
        <span class="hint">4xx/5xx 也可作为期望成功</span>
      </template>
      <template v-else-if="row.type === 'response_time_lt'">
        <el-input v-model="row.expectedMsText" placeholder="毫秒，严格小于" style="width: 160px" />
      </template>
      <template v-else>
        <el-input v-model="row.selector" placeholder="$.data.id" style="width: 180px" />
        <el-input v-model="row.expectedText" placeholder="期望值（JSON，数字不加引号）" />
      </template>
      <el-button link type="danger" @click="step.assertions.splice(index, 1)">删除</el-button>
    </div>
    <p class="hint">必须恰有一个 status_code 断言；JSON 期望值按 JSON 语法解析。</p>
  </div>
</template>

<style scoped>
.assertions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
h4 {
  margin: 0;
  font-size: 14px;
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.hint {
  color: #909399;
  font-size: 12px;
  margin: 0;
}
</style>
