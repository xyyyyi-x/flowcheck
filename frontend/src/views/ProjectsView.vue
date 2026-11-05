<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { describeError } from "../api/client";
import { createProject, listProjects } from "../api/projects";
import type { Project } from "../api/types";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const projects = ref<Project[]>([]);
const total = ref(0);
const loading = ref(true);
const error = ref("");
const creating = ref(false);
const submitting = ref(false);
const form = ref({ name: "", description: "" });

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const page = await listProjects();
    projects.value = page.items;
    total.value = page.total;
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  error.value = "";
  if (!form.value.name.trim()) {
    error.value = "项目名称不能为空";
    return;
  }
  submitting.value = true;
  try {
    const project = await createProject(form.value.name.trim(), form.value.description.trim());
    creating.value = false;
    form.value = { name: "", description: "" };
    await router.push(`/projects/${project.id}/overview`);
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    submitting.value = false;
  }
}

function logout(): void {
  auth.logout();
  router.replace({ name: "login" });
}

onMounted(load);
</script>

<template>
  <div class="page">
    <header class="header">
      <div>
        <h1>我的项目</h1>
        <p class="sub">{{ auth.user?.username }} · 共 {{ total }} 个项目</p>
      </div>
      <div class="actions">
        <el-button type="primary" @click="creating = true">新建项目</el-button>
        <el-button link @click="logout">退出登录</el-button>
      </div>
    </header>

    <el-alert v-if="error" type="error" :title="error" :closable="false" />

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="projects.length === 0" class="state">
      还没有项目。点击“新建项目”开始配置接口回归。
    </div>
    <div v-else class="grid">
      <router-link
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        :to="`/projects/${project.id}/overview`"
      >
        <h2>{{ project.name }}</h2>
        <p>{{ project.description || "暂无描述" }}</p>
        <span class="meta">创建于 {{ new Date(project.created_at).toLocaleString() }}</span>
      </router-link>
    </div>

    <el-dialog v-model="creating" title="新建项目" width="420px">
      <div class="form">
        <label>项目名称</label>
        <el-input v-model="form.name" maxlength="80" show-word-limit />
        <label>描述</label>
        <el-input
          v-model="form.description"
          type="textarea"
          maxlength="500"
          show-word-limit
        />
      </div>
      <template #footer>
        <el-button @click="creating = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 24px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
h1 {
  margin: 0;
  font-size: 22px;
}
.sub {
  margin: 6px 0 0;
  color: #909399;
  font-size: 13px;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.state {
  padding: 48px;
  text-align: center;
  color: #909399;
  background: #fff;
  border-radius: 8px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.project-card {
  display: block;
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  color: inherit;
  text-decoration: none;
  border: 1px solid #ebeef5;
}
.project-card:hover {
  border-color: #409eff;
}
h2 {
  margin: 0 0 8px;
  font-size: 16px;
}
.project-card p {
  margin: 0 0 12px;
  color: #606266;
  font-size: 13px;
  min-height: 20px;
}
.meta {
  color: #a8abb2;
  font-size: 12px;
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
</style>
