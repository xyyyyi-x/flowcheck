<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { listCases } from "../api/cases";
import { describeError } from "../api/client";
import { listEnvironments } from "../api/environments";
import { listRuns } from "../api/runs";
import type { CaseRead, EnvironmentRead, RunStatus, RunSummary } from "../api/types";
import { statusLabel } from "../utils/labels";
import { RunSubmitter } from "../utils/runSubmission";

const route = useRoute();
const router = useRouter();
const projectId = String(route.params.projectId);
const runs = ref<RunSummary[]>([]);
const cases = ref<CaseRead[]>([]);
const environments = ref<EnvironmentRead[]>([]);
const statusFilter = ref<RunStatus | "">("");
const loading = ref(true);
const error = ref("");
const dialogOpen = ref(false);
const selectedCase = ref("");
const selectedEnvironment = ref("");
const submitting = ref(false);
const submitter = new RunSubmitter();

const STATUS_OPTIONS: RunStatus[] = [
  "queued",
  "running",
  "passed",
  "failed",
  "error",
  "interrupted",
];

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [runPage, casePage, envPage] = await Promise.all([
      listRuns(projectId, statusFilter.value),
      listCases(projectId),
      listEnvironments(projectId),
    ]);
    runs.value = runPage.items;
    cases.value = casePage.items;
    environments.value = envPage.items;
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
}

async function execute(): Promise<void> {
  error.value = "";
  if (!selectedCase.value || !selectedEnvironment.value) {
    error.value = "请选择用例和环境";
    return;
  }
  submitting.value = true;
  try {
    const result = await submitter.submit(
      projectId,
      selectedCase.value,
      selectedEnvironment.value,
    );
    dialogOpen.value = false;
    await router.push(`/runs/${result.run_id}`);
  } catch (caught) {
    error.value = `${describeError(caught)}（已保留幂等键，可在网络恢复后重试）`;
  } finally {
    submitting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <header class="header">
      <div>
        <h1>运行记录</h1>
        <p class="sub">每次点击执行生成新的幂等键；网络重试复用当前键。</p>
      </div>
      <el-button type="primary" @click="dialogOpen = true">执行用例</el-button>
    </header>

    <el-alert v-if="error" type="error" :title="error" :closable="false" class="alert" />
    <div class="filters">
      <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 160px" @change="load">
        <el-option
          v-for="status in STATUS_OPTIONS"
          :key="status"
          :label="statusLabel(status)"
          :value="status"
        />
      </el-select>
      <el-button @click="load">刷新</el-button>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="runs.length === 0" class="state">
      暂无运行记录。请先创建用例和环境，然后点击“执行用例”。
    </div>
    <el-table v-else :data="runs" border>
      <el-table-column prop="case_name" label="用例" min-width="150" />
      <el-table-column prop="environment_name" label="环境" min-width="120" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">{{ statusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column label="步骤" width="160">
        <template #default="{ row }">
          通过 {{ row.counts.passed }} / 失败 {{ row.counts.failed }} / 错误 {{ row.counts.error }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="180">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <router-link :to="`/runs/${row.id}`">
            <el-button link type="primary">报告</el-button>
          </router-link>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogOpen" title="执行用例" width="440px">
      <div class="form">
        <el-alert
          v-if="cases.length === 0 || environments.length === 0"
          type="warning"
          :closable="false"
          title="需要至少一个用例和一个环境"
        />
        <label>用例</label>
        <el-select v-model="selectedCase" placeholder="选择用例" style="width: 100%">
          <el-option v-for="item in cases" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <label>环境</label>
        <el-select v-model="selectedEnvironment" placeholder="选择环境" style="width: 100%">
          <el-option
            v-for="item in environments"
            :key="item.id"
            :label="`${item.name} (${item.base_url})`"
            :value="item.id"
          />
        </el-select>
        <p class="hint">执行会向后端发送真实 HTTP 请求，请确认目标服务可控。</p>
      </div>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="cases.length === 0 || environments.length === 0"
          @click="execute"
        >
          {{ submitting ? "提交中…" : "开始执行" }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
h1 {
  margin: 0;
  font-size: 20px;
}
.sub {
  margin: 6px 0 0;
  color: #909399;
  font-size: 13px;
}
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.alert {
  margin-bottom: 12px;
}
.state {
  padding: 40px;
  text-align: center;
  color: #909399;
  background: #fff;
  border-radius: 8px;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
label {
  font-size: 13px;
  color: #606266;
}
.hint {
  color: #909399;
  font-size: 12px;
  margin: 4px 0 0;
}
</style>
