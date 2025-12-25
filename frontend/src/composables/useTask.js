// src/composables/useTask.js
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { getTasks } from '@/api/task'
import { getModels } from '@/api/model'
import { getDatasets } from '@/api/dataset'

export function useTaskData() {
  const taskList = ref([])
  const modelList = ref([])
  const datasetList = ref([]) // 原始数据集列表
  
  // === 新增：分页状态 ===
  const pagination = reactive({
    currentPage: 1,
    pageSize: 10,
    total: 0
  })
  
  let pollingTimer = null

  // 1. 获取任务列表 (轮询用)
  const fetchTasks = async () => {
    try {
      // 修改：传入分页参数
      const res = await getTasks({
        page: pagination.currentPage,
        page_size: pagination.pageSize
      })
      
      // 修改：适配后端分页返回结构 { items: [], total: 100 }
      // 为了兼容性，先判断是否有 items 字段
      if (res.items) {
        taskList.value = res.items
        pagination.total = res.total
      } else {
        // 兼容旧接口直接返回数组的情况
        taskList.value = res
      }
      
      // 移除：taskList.value = data.sort(...) 
      // 后端 API 已经做了 order_by(desc)，前端直接展示即可
    } catch (e) {
      console.error('Fetch tasks failed', e)
    }
  }

  // === 新增：分页事件处理 ===
  const handlePageChange = (page) => {
    pagination.currentPage = page
    fetchTasks()
  }

  const handleSizeChange = (size) => {
    pagination.pageSize = size
    pagination.currentPage = 1 // 切换每页大小时重置回第一页
    fetchTasks()
  }

  // 2. 获取基础元数据 (模型 + 数据集)
  // 这些数据主要用于：表格渲染(ID转Name) 和 创建任务弹窗
  const fetchBasicData = async () => {
    try {
      const [models, datasetsData] = await Promise.all([
        getModels(),
        getDatasets({ page_size: 10000 }) 
      ])
      
      modelList.value = models
      
      const rawItems = datasetsData.items || []
      // 预处理 is_system 标记
      datasetList.value = rawItems.map(meta => ({
        ...meta,
        is_system: meta.configs?.some(c => c.file_path && c.file_path.includes('official://')) 
                   || ['GSM8K', 'MMLU', 'C-Eval'].some(k => meta.name.includes(k))
      }))
    } catch (e) {
      console.error('Fetch basic data failed', e)
    }
  }

  // 3. 启动轮询
  const startPolling = (interval = 3000) => {
    fetchTasks()
    pollingTimer = setInterval(fetchTasks, interval)
  }

  const stopPolling = () => {
    if (pollingTimer) clearInterval(pollingTimer)
  }

  onMounted(() => {
    fetchBasicData()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    taskList,
    modelList,
    datasetList,
    pagination,       // 导出
    handlePageChange, // 导出
    handleSizeChange, // 导出
    fetchTasks,
    fetchBasicData
  }
}