<template>
  <div class="login-container">
    <div class="login-card">
      <h2>🔐 LLM Eval Platform</h2>
      <p class="subtitle">请登录以继续</p>
      
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>用户名</label>
          <input 
            v-model="username" 
            type="text" 
            required 
            placeholder="请输入用户名"
            class="input-field"
          />
        </div>
        
        <div class="form-group">
          <label>密码</label>
          <input 
            v-model="password" 
            type="password" 
            required 
            placeholder="请输入密码"
            class="input-field"
          />
        </div>

        <div v-if="errorMsg" class="error-msg">
          {{ errorMsg }}
        </div>
        
        <button type="submit" :disabled="loading" class="login-btn">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

const handleLogin = async () => {
  if (!username.value || !password.value) return
  
  loading.value = true
  errorMsg.value = ''
  
  try {
    // FastAPI OAuth2 标准要求的 form-data 格式
    const formData = new FormData()
    formData.append('username', username.value)
    formData.append('password', password.value)

    const res = await request.post('v1/auth/login', formData)
    
    // 使用 sessionStorage (关闭浏览器即自动退出)
    sessionStorage.setItem('token', res.access_token)
    
    // 跳转回首页
    router.push('/')
    
  } catch (err) {
    console.error(err)
    errorMsg.value = '登录失败：用户名或密码错误'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f0f2f5;
}

.login-card {
  background: white;
  padding: 2.5rem 3rem;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  width: 100%;
  max-width: 400px;
  text-align: center;
}

h2 { margin-bottom: 0.5rem; color: #333; }
.subtitle { color: #888; margin-bottom: 2rem; font-size: 0.95rem; }

.form-group { margin-bottom: 1.5rem; text-align: left; }
label { display: block; margin-bottom: 0.5rem; color: #333; font-weight: 500; }

.input-field {
  width: 100%;
  padding: 0.8rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 1rem;
  box-sizing: border-box; 
  transition: border-color 0.3s;
}
.input-field:focus { border-color: #409eff; outline: none; }

.login-btn {
  width: 100%;
  padding: 0.8rem;
  background-color: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.3s;
  font-weight: 600;
  margin-top: 0.5rem;
}
.login-btn:hover { background-color: #66b1ff; }
.login-btn:disabled { background-color: #a0cfff; cursor: not-allowed; }

.error-msg {
  color: #f56c6c;
  background: #fef0f0;
  padding: 0.5rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}
</style>