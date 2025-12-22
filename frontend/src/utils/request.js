import axios from 'axios'

// 1. 创建 axios 实例
const service = axios.create({
  // 从环境变量获取 baseURL
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api', 
  timeout: 10000 // 请求超时时间
})

// 2. 请求拦截器 (Request Interceptor)
service.interceptors.request.use(
  (config) => {
    // 如果将来有登录功能，在这里统一加 Token
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers['Authorization'] = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 3. 响应拦截器 (Response Interceptor)
service.interceptors.response.use(
  (response) => {
    // 2xx 范围内的状态码都会触发该函数
    return response.data
  },
  (error) => {
    // 超出 2xx 范围的状态码都会触发该函数
    const { response } = error
    
    // 统一错误提示 (这里假设你用了 Naive UI 或 Element Plus，没用的话可以用 console.error)
    if (response) {
      // 获取后端返回的错误信息 detail
      const errorMsg = response.data?.detail || '系统服务异常'
      console.error(`[API Error] ${response.status}: ${errorMsg}`)
      
      // 可以在这里根据 status 做跳转，比如 401 去登录页
      // if (response.status === 401) { ... }
    } else {
      console.error('[API Error] 网络连接失败')
    }
    
    return Promise.reject(error)
  }
)

export default service