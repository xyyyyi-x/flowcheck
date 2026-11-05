<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { describeError } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const submitting = ref(false);

async function submit(): Promise<void> {
  error.value = "";
  if (!username.value.trim() || !password.value) {
    error.value = "请输入用户名和密码";
    return;
  }
  submitting.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    const redirect = String(route.query.redirect ?? "/projects");
    await router.replace(redirect);
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
      <h1>登录</h1>
      <p class="sub">接口回归测试平台</p>
      <label>用户名</label>
      <el-input v-model="username" autocomplete="username" placeholder="3-32 位字母数字下划线" />
      <label>密码</label>
      <el-input
        v-model="password"
        type="password"
        autocomplete="current-password"
        placeholder="至少 8 位"
        show-password
      />
      <el-alert v-if="error" type="error" :title="error" :closable="false" />
      <el-button type="primary" native-type="submit" :loading="submitting">
        {{ submitting ? "登录中…" : "登录" }}
      </el-button>
      <router-link to="/auth/register">没有账号？注册</router-link>
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
