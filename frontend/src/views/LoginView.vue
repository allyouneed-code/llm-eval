<template>
  <div class="login-container">
    <div class="login-content">
      <div class="login-header">
        <div class="logo-icon">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <h1 class="app-title">LLM Eval Platform</h1>
        <p class="app-subtitle">大语言模型评测与管理系统</p>
      </div>

      <el-card class="login-card" shadow="always">
        <h2 class="login-title">欢迎登录</h2>
        
        <el-form 
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="login-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username">
            <el-input 
              v-model="loginForm.username" 
              placeholder="请输入用户名"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input 
              v-model="loginForm.password" 
              type="password" 
              placeholder="请输入密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <div v-if="errorMsg" class="error-msg">
            <el-icon><Warning /></el-icon>
            <span>{{ errorMsg }}</span>
          </div>
          
          <el-button 
            type="primary" 
            :loading="loading" 
            class="login-btn" 
            size="large"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form>
      </el-card>

      <div class="footer-copyright">
        © {{ new Date().getFullYear() }} LLM Eval Team. All Rights Reserved.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, DataAnalysis, Warning } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()
const loginFormRef = ref(null)

// 使用 reactive 管理表单数据
const loginForm = reactive({
  username: '',
  password: ''
})

// 表单验证规则
const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const loading = ref(false)
const errorMsg = ref('')

const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  // 1. 校验表单
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      errorMsg.value = ''
      
      try {
        const formData = new FormData()
        formData.append('username', loginForm.username)
        formData.append('password', loginForm.password)

        const res = await request.post('v1/auth/login', formData)
        
        // 保存 Token 和 用户名
        sessionStorage.setItem('token', res.access_token)
        sessionStorage.setItem('username', loginForm.username)
        
        router.push('/')
        
      } catch (err) {
        console.error(err)
        errorMsg.value = '登录失败：用户名或密码错误'
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  /* 使用深色渐变背景，更显专业 */
  background: linear-gradient(135deg, #2b3a4d 0%, #1f2937 100%);
  position: relative;
  overflow: hidden;
}

/* 添加一些背景装饰圆 */
.login-container::before {
  content: '';
  position: absolute;
  top: -100px;
  right: -100px;
  width: 400px;
  height: 400px;
  background: rgba(64, 158, 255, 0.1);
  border-radius: 50%;
  filter: blur(80px);
}
.login-container::after {
  content: '';
  position: absolute;
  bottom: -100px;
  left: -100px;
  width: 300px;
  height: 300px;
  background: rgba(64, 158, 255, 0.05);
  border-radius: 50%;
  filter: blur(60px);
}

.login-content {
  width: 100%;
  max-width: 420px;
  padding: 20px;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
  color: #fff;
}

.logo-icon {
  font-size: 48px;
  margin-bottom: 10px;
  color: #409EFF;
  display: inline-block;
}

.app-title {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 1px;
}

.app-subtitle {
  margin: 10px 0 0;
  font-size: 14px;
  opacity: 0.8;
  font-weight: 300;
}

.login-card {
  width: 100%;
  border-radius: 12px;
  /* 毛玻璃效果微调 */
  background: rgba(255, 255, 255, 0.98);
  border: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2) !important;
}

.login-title {
  text-align: center;
  margin: 10px 0 30px;
  font-size: 20px;
  color: #303133;
  font-weight: 600;
}

.login-form :deep(.el-input__wrapper) {
  padding: 8px 15px; /* 增加输入框高度 */
  border-radius: 8px;
}

.login-btn {
  width: 100%;
  margin-top: 10px;
  padding: 22px 0; /* 加大按钮点击区域 */
  font-size: 16px;
  border-radius: 8px;
  font-weight: 500;
  letter-spacing: 2px;
  transition: all 0.3s;
}

.login-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #f56c6c;
  background: #fef0f0;
  padding: 10px 15px;
  border-radius: 6px;
  margin-bottom: 20px;
  font-size: 13px;
  border: 1px solid #fde2e2;
}

.footer-copyright {
  margin-top: 40px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
  text-align: center;
}
</style>