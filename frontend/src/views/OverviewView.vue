<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { describeError } from "../api/client";
import { getProject } from "../api/projects";
import type { Project } from "../api/types";

const route = useRoute();
const project = ref<Project | null>(null);
const error = ref("");
const loading = ref(true);
const projectId = String(route.params.projectId);

onMounted(async () => {
  try {
    project.value = await getProject(projectId);
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
});
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
        <p class="meta">
          创建于 {{ new Date(project.created_at).toLocaleString() }}
        </p>
      </el-card>
      <el-card class="next">
        <h3>下一步</h3>
        <p>先配置环境与允许的目标 origin，再导入 OpenAPI 元数据并创建用例。</p>
        <div class="links">
          <router-link :to="`/projects/${projectId}/environments`">配置环境</router-link>
          <router-link :to="`/projects/${projectId}/apis`">导入接口</router-link>
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
.description {
  color: #606266;
  margin: 0 0 12px;
}
.meta {
  color: #a8abb2;
  font-size: 12px;
}
.next {
  margin-top: 16px;
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
