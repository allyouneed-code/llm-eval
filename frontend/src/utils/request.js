import axios from 'axios'

// 1. 创建 axios 实例
const service = axios.create({
  // 从环境变量获取 baseURL
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api', 
  timeout: 10000 // 请求超时时间
})

// 2. 请求拦截器 (Request Interceptor)
service.interceptors.request.use(
  config => {
    // 从 localStorage 获取 Token
    const token = sessionStorage.getItem('token')
    if (token) {
      // 如果存在 Token，则添加到 Header 中
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.log(error) 
    return Promise.reject(error)
  }
)

// 3. 响应拦截器 (Response Interceptor)
service.interceptors.response.use(
  response => {
    const res = response.data
    // 这里可以根据后端的通用返回格式进行处理
    // 如果直接返回数据对象，则直接返回 res
    return res
  },
  error => {
    console.error('API Error:', error)
    
    // 如果遇到 401 Unauthorized，说明 Token 过期或无效
    if (error.response && error.response.status === 401) {
      // 清除本地 Token
      sessionStorage.removeItem('token')
      // 强制跳转到登录页 (避免无限循环，先判断当前是否已经在登录页)
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
    }
    
    // 提取错误信息
    const errMsg = error.response?.data?.detail || error.message || 'Error'
    // 这里可以接入 ElementPlus 的 ElMessage.error(errMsg)
    alert(errMsg) // 暂时用 alert 替代
    
    return Promise.reject(error)
  }
)

export default service