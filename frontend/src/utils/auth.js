/**
 * 解析 Token 获取用户角色
 * @returns {string|null} 'admin' | 'user' | null
 */
export function getUserRole() {
  const token = sessionStorage.getItem('token')
  if (!token) return null

  try {
    const parts = token.split('.')
    let payload = ''

    if (parts.length === 2) {
      // 对应后端 security_lite.py 生成的 Payload.Signature 格式
      payload = parts[0]
    } else if (parts.length === 3) {
      // 对应标准 JWT 格式 Header.Payload.Signature
      payload = parts[1]
    } else {
      console.warn('Token 格式不正确，既不是2段也不是3段')
      return null
    }

    // Base64Url 解码处理
    payload = payload.replace(/-/g, '+').replace(/_/g, '/')
    
    // 补全 padding
    const pad = payload.length % 4
    if (pad) {
      payload += new Array(5 - pad).join('=')
    }
    
    const decodedStr = window.atob(payload)
    const decoded = JSON.parse(decodeURIComponent(escape(decodedStr)))
    
    // 🌟 调试日志：打开浏览器控制台(F12)查看输出
    console.log('Token解析结果:', decoded)
    console.log('当前用户角色:', decoded.role)

    return decoded.role 
  } catch (e) {
    console.error('Token解析失败', e)
    return null
  }
}

export function isAdmin() {
  return getUserRole() === 'admin'
}