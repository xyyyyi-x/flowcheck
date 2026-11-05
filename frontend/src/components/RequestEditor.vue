<script setup lang="ts">
import type { EditableStep } from "../utils/caseEditor";

defineProps<{ step: EditableStep }>();
const methods = ["GET", "POST", "PUT", "PATCH", "DELETE"];
</script>

<template>
  <div class="editor">
    <div class="grid">
      <label>
        步骤名称
        <el-input v-model="step.name" maxlength="80" />
      </label>
      <label>
        方法
        <el-select v-model="step.method" style="width: 100%">
          <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
        </el-select>
      </label>
      <label>
        相对路径
        <el-input v-model="step.path" placeholder="/articles/{id}" />
      </label>
      <label>
        超时（秒）
        <el-input-number v-model="step.timeout_s" :min="1" :max="30" style="width: 100%" />
      </label>
    </div>
    <label>
      path_params（JSON 对象；值可为 <code v-pre>{{变量}}</code>）
      <el-input v-model="step.path_params_text" type="textarea" :rows="3" />
    </label>
    <label>
      query（JSON 对象）
      <el-input v-model="step.query_text" type="textarea" :rows="3" />
    </label>
    <label>
      headers（JSON 对象，值可含模板）
      <el-input v-model="step.headers_text" type="textarea" :rows="3" />
    </label>
    <label>
      JSON body（留空表示无 body；整段模板保留原生类型）
      <el-input v-model="step.body_text" type="textarea" :rows="5" />
    </label>
    <el-checkbox v-model="step.omit_response_body">报告中省略响应正文（登录步骤建议勾选）</el-checkbox>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 140px 1fr 120px;
  gap: 8px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: #606266;
}
code {
  background: #f5f7fa;
  padding: 0 3px;
}
</style>
