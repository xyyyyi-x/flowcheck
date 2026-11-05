<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { describeError } from "../api/client";
import { getRunReport } from "../api/runs";
import type { RunReport } from "../api/types";
import StepResult from "../components/StepResult.vue";
import { useRunEvents } from "../composables/useRunEvents";
import { errorLabel, statusLabel } from "../utils/labels";

const route = useRoute();
const runId = String(route.params.runId);
const report = ref<RunReport | null>(null);
const loading = ref(true);
const error = ref("");
const terminal = computed(() =>
  report.value ? ["passed", "failed", "error", "interrupted"].includes(report.value.status) : false,
);

const { events, connectionState, start } = useRunEvents(runId, {
  onFinished: (final) => {
    report.value = final;
  },
});

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    report.value = await getRunReport(runId);
    if (!terminal.value) {
      void start("0");
    }
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
}

const connectionLabels: Record<string, string> = {
  idle: "未连接",
  connecting: "连接中",
  open: "实时更新中",
  reconnecting: "重连中",
  polling: "实时连接不可用，改为轮询报告",
  closed: "已停止",
};

onMounted(load);
</script>

<template>
  <div class="page">
    <header class="header">
      <div>
        <router-link v-if="report" :to="`/projects/${report.project_id}/runs`">
          ← 返回运行列表
        </router-link>
        <h1>运行报告</h1>
        <p class="sub">报告内容来自后端数据库的脱敏结果，刷新页面不会创建新运行。</p>
      </div>
      <el-button @click="load">刷新报告</el-button>
    </header>

    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <div v-else-if="loading" class="state">加载中…</div>
    <template v-else-if="report">
      <el-card class="summary" shadow="never">
        <div class="summary-row">
          <span class="status" :data-status="report.status">{{ statusLabel(report.status) }}</span>
          <span>{{ report.case_name }} · 版本 {{ report.case_version }}</span>
          <span class="muted">{{ report.environment_name }}</span>
          <span v-if="report.error_code" class="muted">{{ errorLabel(report.error_code) }}</span>
          <span class="muted">{{ connectionLabels[connectionState] ?? connectionState }}</span>
        </div>
        <div class="counts">
          <span>总步骤 {{ report.counts.total }}</span>
          <span>通过 {{ report.counts.passed }}</span>
          <span>失败 {{ report.counts.failed }}</span>
          <span>错误 {{ report.counts.error }}</span>
          <span>跳过 {{ report.counts.skipped }}</span>
          <span v-if="report.counts.pending">待执行 {{ report.counts.pending }}</span>
          <span v-if="report.counts.running">执行中 {{ report.counts.running }}</span>
        </div>
        <p class="muted">
          创建 {{ new Date(report.created_at).toLocaleString() }}
          <template v-if="report.finished_at">
            · 完成 {{ new Date(report.finished_at).toLocaleString() }}
          </template>
        </p>
      </el-card>

      <el-alert
        v-if="report.status === 'interrupted'"
        class="alert"
        type="warning"
        :closable="false"
        title="运行被中断：部分写操作可能已经生效，请检查目标数据；平台不会自动重试或续跑。"
      />
      <el-alert
        v-else-if="report.status === 'failed'"
        class="alert"
        type="error"
        :closable="false"
        title="断言失败：后续步骤已跳过；没有自动清理可能已产生的测试数据。"
      />

      <div class="steps">
        <StepResult
          v-for="step in report.steps"
          :key="step.id"
          :result="step"
        />
      </div>

      <el-card v-if="events.length > 0" shadow="never" class="events">
        <h3>事件游标</h3>
        <ul>
          <li v-for="event in events.slice(-10)" :key="event.id">
            <span class="muted">#{{ event.id }}</span>
            {{ event.event }}
          </li>
        </ul>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
h1 {
  margin: 8px 0 0;
  font-size: 20px;
}
.sub {
  margin: 6px 0 0;
  color: #909399;
  font-size: 13px;
}
a {
  color: #409eff;
  font-size: 13px;
  text-decoration: none;
}
.state {
  padding: 40px;
  text-align: center;
  color: #909399;
  background: #fff;
  border-radius: 8px;
}
.summary {
  margin-bottom: 12px;
}
.summary-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 14px;
}
.status {
  font-weight: 600;
}
.status[data-status="passed"] {
  color: #67c23a;
}
.status[data-status="failed"],
.status[data-status="error"] {
  color: #f56c6c;
}
.status[data-status="interrupted"] {
  color: #e6a23c;
}
.counts {
  display: flex;
  gap: 14px;
  margin: 10px 0;
  font-size: 13px;
  color: #606266;
  flex-wrap: wrap;
}
.muted {
  color: #909399;
  font-size: 13px;
}
.alert {
  margin-bottom: 12px;
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.events h3 {
  margin: 0 0 6px;
  font-size: 14px;
}
.events ul {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
}
</style>
