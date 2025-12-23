import request from '@/utils/request'

const URL = '/v1/tasks'

// 1. 获取任务列表
export function getTasks() {
  return request.get(URL + '/')
}

// 2. 创建评测任务
export function createTask(data) {
  // data 结构: { model_id: 1, config_ids: [1, 2] }
  return request.post(URL + '/', data)
}

// 3. 获取单任务详情 (虽然目前列表页包含了大部分信息，但详情页将来可能需要独立拉取)
export function getTask(id) {
  return request.get(URL + `/${id}`)
}

// 4. 删除任务
export function deleteTask(id) {
  return request.delete(URL + `/${id}`)
}