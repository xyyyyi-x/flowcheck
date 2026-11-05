<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { createCase, getCase, updateCase } from "../api/cases";
import { describeError } from "../api/client";
import { listApiDefinitions } from "../api/imports";
import type { ApiDefinitionRead, HttpMethod } from "../api/types";
import AssertionEditor from "../components/AssertionEditor.vue";
import ExtractorEditor from "../components/ExtractorEditor.vue";
import RequestEditor from "../components/RequestEditor.vue";
import StepList from "../components/StepList.vue";
import {
  buildCasePayload,
  editableFromDefinition,
  makeEditableStep,
  moveItem,
  type EditableStep,
} from "../utils/caseEditor";

const route = useRoute();
const router = useRouter();
const projectId = String(route.params.projectId);
const caseId = route.params.caseId ? String(route.params.caseId) : null;
const isEdit = computed(() => caseId !== null);

const name = ref("新用例");
const description = ref("");
const version = ref<number | null>(null);
const steps = ref<EditableStep[]>([makeEditableStep()]);
const activeIndex = ref(0);
const apis = ref<ApiDefinitionRead[]>([]);
const apiChoice = ref<string>("");
const loading = ref(isEdit.value);
const saving = ref(false);
const error = ref("");
const activeStep = computed(() => steps.value[activeIndex.value] ?? null);

const SUPPORTED = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);

async function load(): Promise<void> {
  try {
    const definitions = await listApiDefinitions(projectId, 1, 100);
    apis.value = definitions.items;
    if (caseId) {
      const existing = await getCase(projectId, caseId);
      name.value = existing.name;
      description.value = existing.description;
      version.value = existing.version;
      steps.value = existing.steps.map(editableFromDefinition);
      activeIndex.value = 0;
    }
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
}

function addStep(): void {
  steps.value.push(makeEditableStep(`步骤 ${steps.value.length + 1}`));
  activeIndex.value = steps.value.length - 1;
}

function moveStep(index: number, delta: number): void {
  steps.value = moveItem(steps.value, index, delta);
  if (activeIndex.value === index) activeIndex.value = index + delta;
}

function removeStep(index: number): void {
  steps.value.splice(index, 1);
  activeIndex.value = Math.max(0, Math.min(activeIndex.value, steps.value.length - 1));
}

function addFromApi(): void {
  const api = apis.value.find((item) => item.id === apiChoice.value);
  if (!api) {
    error.value = "请选择要添加的接口";
    return;
  }
  if (!SUPPORTED.has(api.method)) {
    error.value = `不支持的 method: ${api.method}`;
    return;
  }
  const pathParams: Record<string, string> = {};
  for (const match of api.path.matchAll(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g)) {
    pathParams[match[1]] = "";
  }
  const step = makeEditableStep(
    api.summary || `${api.method} ${api.path}`,
    api.method as HttpMethod,
    api.path,
    api.id,
    pathParams,
  );
  const query: Record<string, unknown> = {};
  for (const parameter of api.parameters) {
    if (parameter.in === "query") query[parameter.name] = "";
  }
  step.query_text = JSON.stringify(query, null, 2);
  steps.value.push(step);
  activeIndex.value = steps.value.length - 1;
  ElMessage.info("已预填请求；期望状态码与业务值需要人工确认");
}

async function save(): Promise<void> {
  error.value = "";
  let payload;
  try {
    payload = buildCasePayload(name.value, description.value, steps.value, version.value ?? undefined);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "用例内容不合法";
    return;
  }
  saving.value = true;
  try {
    if (caseId && version.value !== null) {
      const updated = await updateCase(projectId, caseId, { ...payload, version: version.value });
      version.value = updated.version;
      ElMessage.success("用例已保存");
    } else {
      const created = await createCase(projectId, payload);
      ElMessage.success("用例已创建");
      await router.replace(`/projects/${projectId}/cases/${created.id}/edit`);
    }
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <header class="header">
      <div>
        <h1>{{ isEdit ? "编辑用例" : "新建用例" }}</h1>
        <p class="sub">步骤顺序由列表决定；状态码断言必须人工确认。</p>
      </div>
      <div class="actions">
        <router-link :to="`/projects/${projectId}/cases`">
          <el-button>返回列表</el-button>
        </router-link>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </header>

    <el-alert v-if="error" type="error" :title="error" :closable="false" class="alert" />
    <div v-if="loading" class="state">加载中…</div>
    <template v-else>
      <div class="meta-form">
        <label>
          用例名称
          <el-input v-model="name" maxlength="80" />
        </label>
        <label>
          描述
          <el-input v-model="description" maxlength="500" />
        </label>
      </div>

      <div class="editor-layout">
        <div class="left">
          <StepList
            :steps="steps"
            :active-index="activeIndex"
            @select="activeIndex = $event"
            @move="moveStep"
            @remove="removeStep"
            @add="addStep"
          />
          <div class="api-add">
            <span class="label">从接口添加</span>
            <el-select v-model="apiChoice" placeholder="选择已导入接口" style="width: 100%">
              <el-option
                v-for="api in apis"
                :key="api.id"
                :label="`${api.method} ${api.path}`"
                :value="api.id"
              />
            </el-select>
            <el-button size="small" :disabled="!apiChoice" @click="addFromApi">
              添加并预填
            </el-button>
          </div>
        </div>

        <div class="right">
          <div v-if="!activeStep" class="state">请选择或添加步骤。</div>
          <template v-else>
            <h3>步骤 {{ activeIndex + 1 }}</h3>
            <RequestEditor :step="activeStep" />
            <AssertionEditor :step="activeStep" />
            <ExtractorEditor :step="activeStep" />
          </template>
        </div>
      </div>
    </template>
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
h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.sub {
  margin: 6px 0 0;
  color: #909399;
  font-size: 13px;
}
.actions {
  display: flex;
  gap: 8px;
}
.alert {
  margin-bottom: 12px;
}
.meta-form {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 12px;
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}
.meta-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: #606266;
}
.editor-layout {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  align-items: start;
}
.api-add {
  margin-top: 12px;
  background: #fff;
  padding: 12px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-size: 13px;
  color: #606266;
}
.right {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.state {
  padding: 40px;
  text-align: center;
  color: #909399;
}
@media (max-width: 1100px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
}
</style>
