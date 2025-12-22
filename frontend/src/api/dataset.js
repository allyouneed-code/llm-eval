import request from '@/utils/request'

const URL = '/v1/datasets'

// 1. 获取统计信息
export function getDatasetStats() {
  return request.get(URL + '/stats')
}

// 2. 获取数据集列表 (原样接收 params: page, page_size, category...)
export function getDatasets(params) {
  return request.get(URL + '/', { params })
}

// 3. 预览文件内容 (用于上传前的解析预览)
export function previewDatasetFile(formData) {
  return request.post(URL + '/preview', formData)
}

// 4. 创建数据集 (上传)
export function createDataset(formData) {
  return request.post(URL + '/', formData)
}

// 5. 获取已保存数据集的预览
export function getSavedDatasetPreview(id) {
  return request.get(URL + `/${id}/preview`)
}

// 6. 删除数据集
export function deleteDataset(id) {
  return request.delete(URL + `/${id}`)
}

// 7. 获取下载链接 (这是一个辅助函数，不是 Promise 请求)
// 配合 request.js 中的 baseURL 使用
export function getDownloadUrl(id) {
  // 假设 baseURL 是 /api/v1，这里手动拼接
  // 如果你的 baseURL 是动态的，这里可能需要调整，但通常 /api/v1 是固定的
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  // 去掉末尾的斜杠防止双斜杠
  const cleanBase = baseURL.endsWith('/') ? baseURL.slice(0, -1) : baseURL
  return `${cleanBase}/datasets/${id}/download`
}