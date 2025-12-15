<template>
  <div style="text-align: center; margin-top: 50px;">
    <h1>OpenCompass Platform</h1>
    <el-button type="primary" @click="testBackend">测试后端连接</el-button>
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const message = ref('')

const testBackend = async () => {
  try {
    // 这里会自动走 vite.config.js 配置的代理
    const res = await axios.get('/api/') 
    message.value = res.data.message
  } catch (error) {
    message.value = '连接失败: ' + error
  }
}
</script>