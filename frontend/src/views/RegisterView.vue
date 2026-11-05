<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { describeError } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const username = ref("");
const password = ref("");
const confirm = ref("");
const error = ref("");
const submitting = ref(false);

async function submit(): Promise<void> {
  error.value = "";
  if (!/^[A-Za-z0-9_]{3,32}$/.test(username.value.trim())) {
    error.value = "用户名需为 3-32 位字母、数字或下划线";
    return;
  }
  if (password.value.length < 8 || password.value.length > 128) {
    error.value = "密码长度需为 8-128 位";
    return;
  }
  if (password.value !== confirm.value) {
    error.value = "两次输入的密码不一致";
    return;
  }
  submitting.value = true;
  try {
    await auth.register(username.value.trim(), password.value);
    await router.replace({ name: "projects" });
  } catch (caught) {
    error.value = describeError(caught);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="auth-page">
    <form class="card" @submit.prevent="submit">
      <h1>注册</h1>
      <p class="sub">注册后将自动登录</p>
      <label>用户名</label>
      <el-input v-model="username" autocomplete="username" />
      <label>密码</label>
      <el-input v-model="password" type="password" autocomplete="new-password" show-password />
      <label>确认密码</label>
      <el-input v-model="confirm" type="password" autocomplete="new-password" show-password />
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <el-button type="primary" native-type="submit" :loading="submitting">
        {{ submitting ? "注册中…" : "注册并登录" }}
      </el-button>
      <router-link to="/auth/login">已有账号？登录</router-link>
    </form>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.card {
  width: 360px;
  background: #fff;
  padding: 32px;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgb(0 0 0 / 8%);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
h1 {
  margin: 0;
  font-size: 22px;
}
.sub {
  margin: 0 0 8px;
  color: #909399;
  font-size: 13px;
}
label {
  font-size: 13px;
  color: #606266;
}
a {
  font-size: 13px;
  color: #409eff;
  text-align: center;
}
</style>
