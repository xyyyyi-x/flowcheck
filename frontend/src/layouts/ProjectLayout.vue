<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { describeError } from "../api/client";
import { getProject } from "../api/projects";
import type { Project } from "../api/types";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
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

function logout(): void {
  auth.logout();
  router.replace({ name: "login" });
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">接口回归测试平台</div>
      <div v-if="project" class="project-name">{{ project.name }}</div>
      <el-menu :default-active="String(route.name)" router>
        <el-menu-item :index="`/projects/${projectId}/overview`">项目概览</el-menu-item>
        <el-menu-item :index="`/projects/${projectId}/environments`">环境配置</el-menu-item>
        <el-menu-item :index="`/projects/${projectId}/apis`">接口定义</el-menu-item>
      </el-menu>
      <div class="sidebar-footer">
        <span>{{ auth.user?.username }}</span>
        <el-button link type="primary" @click="logout">退出登录</el-button>
      </div>
    </aside>
    <main class="content">
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <div v-else-if="loading" class="loading">加载中…</div>
      <router-view v-else />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}
.sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}
.brand {
  padding: 20px 16px 8px;
  font-weight: 600;
  font-size: 15px;
}
.project-name {
  padding: 0 16px 16px;
  color: #909399;
  font-size: 13px;
  word-break: break-all;
}
.sidebar-footer {
  margin-top: auto;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #606266;
}
.content {
  flex: 1;
  padding: 24px;
  min-width: 0;
}
.loading {
  color: #909399;
}
</style>
