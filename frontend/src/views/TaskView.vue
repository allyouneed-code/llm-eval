<script setup>
import { ref, onMounted, reactive, nextTick, computed, onUnmounted, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { 
  VideoPlay, Refresh, Folder, Search, 
  MagicStick, Collection, Monitor, Lock, DataLine,
  Medal, User, Odometer, Setting, Filter 
} from '@element-plus/icons-vue'

// === 1. 数据定义 ===
const tableData = ref([])
const modelList = ref([])
const datasetMetas = ref([]) 

const createDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const currentTask = ref(null) 
const submitting = ref(false)
const terminalLogs = ref([])
let logInterval = null

// 加载状态
const isDataLoading = ref(false) // 弹窗内的加载状态

// 表单数据
const form = reactive({
  model_id: null,
  config_ids: [] 
})

// UI 辅助状态
const selectedMetaMap = reactive({})
const selectedConfigMap = reactive({})
const activeNames = ref([]) 
const searchText = ref('')
const showPrivateOnly = ref(false)
const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 2. 核心计算属性 ===

const selectedModelInfo = computed(() => {
  if (!form.model_id) return null
  return modelList.value.find(m => m.id === form.model_id)
})

const filteredGroupedMetas = computed(() => {
  const groups = {}
  if (!datasetMetas.value.length) return groups
  
  const keyword = searchText.value.toLowerCase().trim()
  
  const filtered = datasetMetas.value.filter(meta => {
    if (showPrivateOnly.value && meta.is_system) {
      return false
    }

    if (!keyword) return true
    return meta.name.toLowerCase().includes(keyword) || 
           meta.category.toLowerCase().includes(keyword)
  })

  filtered.forEach(meta => {
    const cap = meta.category || 'Others'
    if (!groups[cap]) groups[cap] = []
    groups[cap].push(meta)
  })
  
  return groups
})

// === 3. 监听与交互逻辑 ===

watch(searchText, (newVal) => {
  if (newVal.trim()) {
    activeNames.value = Object.keys(filteredGroupedMetas.value)
  }
})

watch(showPrivateOnly, () => {
   activeNames.value = Object.keys(filteredGroupedMetas.value)
})

const handleMetaCheckChange = (meta, isChecked) => {
  if (isChecked) {
    if (!selectedConfigMap[meta.id] && meta.configs.length > 0) {
      selectedConfigMap[meta.id] = meta.configs[0].id
    }
  }
  syncToForm()
}

const handleConfigChange = (metaId, newConfigId) => {
  if (selectedMetaMap[metaId]) {
    syncToForm()
  }
}

const syncToForm = () => {
  const ids = []
  for (const [metaId, isChecked] of Object.entries(selectedMetaMap)) {
    if (isChecked) {
      const configId = selectedConfigMap[metaId]
      if (configId) {
        ids.push(configId)
      }
    }
  }
  form.config_ids = ids
}

// === 4. 辅助函数 ===

const getCapIcon = (cap) => {
  const map = { 'Reasoning': MagicStick, 'Knowledge': Collection, 'Coding': Monitor, 'Safety': Lock }
  for (const key in map) { if (cap && cap.includes(key)) return map[key] }
  return DataLine
}

const getCapColor = (cap) => {
  if (!cap) return '#909399'
  let hash = 0
  for (let i = 0; i < cap.length; i++) {
    hash = cap.charCodeAt(i) + ((hash << 5) - hash)
  }
  const h = Math.abs(hash) % 360
  const s = 65 + (Math.abs(hash) % 20) 
  const l = 40 + (Math.abs(hash) % 15)
  return `hsl(${h}, ${s}%, ${l}%)`
}

const getModelName = (id) => {
  const found = modelList.value.find(m => m.id === id)
  return found ? found.name : `Model-${id}`
}

const parseJSON = (jsonStr) => {
  try { return JSON.parse(jsonStr) } catch { return [] }
}

const getStatusType = (status) => {
  const map = { pending: 'info', running: 'primary', success: 'success', failed: 'danger' }
  return map[status] || 'info'
}

const getTaskDatasetDisplay = (taskRow) => {
  // 如果 datasetMetas 还没加载（比如刚打开页面），这里可能会空，但这不影响
  const configIds = parseJSON(taskRow.datasets_list)
  if (!configIds.length) return []
  
  const displayItems = []
  configIds.forEach(cid => {
    for (const meta of datasetMetas.value) {
      const foundCfg = meta.configs.find(c => c.id === cid)
      if (foundCfg) {
        displayItems.push({
          cap: meta.category,
          label: `${meta.name} (${foundCfg.mode})`,
          mode: foundCfg.mode
        })
        break
      }
    }
  })
  
  const grouped = {}
  displayItems.forEach(item => {
    if (!grouped[item.cap]) grouped[item.cap] = []
    grouped[item.cap].push(item)
  })
  return grouped
}


// === 5. 数据交互 (核心优化部分) ===

// 5.1 只拉取任务列表 (用于高频轮询)
const fetchTasksOnly = async () => {
  try {
    const res = await axios.get(`${API_BASE}/tasks/`)
    tableData.value = res.data.sort((a, b) => b.id - a.id)
  } catch (e) { console.error(e) }
}

// 5.2 拉取基础数据 (模型+数据集)
const fetchBasicData = async () => {
  try {
    const [modelRes, datasetRes] = await Promise.all([
      axios.get(`${API_BASE}/models/`),
      axios.get(`${API_BASE}/datasets/`, { params: { page_size: 10000 } }) 
    ])
    
    modelList.value = modelRes.data
    
    const rawItems = datasetRes.data.items || [] 
    datasetMetas.value = rawItems.map(meta => ({
      ...meta,
      is_system: meta.configs?.some(c => c.file_path && c.file_path.includes('official://')) 
                 || ['GSM8K', 'MMLU', 'C-Eval'].some(k => meta.name.includes(k))
    }))
    
    // 初始化默认选中
    datasetMetas.value.forEach(meta => {
      if (meta.configs && meta.configs.length > 0) {
        selectedConfigMap[meta.id] = meta.configs[0].id
      }
    })
  } catch (error) {
    ElMessage.error('基础数据加载失败')
  }
}

// 5.3 页面初始化 (全量)
const initPageData = async () => {
   await Promise.all([fetchTasksOnly(), fetchBasicData()])
}

// 🌟 核心优化：打开弹窗时不阻塞，而是异步加载
const handleOpenCreate = () => {
  // 1. 先重置状态
  searchText.value = '' 
  showPrivateOnly.value = false 
  form.model_id = null
  form.config_ids = []
  Object.keys(selectedMetaMap).forEach(k => selectedMetaMap[k] = false)
  
  // 2. 立即显示弹窗
  createDialogVisible.value = true
  isDataLoading.value = true

  // 3. 异步延迟请求数据 (给 Vue 渲染弹窗的时间)
  setTimeout(async () => {
    try {
      await fetchBasicData() // 刷新模型和数据集
      
      // 自动展开
      if (activeNames.value.length === 0 && Object.keys(filteredGroupedMetas.value).length > 0) {
        activeNames.value = Object.keys(filteredGroupedMetas.value)
      }
    } finally {
      isDataLoading.value = false
    }
  }, 100)
}

const handleSubmit = async () => {
  if (!form.model_id || form.config_ids.length === 0) return ElMessage.warning('请至少选择一个模型和一个评测配置')
  
  submitting.value = true
  try {
    await axios.post(`${API_BASE}/tasks/`, {
      model_id: form.model_id,
      config_ids: form.config_ids
    })
    ElMessage.success('🚀 评测任务已启动')
    createDialogVisible.value = false
    fetchTasksOnly() // 提交后刷新列表
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

// ... 详情页逻辑保持不变 ...
const handleViewDetail = (row) => {
  currentTask.value = row
  detailDrawerVisible.value = true
  if (row.status === 'running' || row.status === 'pending') startFakeLogs()
  else if (row.status === 'success') nextTick(() => initRadarChart())
}

const startFakeLogs = () => {
  terminalLogs.value = ['> System init...']
  if (logInterval) clearInterval(logInterval)
  const logPool = ['Loading weights...', 'Allocating GPU...', 'Inference batch...', 'Calculating metrics...']
  logInterval = setInterval(() => {
    if (currentTask.value?.status !== 'running') { clearInterval(logInterval); return }
    const msg = logPool[Math.floor(Math.random() * logPool.length)]
    terminalLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
    const terminal = document.getElementById('terminal-box')
    if(terminal) terminal.scrollTop = terminal.scrollHeight
  }, 1500)
}

const initRadarChart = () => {
  const chartDom = document.getElementById('result-radar')
  if (!chartDom || !currentTask.value.result_summary) return
  let resultObj = {}
  try { resultObj = JSON.parse(currentTask.value.result_summary) } catch(e) { return }
  if(!resultObj.radar) return
  const myChart = echarts.init(chartDom)
  const option = {
    tooltip: {},
    radar: { indicator: resultObj.radar.map(r => ({ name: r.name, max: r.max })), radius: '65%' },
    series: [{ type: 'radar', data: [{ value: resultObj.radar.map(r => r.score), name: 'Model Score', itemStyle: { color: '#409EFF' }, areaStyle: { opacity: 0.2 } }] }]
  }
  myChart.setOption(option)
  window.addEventListener('resize', () => myChart.resize())
}

const taskResult = computed(() => {
  if (!currentTask.value?.result_summary) return null
  try { return JSON.parse(currentTask.value.result_summary) } catch { return null }
})

// === 7. 生命周期 ===
let pollingTimer = null

onMounted(() => {
  initPageData()
  // 🌟 轮询改为只拉取 Task 列表，极大减轻负载
  pollingTimer = setInterval(fetchTasksOnly, 3000)
})

onUnmounted(() => {
  if (pollingTimer) clearInterval(pollingTimer)
  if (logInterval) clearInterval(logInterval)
})
</script>

<template>
  <div class="task-view">
    <div class="header-actions">
      <el-button type="primary" size="large" @click="handleOpenCreate" class="create-btn">
        <el-icon class="mr-1"><VideoPlay /></el-icon> 新建评测任务
      </el-button>
      <el-button :icon="Refresh" circle @click="initPageData" />
    </div>

    <el-table :data="tableData" border style="width: 100%" stripe highlight-current-row class="main-table">
      <el-table-column prop="id" label="ID" width="70" align="center" sortable />
      <el-table-column label="模型 (Model)" min-width="140">
        <template #default="scope">
          <div style="font-weight:600">{{ getModelName(scope.row.model_id) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="评测配置 (Content)" min-width="320">
        <template #default="scope">
          <div class="content-container">
            <div v-for="(items, cap) in getTaskDatasetDisplay(scope.row)" :key="cap" class="cap-row">
              <div class="cap-header" :style="{ color: getCapColor(cap) }">
                <el-icon class="cap-icon"><component :is="getCapIcon(cap)" /></el-icon>
                <span class="cap-name">{{ cap }}</span>
              </div>
              <div class="ds-list">
                <el-tag 
                  v-for="(item, idx) in items" 
                  :key="idx" 
                  :type="item.mode === 'gen' ? 'warning' : 'info'" 
                  size="small" 
                  effect="light"
                  class="ds-pill"
                >
                  {{ item.label }}
                </el-tag>
              </div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="scope">
          <el-tag :type="getStatusType(scope.row.status)" effect="light" size="small" round>
            {{ scope.row.status.toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="140">
        <template #default="scope">
          <el-progress :percentage="scope.row.progress" :status="scope.row.status === 'failed' ? 'exception' : ''" :stroke-width="8" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160" sortable prop="created_at">
        <template #default="scope">
          <span class="time-text">{{ new Date(scope.row.created_at).toLocaleString() }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right" align="center">
        <template #default="scope">
          <el-button type="primary" link @click="handleViewDetail(scope.row)">
            {{ scope.row.status === 'success' ? '报告' : '详情' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createDialogVisible" title="新建评测任务" width="1000px" top="5vh" :close-on-click-modal="false" class="custom-dialog">
      <div class="dialog-body" v-loading="isDataLoading" element-loading-text="正在加载最新模型与数据集...">
        <el-form label-position="top">
          <div class="section-card">
            <div class="section-title">Step 1. 选择待测模型</div>
            <el-select v-model="form.model_id" placeholder="搜索模型..." style="width: 100%" size="large" filterable>
              <template #prefix><el-icon><Search /></el-icon></template>
              <el-option v-for="m in modelList" :key="m.id" :label="m.name" :value="m.id">
                <div class="model-option">
                  <span class="model-name">{{ m.name }}</span>
                  <span class="model-path-opt"><el-icon><Folder /></el-icon> {{ m.path }}</span>
                </div>
              </el-option>
            </el-select>
          </div>

          <div class="section-card" style="margin-top: 15px; display: flex; flex-direction: column;">
            <div class="section-title">
              Step 2. 选择数据集 (按能力)
              <span class="sub-text">已选配置: {{ form.config_ids.length }}</span>
            </div>

            <div class="search-bar">
               <div class="filter-box" :class="{ active: showPrivateOnly }" @click="showPrivateOnly = !showPrivateOnly">
                  <span class="filter-label">
                    <el-icon class="mr-1"><Filter /></el-icon> 只看私有
                  </span>
                  <el-switch v-model="showPrivateOnly" size="small" style="--el-switch-on-color: #9b59b6;" @click.stop />
               </div>

               <el-input 
                 v-model="searchText" 
                 placeholder="搜索数据集名称..." 
                 prefix-icon="Search" 
                 clearable 
                 style="width: 300px"
               />
            </div>
            
            <div class="dataset-scroll-area">
              <el-collapse v-model="activeNames">
                <el-collapse-item v-for="(metas, capability) in filteredGroupedMetas" :key="capability" :name="capability">
                  <template #title>
                    <div class="group-title">
                      <el-tag :color="getCapColor(capability)" effect="dark" style="border:none; color:white" round size="small" class="mr-1">
                        {{ capability }}
                      </el-tag>
                      <span class="count-badge">{{ metas.length }} datasets</span>
                    </div>
                  </template>
                  
                  <div class="dataset-grid">
                    <div 
                      v-for="meta in metas" 
                      :key="meta.id" 
                      class="dataset-card"
                      :class="{ 'is-selected': selectedMetaMap[meta.id], 'is-official': meta.is_system }"
                    >
                      <div class="card-header">
                        <el-checkbox 
                          v-model="selectedMetaMap[meta.id]" 
                          @change="(val) => handleMetaCheckChange(meta, val)"
                        >
                          <span class="card-title" :title="meta.name">{{ meta.name }}</span>
                        </el-checkbox>
                        
                        <div v-if="meta.is_system" class="mini-badge official">Off.</div>
                        <div v-else class="mini-badge private">Pri.</div>
                      </div>
                      
                      <div class="card-body">
                         <div v-if="meta.configs && meta.configs.length > 1" class="mode-selector">
                            <span class="label">Mode:</span>
                            <el-select 
                              v-model="selectedConfigMap[meta.id]" 
                              size="small" 
                              style="width: 100px"
                              @change="(val) => handleConfigChange(meta.id, val)"
                              :disabled="!selectedMetaMap[meta.id]"
                            >
                               <el-option 
                                 v-for="cfg in meta.configs" 
                                 :key="cfg.id" 
                                 :label="cfg.mode.toUpperCase()" 
                                 :value="cfg.id" 
                               />
                            </el-select>
                         </div>
                         <div v-else-if="meta.configs && meta.configs.length === 1" class="mode-text">
                            <el-icon><Setting /></el-icon> 
                            <span>Mode: {{ meta.configs[0].mode.toUpperCase() }}</span>
                         </div>
                         <div v-else class="mode-text error">
                            暂无配置
                         </div>
                      </div>
                      
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
              
              <div v-if="!Object.keys(filteredGroupedMetas).length" class="empty-tip">未找到匹配的数据集</div>
            </div>
          </div>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="createDialogVisible = false" size="large">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting" size="large" style="width: 150px;">
            立即启动 ({{ form.config_ids.length }})
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-drawer v-model="detailDrawerVisible" :title="currentTask ? `Task #${currentTask.id}` : '详情'" size="50%">
       <div v-if="currentTask" class="detail-container">
          <div class="status-banner" :class="currentTask.status">
             <div class="status-text">
                <h2>{{ currentTask.status.toUpperCase() }}</h2>
                <p>{{ getModelName(currentTask.model_id) }}</p>
             </div>
             <el-progress type="dashboard" :percentage="currentTask.progress" :width="60" />
          </div>
          <div v-if="currentTask.status === 'running'" class="terminal-box" id="terminal-box">
             <div v-for="(log,i) in terminalLogs" :key="i">{{ log }}</div>
          </div>
          <div v-if="currentTask.status === 'success' && taskResult">
             <div id="result-radar" style="width:100%;height:300px;"></div>
             <el-table :data="taskResult.table" border size="small" style="margin-top:10px;">
               <el-table-column prop="capability" label="Capability" width="100"/>
               <el-table-column prop="dataset" label="Dataset" />
               <el-table-column prop="score" label="Score" />
             </el-table>
          </div>
       </div>
    </el-drawer>
  </div>
</template>

<style scoped>
/* 样式与上一次保持一致 */
.search-bar { margin-bottom: 10px; border-bottom: 1px solid #f0f0f0; padding-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
.filter-box { display: flex; align-items: center; background: #f4f4f5; padding: 4px 10px; border-radius: 16px; margin-right: 10px; cursor: pointer; transition: all 0.3s; border: 1px solid transparent; }
.filter-box:hover { background: #ebeef5; }
.filter-box.active { background: #f2ebfb; border-color: #d6bbf5; }
.filter-label { font-size: 12px; color: #606266; margin-right: 8px; display: flex; align-items: center; }
.filter-box.active .filter-label { color: #8e44ad; font-weight: bold; }
.mini-badge { font-size: 10px; padding: 1px 4px; border-radius: 4px; font-weight: bold; height: 16px; line-height: 14px; flex-shrink: 0; margin-left: 5px; }
.mini-badge.official { background-color: #ecf5ff; color: #409eff; border: 1px solid #c6e2ff; }
.mini-badge.private { background-color: #f3e5f5; color: #7b1fa2; border: 1px solid #e1bee7; }
.dataset-card.is-official { border-left: 3px solid #409EFF; }
.dataset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; padding: 12px; background: #fafafa; }
.dataset-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px; display: flex; flex-direction: column; justify-content: space-between; transition: all 0.2s; }
.dataset-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.05); transform: translateY(-1px); }
.dataset-card.is-selected { border-color: #409EFF; background-color: #ecf5ff; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.card-title { font-weight: 600; font-size: 14px; color: #303133; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-all; }
.card-body { padding-top: 5px; border-top: 1px dashed #eee; display: flex; align-items: center; justify-content: space-between; }
.mode-selector { display: flex; align-items: center; gap: 5px; width: 100%; }
.mode-selector .label { font-size: 12px; color: #909399; }
.mode-text { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; }
.mode-text.error { color: #F56C6C; }
.header-actions { display: flex; justify-content: space-between; margin-bottom: 20px; }
.content-container { display: flex; flex-direction: column; gap: 6px; }
.cap-row { display: flex; align-items: flex-start; }
.cap-header { display: flex; align-items: center; gap: 4px; width: 120px; flex-shrink: 0; font-weight: bold; font-size: 13px; justify-content: flex-end; padding-right: 12px; border-right: 2px solid #eee; margin-right: 12px; height: 24px; }
.ds-list { display: flex; flex-wrap: wrap; gap: 4px; }
.section-card { background: #fff; padding: 15px; border: 1px solid #ebeef5; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
.section-title { font-size: 15px; font-weight: bold; color: #303133; margin-bottom: 12px; border-left: 4px solid #409EFF; padding-left: 10px; display: flex; justify-content: space-between; }
.dataset-scroll-area { max-height: 50vh; overflow-y: auto; padding-right: 5px; }
.group-title { width: 100%; display: flex; align-items: center; }
.count-badge { margin-left: auto; font-size: 12px; color: #999; margin-right: 10px; }
.status-banner { display: flex; justify-content: space-between; background: #409EFF; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
.terminal-box { background: #1e1e1e; color: #67c23a; padding: 15px; height: 300px; overflow-y: auto; font-family: monospace; border-radius: 6px; }
</style>