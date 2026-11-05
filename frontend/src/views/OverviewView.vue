<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { describeError } from "../api/client";
import { getProject } from "../api/projects";
import { getProjectSummary } from "../api/summary";
import type { Project, ProjectSummary } from "../api/types";

const route = useRoute();
const project = ref<Project | null>(null);
const summary = ref<ProjectSummary | null>(null);
const error = ref("");
const loading = ref(true);
const summaryError = ref("");
const projectId = String(route.params.projectId);

async function loadSummary(): Promise<void> {
  summaryError.value = "";
  try {
    summary.value = await getProjectSummary(projectId);
  } catch (caught) {
    summaryError.value = describeError(caught);
  }
}

onMounted(async () => {
  try {
    project.value = await getProject(projectId);
    await loadSummary();
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
});

function passRateText(summaryValue: ProjectSummary): string {
  if (summaryValue.pass_rate === null) return "暂无业务运行";
  return `${(summaryValue.pass_rate * 100).toFixed(1)}%`;
}
</script>

<template>
  <section>
    <h1>项目概览</h1>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <div v-else-if="loading" class="state">加载中…</div>
    <template v-else-if="project">
      <el-card>
        <h2>{{ project.name }}</h2>
        <p class="description">{{ project.description || "暂无描述" }}</p>
        <p class="meta">创建于 {{ new Date(project.created_at).toLocaleString() }}</p>
      </el-card>

      <el-card class="summary-card">
        <div class="summary-head">
          <h3>运行统计</h3>
          <div class="actions">
            <span class="meta">统计最多 30 秒延迟</span>
            <el-button size="small" @click="loadSummary">刷新统计</el-button>
          </div>
        </div>
        <el-alert v-if="summaryError" type="warning" :title="summaryError" :closable="false" />
        <div v-else-if="summary" class="stats">
          <div class="stat">
            <span class="value">{{ summary.total_runs }}</span>
            <span class="label">总运行</span>
          </div>
          <div class="stat">
            <span class="value">{{ passRateText(summary) }}</span>
            <span class="label">通过率（通过 /（通过+失败））</span>
          </div>
          <div class="stat passed">
            <span class="value">{{ summary.passed_runs }}</span>
            <span class="label">通过</span>
          </div>
          <div class="stat failed">
            <span class="value">{{ summary.failed_runs }}</span>
            <span class="label">断言失败</span>
          </div>
          <div class="stat error">
            <span class="value">{{ summary.error_runs }}</span>
            <span class="label">错误</span>
          </div>
          <div class="stat">
            <span class="value">{{ summary.interrupted_runs }}</span>
            <span class="label">中断</span>
          </div>
          <div class="stat">
            <span class="value">{{ summary.active_runs }}</span>
            <span class="label">排队/执行中</span>
          </div>
        </div>
        <p v-if="summary" class="meta">
          数据计算于 {{ new Date(summary.computed_at).toLocaleString() }}
          <span v-if="summary.cache_hit">（来自 30 秒缓存）</span>
        </p>
      </el-card>

      <el-card class="next">
        <h3>下一步</h3>
        <p>先配置环境与允许的目标 origin，再导入 OpenAPI 元数据并创建用例。</p>
        <div class="links">
          <router-link :to="`/projects/${projectId}/environments`">配置环境</router-link>
          <router-link :to="`/projects/${projectId}/apis`">导入接口</router-link>
          <router-link :to="`/projects/${projectId}/cases`">创建用例</router-link>
          <router-link :to="`/projects/${projectId}/runs`">运行记录</router-link>
        </div>
      </el-card>
    </template>
  </section>
</template>

<style scoped>
h1 {
  font-size: 20px;
  margin: 0 0 16px;
}
h2 {
  margin: 0 0 8px;
  font-size: 18px;
}
h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.description {
  color: #606266;
  margin: 0 0 12px;
}
.meta {
  color: #a8abb2;
  font-size: 12px;
}
.summary-card,
.next {
  margin-top: 16px;
}
.summary-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.stat {
  background: #f7f8fa;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.value {
  font-size: 22px;
  font-weight: 600;
}
.label {
  font-size: 12px;
  color: #909399;
}
.stat.passed .value {
  color: #67c23a;
}
.stat.failed .value {
  color: #f56c6c;
}
.stat.error .value {
  color: #e6a23c;
}
.links {
  display: flex;
  gap: 16px;
}
a {
  color: #409eff;
}
.state {
  color: #909399;
}
</style>
