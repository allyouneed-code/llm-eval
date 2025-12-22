// src/composables/useDataset.js
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDatasets, getDatasetStats, deleteDataset } from '@/api/dataset'

export function useDatasetList() {
  const tableData = ref([])
  const totalItems = ref(0)
  const loading = ref(false)
  const categoryStats = ref([])

  // 筛选状态
  const filter = ref({
    page: 1,
    pageSize: 10,
    category: 'All',
    keyword: '',
    privateOnly: false
  })

  // 1. 获取统计信息
  const fetchStats = async () => {
    try {
      const data = await getDatasetStats()
      categoryStats.value = data
    } catch (e) {
      console.error(e)
    }
  }

  // 2. 获取列表 (包含 is_system 逻辑处理)
  const fetchData = async () => {
    loading.value = true
    try {
      const params = {
        page: filter.value.page,
        page_size: filter.value.pageSize,
        category: filter.value.category,
        keyword: filter.value.keyword || undefined,
        private_only: filter.value.privateOnly
      }

      const data = await getDatasets(params)
      totalItems.value = data.total
      
      // 处理 is_system 标记
      tableData.value = data.items.map(d => {
        let isSystem = true
        if (!d.configs || d.configs.length === 0) {
          isSystem = false 
        } else {
          const path = d.configs[0].file_path || ''
          if (path.includes('data/datasets') || path.includes('data\\datasets')) {
            isSystem = false
          }
        }
        return { ...d, is_system: isSystem }
      })
    } catch (error) {
      ElMessage.error('获取数据集列表失败')
    } finally {
      loading.value = false
    }
  }

  // 3. 删除逻辑
  const handleDelete = (row) => {
    ElMessageBox.confirm(`确定要删除数据集 "${row.name}" 吗?`, '警告', { type: 'warning' })
      .then(async () => {
        await deleteDataset(row.id)
        ElMessage.success('删除成功')
        fetchStats() // 刷新统计
        fetchData()  // 刷新列表
      })
      .catch(() => {})
  }

  // 监听筛选变化 (分页、分类、只看私有)
  watch(
    () => [filter.value.page, filter.value.pageSize, filter.value.category, filter.value.privateOnly],
    () => fetchData()
  )

  // 辅助函数：解析配置 tags
  const parseConfigInfo = (cfg) => {
    let evaluator = 'Unknown'
    let isLLM = false
    try {
      const mCfg = JSON.parse(cfg.metric_config)
      const eType = mCfg.evaluator?.type || mCfg.evaluator || ''
      evaluator = eType.replace('Evaluator', '') 
      if (evaluator.toLowerCase().includes('llm') || evaluator.toLowerCase().includes('judge')) {
        isLLM = true
      }
    } catch (e) { }
    return { evaluator, isLLM }
  }

  // 初始化
  onMounted(() => {
    fetchStats()
    fetchData()
  })

  return {
    tableData,
    totalItems,
    loading,
    categoryStats,
    filter,
    fetchData,
    fetchStats,
    handleDelete,
    parseConfigInfo
  }
}