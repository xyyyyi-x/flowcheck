<script setup lang="ts">
import type { EditableStep } from "../utils/caseEditor";

defineProps<{
  steps: EditableStep[];
  activeIndex: number;
}>();

const emit = defineEmits<{
  (event: "select", index: number): void;
  (event: "move", index: number, delta: number): void;
  (event: "remove", index: number): void;
  (event: "add"): void;
}>();
</script>

<template>
  <div class="step-list">
    <div class="head">
      <h3>步骤（{{ steps.length }}）</h3>
      <el-button size="small" @click="emit('add')">添加步骤</el-button>
    </div>
    <div v-if="steps.length === 0" class="empty">暂无步骤，点击“添加步骤”。</div>
    <div
      v-for="(step, index) in steps"
      :key="step.id"
      class="step-row"
      :class="{ active: index === activeIndex }"
      @click="emit('select', index)"
    >
      <span class="index">{{ index + 1 }}</span>
      <span class="name">{{ step.name || "未命名" }}</span>
      <span class="meta">{{ step.method }} {{ step.path }}</span>
      <span class="buttons">
        <el-button link size="small" :disabled="index === 0" @click.stop="emit('move', index, -1)">
          上移
        </el-button>
        <el-button
          link
          size="small"
          :disabled="index === steps.length - 1"
          @click.stop="emit('move', index, 1)"
        >
          下移
        </el-button>
        <el-button link size="small" type="danger" @click.stop="emit('remove', index)">
          删除
        </el-button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.step-list {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
h3 {
  margin: 0;
  font-size: 15px;
}
.empty {
  color: #a8abb2;
  font-size: 13px;
}
.step-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
  font-size: 13px;
}
.step-row:hover {
  background: #f5f7fa;
}
.step-row.active {
  border-color: #409eff;
  background: #ecf5ff;
}
.index {
  width: 20px;
  color: #909399;
}
.name {
  font-weight: 500;
  min-width: 80px;
}
.meta {
  color: #909399;
  flex: 1;
}
.buttons {
  display: flex;
  gap: 4px;
}
</style>
