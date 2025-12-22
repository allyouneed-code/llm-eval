// src/composables/useTask.js
import { ref, onMounted, onUnmounted } from 'vue'
import { getTasks } from '@/api/task'
import { getModels } from '@/api/model'
import { getDatasets } from '@/api/dataset'

export function useTaskData() {
  const taskList = ref([])
  const modelList = ref([])
  const datasetList = ref([]) // 原始数据集列表
  
  let pollingTimer = null

  // 1. 获取任务列表 (轮询用)
  const fetchTasks = async () => {
    try {
      const data = await getTasks()
      // 按 ID 倒序
      taskList.value = data.sort((a, b) => b.id - a.id)
    } catch (e) {
      console.error('Fetch tasks failed', e)
    }
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
    fetchTasks,
    fetchBasicData
  }
}