<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { describeError } from "../api/client";
import { importOpenApi, listApiDefinitions } from "../api/imports";
import type { ApiDefinitionRead, ImportResult } from "../api/types";

const route = useRoute();
const projectId = String(route.params.projectId);
const definitions = ref<ApiDefinitionRead[]>([]);
const warnings = ref<ImportResult["warnings"]>([]);
const importSummary = ref<ImportResult | null>(null);
const selectedFile = ref<File | null>(null);
const loading = ref(true);
const importing = ref(false);
const error = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const page = await listApiDefinitions(projectId);
    definitions.value = page.items;
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
}

function pickFile(event: Event): void {
  const files = (event.target as HTMLInputElement).files;
  selectedFile.value = files && files.length > 0 ? files[0] : null;
}

async function upload(): Promise<void> {
  error.value = "";
  importSummary.value = null;
  warnings.value = [];
  if (!selectedFile.value) {
    error.value = "请选择本地 OpenAPI JSON 文件";
    return;
  }
  importing.value = true;
  try {
    const result = await importOpenApi(projectId, selectedFile.value);
    importSummary.value = result;
    warnings.value = result.warnings;
    selectedFile.value = null;
    if (fileInput.value) fileInput.value.value = "";
    await load();
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    importing.value = false;
  }
}

function formatParameters(item: ApiDefinitionRead): string {
  if (item.parameters.length === 0) return "无";
  return item.parameters
    .map((parameter) => `${parameter.in}:${parameter.name}(${parameter.type})`)
    .join("，");
}

onMounted(load);
</script>

<template>
  <section>
    <header class="header">
      <div>
        <h1>接口定义</h1>
        <p class="sub">仅支持本地 OpenAPI 3.0/3.1 JSON；不访问网络。</p>
      </div>
      <div class="upload">
        <input ref="fileInput" type="file" accept="application/json,.json" @change="pickFile" />
        <el-button type="primary" :loading="importing" @click="upload">
          {{ importing ? "导入中…" : "导入" }}
        </el-button>
      </div>
    </header>

    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <el-alert
      v-if="importSummary"
      class="summary"
      type="success"
      :closable="false"
      :title="`新增 ${importSummary.created_count} 个，跳过已存在 ${importSummary.skipped_count} 个`"
    />
    <el-alert
      v-if="warnings.length > 0"
      class="summary"
      type="warning"
      :closable="false"
      :title="`${warnings.length} 条导入提示`"
    >
      <ul class="warnings">
        <li v-for="(warning, index) in warnings" :key="index">
          {{ warning.path }}：{{ warning.message }}
        </li>
      </ul>
    </el-alert>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="definitions.length === 0" class="state">
      暂无接口。选择 OpenAPI JSON 文件导入后，可在用例编辑器中引用。
    </div>
    <el-table v-else :data="definitions" border>
      <el-table-column prop="method" label="方法" width="90" />
      <el-table-column prop="path" label="路径" min-width="200" />
      <el-table-column prop="summary" label="摘要" min-width="180" />
      <el-table-column label="参数（只读）" min-width="260">
        <template #default="{ row }">{{ formatParameters(row) }}</template>
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
  gap: 16px;
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
.upload {
  display: flex;
  gap: 8px;
  align-items: center;
}
.summary {
  margin-bottom: 12px;
}
.warnings {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 13px;
  max-height: 180px;
  overflow: auto;
}
.state {
  padding: 40px;
  text-align: center;
  color: #909399;
  background: #fff;
  border-radius: 8px;
}
</style>
