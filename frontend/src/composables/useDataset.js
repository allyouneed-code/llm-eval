// src/composables/useDataset.js
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDatasets, getDatasetStats, deleteDataset } from '@/api/dataset'

export function useDatasetList() {
  const tableData = ref([])
  const totalItems = ref(0)
  const loading = ref(false)
  const categoryStats = ref([])
  
  // 🆕 新增：总题量状态
  const totalQuestions = ref(0)
  const sortState = ref({
    prop: '', 
    order: '' // 'ascending' | 'descending' | null
  })

  // 筛选状态
  const filter = ref({
    page: 1,
    pageSize: 10,
    category: 'All',
    keyword: '',
    privateOnly: false
  })

  // 1. 获取统计信息 (兼容新旧 API 结构)
  const fetchStats = async () => {
    try {
      const data = await getDatasetStats()
      
      // 检查返回结构
      if (Array.isArray(data)) {
        // 旧结构 (List)
        categoryStats.value = data
        totalQuestions.value = 0
      } else {
        // 新结构 (Object): { categories: [], total_questions: 123 }
        categoryStats.value = data.categories || []
        totalQuestions.value = data.total_questions || 0
      }
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
        private_only: filter.value.privateOnly,
        // 🆕 注入排序参数
        sort_prop: sortState.value.prop || undefined,
        sort_order: sortState.value.order || undefined
      }

      const data = await getDatasets(params)
      // ... (后续数据处理逻辑保持不变)
      totalItems.value = data.total
      tableData.value = data.items.map(d => {
         // ... (is_system 处理逻辑)
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

  const handleSortChange = ({ prop, order }) => {
    sortState.value.prop = prop
    sortState.value.order = order
    // 排序变化时，通常建议重置到第一页
    filter.value.page = 1 
    fetchData()
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

  // 监听筛选变化
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
    totalQuestions, // 导出
    filter,
    fetchData,
    fetchStats,
    handleSortChange,
    handleDelete,
    parseConfigInfo
  }
}