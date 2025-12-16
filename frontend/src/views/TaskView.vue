<script setup>
import { ref, onMounted, reactive, nextTick, computed, onUnmounted, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { 
  VideoPlay, Refresh, Document, Connection, 
  DataLine, Download, Loading, Monitor,
  Folder, Search, InfoFilled, Odometer, PriceTag,
  Cpu, Key, MagicStick, Collection, Lock,
  Medal, User 
} from '@element-plus/icons-vue'

// === 1. 数据定义 ===
const tableData = ref([])
const modelList = ref([])
const datasetList = ref([])

// 弹窗与抽屉控制
const createDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const currentTask = ref(null) 
const submitting = ref(false)
const terminalLogs = ref([])
let logInterval = null

// 表单数据
const form = reactive({
  model_id: null,
  dataset_ids: []
})

// 界面状态
const activeNames = ref([]) 
const searchText = ref('') // 🔍 数据集搜索关键词

const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 2. 核心计算属性 ===

// 当前选中的模型信息
const selectedModelInfo = computed(() => {
  if (!form.model_id) return null
  return modelList.value.find(m => m.id === form.model_id)
})

// 🌟 核心：带搜索过滤和分组的数据集列表
const filteredGroupedDatasets = computed(() => {
  const groups = {}
  if (!datasetList.value || datasetList.value.length === 0) return groups
  
  // 1. 关键词过滤
  const keyword = searchText.value.toLowerCase().trim()
  const filteredList = datasetList.value.filter(ds => {
    if (!keyword) return true
    const isOfficialMatch = ds.is_system && 'official'.includes(keyword)
    const isPrivateMatch = !ds.is_system && 'private'.includes(keyword)
    
    return ds.name.toLowerCase().includes(keyword) || 
           (ds.capability && ds.capability.toLowerCase().includes(keyword)) ||
           isOfficialMatch || isPrivateMatch
  })

  // 2. 分组
  filteredList.forEach(ds => {
    const cap = ds.capability || 'Base' 
    if (!groups[cap]) groups[cap] = []
    groups[cap].push(ds)
  })
  
  return groups
})

// === 3. 辅助逻辑 ===

// 监听搜索词，自动展开所有分组
watch(searchText, (newVal) => {
  if (newVal.trim()) {
    activeNames.value = Object.keys(filteredGroupedDatasets.value)
  }
})

// 列表页：按能力分组数据集
const getTaskDatasetGroups = (taskRow) => {
  const dsNames = parseDatasets(taskRow.datasets_list)
  if (!dsNames.length) return {}
  
  const groups = {}
  dsNames.forEach(name => {
    const dsObj = datasetList.value.find(d => d.name === name)
    const cap = dsObj ? (dsObj.capability || 'Others') : 'Unknown'
    if (!groups[cap]) groups[cap] = []
    groups[cap].push(name)
  })
  return groups
}

// 图标映射
const getCapIcon = (cap) => {
  const map = {
    'Reasoning': MagicStick,
    'Knowledge': Collection,
    'Coding': Monitor,
    'Safety': Lock,
    'Understanding': Document
  }
  for (const key in map) {
    if (cap.includes(key)) return map[key]
  }
  return DataLine
}

// 颜色映射
const getCapColor = (cap) => {
  if (cap.includes('Reasoning') || cap.includes('Math')) return '#E6A23C'
  if (cap.includes('Knowledge')) return '#409EFF'
  if (cap.includes('Coding')) return '#67C23A'
  if (cap.includes('Safety')) return '#F56C6C'
  return '#909399'
}

const getModelName = (id) => {
  const found = modelList.value.find(m => m.id === id)
  return found ? found.name : `Model-${id}`
}

const parseDatasets = (jsonStr) => {
  try { return JSON.parse(jsonStr) } catch { return [] }
}

const getStatusType = (status) => {
  const map = { pending: 'info', running: 'primary', success: 'success', failed: 'danger' }
  return map[status] || 'info'
}

// === 4. 数据交互 ===

const fetchData = async () => {
  try {
    const [taskRes, modelRes, datasetRes] = await Promise.all([
      axios.get(`${API_BASE}/tasks/`),
      axios.get(`${API_BASE}/models/`),
      axios.get(`${API_BASE}/datasets/`)
    ])
    tableData.value = taskRes.data.sort((a, b) => b.id - a.id)
    modelList.value = modelRes.data
    datasetList.value = datasetRes.data
    
    if (activeNames.value.length === 0 && Object.keys(filteredGroupedDatasets.value).length > 0) {
       activeNames.value = Object.keys(filteredGroupedDatasets.value)
    }
    
    if (detailDrawerVisible.value && currentTask.value && currentTask.value.status === 'running') {
       const updatedTask = tableData.value.find(t => t.id === currentTask.value.id)
       if(updatedTask) handleViewDetail(updatedTask, false)
    }
  } catch (error) {
    console.error(error)
  }
}

const handleOpenCreate = () => {
  createDialogVisible.value = true
  searchText.value = '' 
  fetchData()
}

const handleSubmit = async () => {
  if (!form.model_id || form.dataset_ids.length === 0) return ElMessage.warning('请至少选择一个模型和一个数据集')
  submitting.value = true
  try {
    await axios.post(`${API_BASE}/tasks/`, form)
    ElMessage.success('🚀 评测任务已启动')
    createDialogVisible.value = false
    form.model_id = null
    form.dataset_ids = []
    fetchData()
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

// === 5. 详情页与日志 ===

const handleViewDetail = (row, resetLogs = true) => {
  currentTask.value = row
  detailDrawerVisible.value = true
  if (row.status === 'running' || row.status === 'pending') {
    if (resetLogs) startFakeLogs()
  } else if (row.status === 'success') {
    terminalLogs.value = []
    if(logInterval) clearInterval(logInterval)
    nextTick(() => { initRadarChart() })
  }
}

const startFakeLogs = () => {
  terminalLogs.value = ['> System init...']
  if (logInterval) clearInterval(logInterval)
  const logPool = ['Loading model weights...', 'Allocating GPU memory...', 'Inference batch processed...', 'Calculating metrics...']
  logInterval = setInterval(() => {
    if (currentTask.value.status !== 'running') {
      clearInterval(logInterval)
      return
    }
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
  if (!resultObj.radar) return

  const myChart = echarts.init(chartDom)
  const option = {
    tooltip: {},
    radar: { indicator: resultObj.radar.map(r => ({ name: r.name, max: r.max })), radius: '65%' },
    series: [{
      type: 'radar',
      data: [{ value: resultObj.radar.map(r => r.score), name: 'Model Score', itemStyle: { color: '#409EFF' }, areaStyle: { opacity: 0.2 } }]
    }]
  }
  myChart.setOption(option)
  window.addEventListener('resize', () => myChart.resize())
}

const taskResult = computed(() => {
  if (!currentTask.value || !currentTask.value.result_summary) return null
  try { return JSON.parse(currentTask.value.result_summary) } catch { return null }
})

// === 6. 生命周期 ===
let pollingTimer = null
onMounted(() => {
  fetchData()
  pollingTimer = setInterval(fetchData, 3000)
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
      <el-button :icon="Refresh" circle @click="fetchData" />
    </div>

    <el-table :data="tableData" border style="width: 100%" stripe highlight-current-row class="main-table">
      <el-table-column prop="id" label="ID" width="70" align="center" sortable />
      
      <el-table-column label="模型 (Model)" min-width="140">
        <template #default="scope">
          <div class="model-cell">
            <strong>{{ getModelName(scope.row.model_id) }}</strong>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="评测内容 (Content)" min-width="320">
        <template #default="scope">
          <div class="content-container">
            <div 
              v-for="(datasets, cap) in getTaskDatasetGroups(scope.row)" 
              :key="cap" 
              class="cap-row"
            >
              <div class="cap-header" :style="{ color: getCapColor(cap) }">
                <el-icon class="cap-icon"><component :is="getCapIcon(cap)" /></el-icon>
                <span class="cap-name">{{ cap }}</span>
              </div>
              <div class="ds-list">
                <span v-for="ds in datasets" :key="ds" class="ds-pill">{{ ds }}</span>
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
          <el-progress 
            :percentage="scope.row.progress" 
            :status="scope.row.status === 'failed' ? 'exception' : ''" 
            :stroke-width="8"
          />
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

    <el-dialog 
      v-model="createDialogVisible" 
      title="新建评测任务" 
      width="55%"
      top="5vh"
      :close-on-click-modal="false"
      class="custom-dialog"
    >
      <div class="dialog-body">
        <el-form label-position="top">
          
          <div class="section-card">
            <div class="section-title">Step 1. 选择待测模型 (Target Model)</div>
            <el-select 
              v-model="form.model_id" 
              placeholder="请搜索或选择模型..." 
              style="width: 100%" 
              size="large"
              filterable
            >
              <template #prefix><el-icon><Search /></el-icon></template>
              <el-option v-for="m in modelList" :key="m.id" :label="m.name" :value="m.id">
                <div class="model-option">
                  <span class="model-name">{{ m.name }}</span>
                  <span class="model-path-opt"><el-icon><Folder /></el-icon> {{ m.path }}</span>
                </div>
              </el-option>
            </el-select>

            <div v-if="selectedModelInfo" class="model-summary-card">
              <div class="ms-row">
                <div class="ms-main-info">
                  <el-icon :size="20" class="ms-icon"><Cpu /></el-icon>
                  <span class="ms-name">{{ selectedModelInfo.name }}</span>
                </div>
                <div class="ms-tags">
                  <el-tag effect="plain" type="success" size="small">{{ selectedModelInfo.param_size || 'Unknown' }}</el-tag>
                  <el-tag effect="plain" type="warning" size="small">{{ selectedModelInfo.type.toUpperCase() }}</el-tag>
                </div>
              </div>
              <div class="ms-row secondary">
                <div class="ms-item">
                  <el-icon><Folder /></el-icon> 
                  <span class="ms-text path">{{ selectedModelInfo.path }}</span>
                </div>
              </div>
              <div class="ms-row secondary" v-if="selectedModelInfo.description">
                 <div class="ms-item">
                  <el-icon><InfoFilled /></el-icon>
                  <span class="ms-text">{{ selectedModelInfo.description }}</span>
                 </div>
              </div>
            </div>
          </div>

          <div class="section-card" style="margin-top: 15px; flex: 1; display: flex; flex-direction: column; overflow: hidden;">
            <div class="section-title">
              Step 2. 选择评测数据集
              <span class="sub-text">已选: {{ form.dataset_ids.length }}</span>
            </div>

            <div class="search-bar">
              <el-input 
                v-model="searchText" 
                placeholder="搜索名称、能力 (如 'Math')、来源 (如 'Official')" 
                prefix-icon="Search"
                clearable
              />
            </div>
            
            <div class="dataset-scroll-area">
              <el-collapse v-model="activeNames">
                <el-collapse-item 
                  v-for="(datasets, capability) in filteredGroupedDatasets" 
                  :key="capability" 
                  :name="capability"
                >
                  <template #title>
                    <div class="group-title">
                      <el-tag :color="getCapColor(capability)" effect="dark" style="border:none; color:white" round size="small" class="mr-1">
                        {{ capability }}
                      </el-tag>
                      <span class="count-badge">{{ datasets.length }} sets</span>
                    </div>
                  </template>
                  
                  <div class="dataset-grid">
                    <el-checkbox-group v-model="form.dataset_ids" style="display: contents;">
                      <el-checkbox 
                        v-for="d in datasets" 
                        :key="d.id" 
                        :label="d.id" 
                        border
                        class="grid-item"
                        :class="{ 'is-system': d.is_system }"
                      >
                        <div class="cb-content">
                          <div class="ds-header">
                            <span class="cb-name" :title="d.name">{{ d.name }}</span>
                            <div v-if="d.is_system" class="custom-tag tag-official">
                              <el-icon><Medal /></el-icon> Official
                            </div>
                            <div v-else class="custom-tag tag-private">
                              <el-icon><User /></el-icon> Private
                            </div>
                          </div>
                          <span class="cb-metric">
                            <el-icon><Odometer /></el-icon> {{ d.metric_name }}
                          </span>
                        </div>
                      </el-checkbox>
                    </el-checkbox-group>
                  </div>
                </el-collapse-item>
              </el-collapse>

              <div v-if="Object.keys(filteredGroupedDatasets).length === 0" class="empty-tip">
                未找到匹配的数据集
              </div>
            </div>
          </div>

        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="createDialogVisible = false" size="large">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting" size="large" style="width: 150px;">
            立即启动 ({{ form.dataset_ids.length }})
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-drawer v-model="detailDrawerVisible" :title="currentTask ? `Task #${currentTask.id}` : '任务详情'" size="50%" destroy-on-close>
      <div v-if="currentTask" class="detail-container">
        <div class="status-banner" :class="currentTask.status">
          <div class="status-text">
            <h2>{{ currentTask.status.toUpperCase() }}</h2>
            <p>{{ getModelName(currentTask.model_id) }}</p>
          </div>
          <el-progress type="dashboard" :percentage="currentTask.progress" :width="60" />
        </div>
        <div v-if="currentTask.status === 'running'" class="terminal-box">
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
/* 基础布局 */
.header-actions { display: flex; justify-content: space-between; margin-bottom: 20px; }
.time-text { font-size: 12px; color: #909399; }

/* 列表页：Key-Value 评测内容样式 */
.content-container { display: flex; flex-direction: column; gap: 8px; padding: 4px 0; }
.cap-row { display: flex; align-items: baseline; }
.cap-header { 
  display: flex; align-items: center; gap: 4px; width: 100px; flex-shrink: 0;
  font-weight: bold; font-size: 13px; justify-content: flex-end; padding-right: 12px;
  border-right: 2px solid #eee; margin-right: 12px;
}
.cap-name { text-transform: capitalize; }
.ds-list { display: flex; flex-wrap: wrap; gap: 6px; }
.ds-pill { 
  background: #f4f4f5; color: #606266; padding: 2px 8px; border-radius: 12px; font-size: 12px; 
  border: 1px solid #e9e9eb;
}

/* 弹窗样式 */
.dialog-body { display: flex; flex-direction: column; gap: 15px; }
.section-card { background: #fff; padding: 15px; border: 1px solid #ebeef5; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
.section-title { font-size: 15px; font-weight: bold; color: #303133; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #409EFF; padding-left: 10px; }
.sub-text { font-size: 12px; color: #909399; font-weight: normal; }

/* 模型摘要卡片 */
.model-summary-card {
  margin-top: 12px; background-color: #fcfcfc; border: 1px solid #e4e7ed; border-radius: 6px; padding: 12px 16px;
  animation: fadeIn 0.3s ease;
}
.ms-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.ms-row.secondary { margin-bottom: 4px; justify-content: flex-start; }
.ms-main-info { display: flex; align-items: center; gap: 8px; }
.ms-name { font-size: 16px; font-weight: bold; color: #303133; }
.ms-tags { display: flex; gap: 6px; }
.ms-item { display: flex; align-items: center; gap: 6px; color: #909399; font-size: 13px; }
.ms-text { color: #606266; }
.ms-text.path { font-family: monospace; background: #f0f2f5; padding: 0 4px; border-radius: 4px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }

/* 数据集选择区样式 - 优化后 */
.search-bar { padding: 0 0 10px 0; border-bottom: 1px solid #f0f0f0; margin-bottom: 10px; }
.dataset-scroll-area { max-height: 45vh; overflow-y: auto; padding-right: 5px; }

/* 🌟 优化 1: 加宽 Grid 列宽，增加间距 */
.dataset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); /* 从 220px 增加到 250px */
  gap: 12px; /* 增加间距 */
  padding: 12px;
  background: #fcfcfc;
}
.grid-item { margin-right: 0 !important; width: 100%; height: auto; padding: 10px; display: flex; align-items: flex-start; }

/* Grid Item 内部 - 优化后 */
.cb-content { display: flex; flex-direction: column; width: 100%; overflow: hidden; }
/* 🌟 优化 2: 紧凑排列，名称自适应宽度 */
.ds-header {
  display: flex;
  justify-content: flex-start; /* 改为靠左对齐 */
  align-items: center;
  width: 100%;
  margin-bottom: 6px;
  gap: 8px; /* 增加名称和标签之间的间距 */
}
.cb-name {
  font-weight: bold;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-grow: 1; /* 让名称占据剩余空间 */
  flex-shrink: 1; /* 空间不足时收缩 */
}
.cb-metric { font-size: 12px; color: #999; display: flex; align-items: center; gap: 4px; }

/* 🌟 优化 3: 自定义标签样式 (替代 el-tag) */
.custom-tag {
  border-radius: 12px;
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
  flex-shrink: 0; /* 防止标签被压缩 */
  height: 20px;
  line-height: 18px;
  border: 1px solid;
}
/* 醒目的紫色 Private 主题 */
.tag-private {
  background-color: #f2ebfb;
  border-color: #d6bbf5;
  color: #8e44ad;
}
/* 配套的蓝色 Official 主题 */
.tag-official {
  background-color: #ecf5ff;
  border-color: #c6e2ff;
  color: #409eff;
}

/* 官方数据集背景高亮 (可选) */
.grid-item.is-system { background-color: #f0f9eb66; } /* 稍微淡一点的绿色背景 */

.empty-tip { text-align: center; color: #909399; padding: 20px; font-size: 13px; }
.group-title { font-weight: bold; font-size: 14px; display: flex; align-items: center; width: 100%; }
.count-badge { font-size: 12px; color: #909399; margin-left: auto; margin-right: 10px; }
.mr-1 { margin-right: 8px; }

/* 详情复用 */
.status-banner { display: flex; justify-content: space-between; background: #409EFF; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
.terminal-box { background: #1e1e1e; color: #67c23a; padding: 15px; height: 300px; overflow-y: auto; font-family: 'Consolas', monospace; border-radius: 6px; }
</style>