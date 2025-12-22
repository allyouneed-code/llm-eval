import request from '@/utils/request'

// 这里的 URL 不需要加 /api/v1，因为 baseURL 已经在 request.js 里配置好了
const URL = '/v1/models'

// 1. 获取模型列表
export function getModels() {
  return request.get(URL + '/')
}

// 2. 创建模型
export function createModel(data) {
  return request.post(URL + '/', data)
}

// 3. 删除模型
export function deleteModel(id) {
  return request.delete(URL + `/${id}`)
}

// 4. 校验模型名称是否重复
export function validateModelName(name) {
  return request.post(URL + '/validate/name', { name })
}