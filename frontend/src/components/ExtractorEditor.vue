<script setup lang="ts">
import type { EditableStep } from "../utils/caseEditor";

defineProps<{ step: EditableStep }>();

function add(step: EditableStep): void {
  step.extractors.push({ name: "", selector: "$.id", is_secret: false });
}
</script>

<template>
  <div class="extractors">
    <div class="head">
      <h4>变量提取</h4>
      <el-button size="small" @click="add(step)">添加提取</el-button>
    </div>
    <div v-if="step.extractors.length === 0" class="hint">暂无提取</div>
    <div v-for="(row, index) in step.extractors" :key="index" class="row">
      <el-input v-model="row.name" placeholder="变量名" style="width: 160px" />
      <el-input v-model="row.selector" placeholder="$.access_token" style="width: 200px" />
      <el-checkbox v-model="row.is_secret">secret</el-checkbox>
      <el-button link type="danger" @click="step.extractors.splice(index, 1)">删除</el-button>
    </div>
    <p class="hint">名称跨步骤不可重复，也不能与环境变量或 run_id 冲突。</p>
  </div>
</template>

<style scoped>
.extractors {
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
}
.hint {
  color: #909399;
  font-size: 12px;
  margin: 0;
}
</style>
