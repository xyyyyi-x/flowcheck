<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { listCases } from "../api/cases";
import { describeError } from "../api/client";
import type { CaseRead } from "../api/types";

const route = useRoute();
const projectId = String(route.params.projectId);
const cases = ref<CaseRead[]>([]);
const loading = ref(true);
const error = ref("");

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const page = await listCases(projectId);
    cases.value = page.items;
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <header class="header">
      <div>
        <h1>测试用例</h1>
        <p class="sub">线性步骤；保存时携带版本，冲突需重新加载。</p>
      </div>
      <router-link :to="`/projects/${projectId}/cases/new`">
        <el-button type="primary">新建用例</el-button>
      </router-link>
    </header>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="cases.length === 0" class="state">
      暂无用例。新建后用“从接口添加”预填请求，再人工确认断言。
    </div>
    <el-table v-else :data="cases" border>
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="步骤数" width="90">
        <template #default="{ row }">{{ row.steps.length }}</template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column label="更新时间" min-width="180">
        <template #default="{ row }">{{ new Date(row.updated_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <router-link :to="`/projects/${projectId}/cases/${row.id}/edit`">
            <el-button link type="primary">编辑</el-button>
          </router-link>
        </template>
      </el-table-column>
    </el-table>
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
.state {
  padding: 40px;
  text-align: center;
  color: #909399;
  background: #fff;
  border-radius: 8px;
}
</style>
