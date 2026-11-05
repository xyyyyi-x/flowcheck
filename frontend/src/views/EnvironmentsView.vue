<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { describeError } from "../api/client";
import {
  createEnvironment,
  getTargetOrigins,
  listEnvironments,
  updateEnvironment,
} from "../api/environments";
import {
  buildHeader,
  buildVariable,
  stringifyScalar,
  type EditableHeader,
  type EditableVariable,
} from "../api/secretPayload";
import type { EnvironmentRead, EnvironmentWrite } from "../api/types";
import SecretField from "../components/SecretField.vue";

const route = useRoute();
const projectId = String(route.params.projectId);
const environments = ref<EnvironmentRead[]>([]);
const origins = ref<string[]>([]);
const loading = ref(true);
const error = ref("");
const dialogOpen = ref(false);
const editingId = ref<string | null>(null);
const editingVersion = ref(1);
const submitting = ref(false);
const formError = ref("");
const form = ref({ name: "", base_url: "" });
const variables = ref<EditableVariable[]>([]);
const headers = ref<EditableHeader[]>([]);

const AUTH_HEADERS = new Set(["authorization", "proxy-authorization", "cookie", "x-api-key"]);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [page, target] = await Promise.all([
      listEnvironments(projectId),
      getTargetOrigins(),
    ]);
    environments.value = page.items;
    origins.value = target.items;
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
}

function openCreate(): void {
  editingId.value = null;
  editingVersion.value = 1;
  form.value = { name: "", base_url: origins.value[0] ?? "" };
  variables.value = [];
  headers.value = [];
  formError.value = "";
  dialogOpen.value = true;
}

function openEdit(environment: EnvironmentRead): void {
  editingId.value = environment.id;
  editingVersion.value = environment.version;
  form.value = { name: environment.name, base_url: environment.base_url };
  variables.value = environment.variables.map((item) => ({
    name: item.name,
    value: item.is_secret ? "" : stringifyScalar(item.value),
    is_secret: item.is_secret,
    has_value: item.has_value,
    mode: "keep",
  }));
  headers.value = environment.common_headers.map((item) => ({
    name: item.name,
    value: item.is_secret ? "" : (item.value ?? ""),
    is_secret: item.is_secret,
    has_value: item.has_value,
    mode: "keep",
  }));
  formError.value = "";
  dialogOpen.value = true;
}

function addVariable(): void {
  variables.value.push({
    name: "",
    value: "",
    is_secret: false,
    has_value: false,
    mode: "replace",
  });
}

function addHeader(): void {
  headers.value.push({
    name: "",
    value: "",
    is_secret: false,
    has_value: false,
    mode: "replace",
  });
}

function toggleSecret(row: EditableVariable | EditableHeader): void {
  if (row.is_secret) {
    row.has_value = false;
    row.mode = "replace";
    row.value = "";
  }
}

function headerSecretChanged(row: EditableHeader): void {
  if (AUTH_HEADERS.has(row.name.toLowerCase())) {
    row.is_secret = true;
  }
  toggleSecret(row);
}

async function save(): Promise<void> {
  formError.value = "";
  if (!form.value.name.trim()) {
    formError.value = "环境名称不能为空";
    return;
  }
  if (!form.value.base_url) {
    formError.value = "请选择部署者允许的 base_url";
    return;
  }
  if (variables.value.some((row) => !row.name.trim())) {
    formError.value = "变量名不能为空";
    return;
  }
  if (headers.value.some((row) => !row.name.trim())) {
    formError.value = "header 名不能为空";
    return;
  }
  const payload: EnvironmentWrite = {
    name: form.value.name.trim(),
    base_url: form.value.base_url,
    variables: [],
    common_headers: [],
  };
  try {
    for (const row of variables.value) {
      const item = buildVariable(row);
      if (item) payload.variables.push(item);
    }
    for (const row of headers.value) {
      const item = buildHeader(row);
      if (item) payload.common_headers.push(item);
    }
  } catch (caught) {
    formError.value = caught instanceof Error ? caught.message : "secret 配置不完整";
    return;
  }
  submitting.value = true;
  try {
    if (editingId.value) {
      await updateEnvironment(projectId, editingId.value, {
        ...payload,
        version: editingVersion.value,
      });
      ElMessage.success("环境已更新");
    } else {
      await createEnvironment(projectId, payload);
      ElMessage.success("环境已创建");
    }
    dialogOpen.value = false;
    await load();
  } catch (caught) {
    formError.value = describeError(caught);
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
        <h1>环境配置</h1>
        <p class="sub">secret 只写不读；编辑时可明确保留、替换或移除。</p>
      </div>
      <el-button type="primary" @click="openCreate">新建环境</el-button>
    </header>

    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="environments.length === 0" class="state">
      暂无环境。创建一个指向允许 origin 的环境后即可执行用例。
    </div>
    <el-table v-else :data="environments" border>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="base_url" label="base_url" min-width="220" />
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column label="更新时间" min-width="180">
        <template #default="{ row }">
          {{ new Date(row.updated_at).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogOpen" :title="editingId ? '编辑环境' : '新建环境'" width="820px">
      <el-alert v-if="formError" type="error" :title="formError" :closable="false" />
      <div class="form">
        <label>名称</label>
        <el-input v-model="form.name" maxlength="80" />
        <label>base_url（部署者允许的 origin）</label>
        <el-select v-model="form.base_url" placeholder="选择 origin" style="width: 100%">
          <el-option v-for="origin in origins" :key="origin" :label="origin" :value="origin" />
        </el-select>

        <div class="section-head">
          <h3>变量</h3>
          <el-button size="small" @click="addVariable">添加变量</el-button>
        </div>
        <div v-if="variables.length === 0" class="empty">暂无变量</div>
        <div v-for="(row, index) in variables" :key="`v-${index}`" class="row">
          <el-input v-model="row.name" placeholder="变量名" style="width: 180px" />
          <el-checkbox v-model="row.is_secret" @change="toggleSecret(row)">secret</el-checkbox>
          <SecretField
            v-if="row.is_secret"
            v-model:mode="row.mode"
            v-model:model-value="row.value"
            :has-value="row.has_value"
          />
          <el-input v-else v-model="row.value" placeholder="值（空为 null）" />
          <el-button link type="danger" @click="variables.splice(index, 1)">删除</el-button>
        </div>

        <div class="section-head">
          <h3>公共 header</h3>
          <el-button size="small" @click="addHeader">添加 header</el-button>
        </div>
        <div v-if="headers.length === 0" class="empty">暂无公共 header</div>
        <div v-for="(row, index) in headers" :key="`h-${index}`" class="row">
          <el-input
            v-model="row.name"
            placeholder="header 名"
            style="width: 180px"
            @blur="headerSecretChanged(row)"
          />
          <el-checkbox v-model="row.is_secret" @change="headerSecretChanged(row)">
            secret
          </el-checkbox>
          <SecretField
            v-if="row.is_secret"
            v-model:mode="row.mode"
            v-model:model-value="row.value"
            :has-value="row.has_value"
          />
          <el-input v-else v-model="row.value" placeholder="值，可含 {{变量}}" />
          <el-button link type="danger" @click="headers.splice(index, 1)">删除</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
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
  gap: 10px;
}
label {
  font-size: 13px;
  color: #606266;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
h3 {
  margin: 0;
  font-size: 14px;
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.empty {
  color: #a8abb2;
  font-size: 13px;
}
</style>
