<script setup>
import { ref, onMounted, reactive, nextTick, computed, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { 
  VideoPlay, Refresh, Document, Connection, 
  DataLine, Download, Loading, Monitor 
} from '@element-plus/icons-vue'

// === 1. 数据定义 ===
const tableData = ref([])
const modelList = ref([])
const datasetList = ref([])

// 弹窗与抽屉控制
const createDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const currentTask = ref(null) // 当前查看的任务
const submitting = ref(false)

// 实时日志模拟
const terminalLogs = ref([])
let logInterval = null

// 表单
const form = reactive({
  model_id: null,
  dataset_ids: []
})

const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 2. 辅助函数 ===
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

// === 3. 核心交互逻辑 ===

// 加载基础列表
const fetchData = async () => {
  try {
    const [taskRes, modelRes, datasetRes] = await Promise.all([
      axios.get(`${API_BASE}/tasks/`),
      axios.get(`${API_BASE}/models/`),
      axios.get(`${API_BASE}/datasets/`)
    ])
    // 倒序排列，最新的在前面
    tableData.value = taskRes.data.sort((a, b) => b.id - a.id)
    modelList.value = modelRes.data
    datasetList.value = datasetRes.data
    
    // 如果当前正在看详情，且任务还在跑，更新当前详情数据
    if (detailDrawerVisible.value && currentTask.value && currentTask.value.status === 'running') {
       const updatedTask = tableData.value.find(t => t.id === currentTask.value.id)
       if(updatedTask) handleViewDetail(updatedTask, false) // false 表示不重置日志
    }

  } catch (error) {
    console.error(error)
  }
}

// 提交新任务
const handleSubmit = async () => {
  if (!form.model_id || form.dataset_ids.length === 0) return ElMessage.warning('请补全信息')
  submitting.value = true
  try {
    await axios.post(`${API_BASE}/tasks/`, form)
    ElMessage.success('🚀 评测任务已启动')
    createDialogVisible.value = false
    form.model_id = null; form.dataset_ids = []
    fetchData()
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

// === 4. 详情页与日志逻辑 ===

const handleViewDetail = (row, resetLogs = true) => {
  currentTask.value = row
  detailDrawerVisible.value = true
  
  // 如果任务是 Running 状态，启动日志模拟和轮询
  if (row.status === 'running' || row.status === 'pending') {
    if (resetLogs) startFakeLogs()
  } else if (row.status === 'success') {
    // 如果成功，显示结果图表
    terminalLogs.value = [] // 清空日志
    if(logInterval) clearInterval(logInterval)
    nextTick(() => {
      initRadarChart()
    })
  }
}

// 模拟日志流 (为了演示效果)
const startFakeLogs = () => {
  terminalLogs.value = ['> System init...', '> Waiting for worker...']
  if (logInterval) clearInterval(logInterval)
  
  const logPool = [
    'Loading model weights from disk...',
    'Allocating GPU memory (22GB/24GB)...',
    'Loading dataset GSM8K...',
    'Inference batch [12/100] speed=12.5 tokens/s',
    'Inference batch [24/100] speed=13.1 tokens/s',
    'Calculating metrics...',
    'Saving intermediate results to /tmp/output...'
  ]
  
  let idx = 0
  logInterval = setInterval(() => {
    if (currentTask.value.status !== 'running') {
      clearInterval(logInterval)
      return
    }
    // 随机取日志
    const msg = logPool[Math.floor(Math.random() * logPool.length)]
    const time = newjhDate().toLocaleTimeString()
    terminalLogs.value.push(`[${time}] ${msg}`)
    
    // 保持滚动到底部
    const terminal = document.getElementById('terminal-box')
    if(terminal) terminal.scrollTop = terminal.scrollHeight
  }, 1500)
}

// 雷达图初始化
const initRadarChart = () => {
  const chartDom = document.getElementById('result-radar')
  if (!chartDom || !currentTask.value.result_summary) return
  
  let resultObj = {}
  try {
    resultObj = JSON.parse(currentTask.value.result_summary)
  } catch(e) { return }

  if (!resultObj.radar) return

  const myChart = echarts.init(chartDom)
  const option = {
    tooltip: {},
    radar: {
      indicator: resultObj.radar.map(r => ({ name: r.name, max: r.max })),
      radius: '65%'
    },
    series: [{
      name: '能力评估',
      type: 'radar',
      data: [{
        value: resultObj.radar.map(r => r.score),
        name: 'Model Score',
        itemStyle: { color: '#409EFF' },
        areaStyle: { opacity: 0.2 }
      }]
    }]
  }
  myChart.setOption(option)
  
  // 窗口缩放自适应
  window.addEventListener('resize', () => myChart.resize())
}

// 结果解析器
const taskResult = computed(() => {
  if (!currentTask.value || !currentTask.value.result_summary) return null
  try {
    return JSON.parse(currentTask.value.result_summary)
  } catch {
    return null
  }
})

// === 5. 生命周期 ===
let pollingTimer = null
onMounted(() => {
  fetchData()
  pollingTimer = setInterval(fetchData, 3000) // 每3秒轮询一次列表状态
})

onUnmounted(() => {
  if (pollingTimer) clearInterval(pollingTimer)
  if (logInterval) clearInterval(logInterval)
})
</script>

<template>
  <div class="task-view">
    <div class="header-actions">
      <el-button type="primary" size="large" @click="createDialogVisible = true">
        <el-icon class="mr-1"><VideoPlay /></el-icon> 新建评测任务
      </el-button>
      <el-button :icon="Refresh" circle @click="fetchData" />
    </div>

    <el-table :data="tableData" border style="width: 100%" stripe highlight-current-row>
      <el-table-column prop="id" label="ID" width="70" align="center" />
      <el-table-column label="模型" min-width="150">
        <template #default="scope">
          <strong>{{ getModelName(scope.row.model_id) }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="数据集" min-width="200" show-overflow-tooltip>
        <template #default="scope">
          <span v-for="d in parseDatasets(scope.row.datasets_list)" :key="d" class="ds-tag">
            {{ d }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120" align="center">
        <template #default="scope">
          <el-tag :type="getStatusType(scope.row.status)" effect="dark">
            {{ scope.row.status.toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="150">
        <template #default="scope">
          <el-progress 
            :percentage="scope.row.progress" 
            :status="scope.row.status === 'failed' ? 'exception' : ''"
            :stroke-width="10"
          />
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="180">
        <template #default="scope">
          <span style="font-size: 12px; color: #666;">
            {{ new Date(scope.row.created_at).toLocaleString() }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right" align="center">
        <template #default="scope">
          <el-button type="primary" link @click="handleViewDetail(scope.row)">
            {{ scope.row.status === 'success' ? '查看报告' : '查看详情' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createDialogVisible" title="新建评测任务" width="500px">
      <el-form label-position="top">
        <el-form-item label="选择模型">
          <el-select v-model="form.model_id" placeholder="请选择" style="width: 100%">
            <el-option v-for="m in modelList" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择数据集">
          <el-select v-model="form.dataset_ids" multiple placeholder="支持多选" style="width: 100%">
            <el-option v-for="d in datasetList" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">提交</el-button>
      </template>
    </el-dialog>

    <el-drawer 
      v-model="detailDrawerVisible" 
      :title="currentTask ? `Task #${currentTask.id} 详情` : '任务详情'"
      size="50%"
      destroy-on-close
    >
      <div v-if="currentTask" class="detail-container">
        
        <div class="status-banner" :class="currentTask.status">
          <el-icon size="24" class="icon-spin" v-if="currentTask.status === 'running'"><Loading /></el-icon>
          <el-icon size="24" v-else-if="currentTask.status === 'success'"><CircleCheck /></el-icon>
          <div class="status-text">
            <h2>{{ currentTask.status.toUpperCase() }}</h2>
            <p>Model: {{ getModelName(currentTask.model_id) }}</p>
          </div>
          <el-progress type="dashboard" :percentage="currentTask.progress" :width="60" />
        </div>

        <div v-if="currentTask.status === 'running' || currentTask.status === 'pending'" class="running-view">
          <h3><el-icon><Monitor /></el-icon> 实时终端日志</h3>
          <div id="terminal-box" class="terminal-box">
            <div v-for="(log, i) in terminalLogs" :key="i" class="log-line">
              {{ log }}
            </div>
            <div class="cursor-line">_</div>
          </div>
        </div>

        <div v-if="currentTask.status === 'success' && taskResult" class="result-view">
          
          <el-card class="box-card mb-3">
            <template #header><div class="card-head">🎯 综合能力画像 (Capability)</div></template>
            <div id="result-radar" style="width: 100%; height: 300px;"></div>
          </el-card>

          <el-card class="box-card mb-3">
            <template #header><div class="card-head">📊 数据集详情 (Datasets)</div></template>
            <el-table :data="taskResult.table" style="width: 100%" size="small" border>
              <el-table-column prop="capability" label="能力维度" width="100" />
              <el-table-column prop="dataset" label="数据集" />
              <el-table-column prop="metric" label="指标" width="100" />
              <el-table-column prop="score" label="得分" width="80" align="right">
                <template #default="scope">
                  <span :class="scope.row.score >= 60 ? 'score-pass' : 'score-fail'">
                    {{ scope.row.score }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card class="box-card">
            <template #header><div class="card-head">Vk🗂️ 产物文件 (Artifacts)</div></template>
            <div v-for="file in taskResult.files" :key="file.name" class="file-item">
              <div class="file-left">
                <el-icon><Document /></el-icon>
                <span class="fname">{{ file.name }}</span>
                <el-tag size="small" type="info">{{ file.size }}</el-tag>
              </div>
              <el-button link type="primary" :icon="Download">下载</el-button>
            </div>
          </el-card>

        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  justify-content: space-between;
  margin-bottom: 20px;
}
.ds-tag {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  margin-right: 4px;
  color: #606266;
}
.mb-3 { margin-bottom: 15px; }
.mr-1 { margin-right: 5px; }

/* 状态 Banner */
.status-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-radius: 8px;
  color: #fff;
  margin-bottom: 20px;
}
.status-banner.running { background: linear-gradient(135deg, #409eff, #36d1dc); }
.status-banner.success { background: linear-gradient(135deg, #67c23a, #f0f9eb); color: #67c23a; border: 1px solid #67c23a; }
.status-banner.success h2 { color: #67c23a; } 
.status-banner.success p { color: #606266; }

.status-text h2 { margin: 0; font-size: 24px; }
.status-text p { margin: 5px 0 0 0; opacity: 0.9; font-size: 14px; }

/* 终端日志 */
.terminal-box {
  background: #1e1e1e;
  color: #00ff00;
  font-family: 'Consolas', 'Monaco', monospace;
  padding: 15px;
  border-radius: 6px;
  height: 400px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.5;
  box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
}
.log-line { margin-bottom: 4px; border-bottom: 1px dashed #333; padding-bottom: 2px; }
.cursor-line { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* 结果视图 */
.card-head { font-weight: bold; font-size: 15px; }
.score-pass { color: #67c23a; font-weight: bold; }
.score-fail { color: #f56c6c; font-weight: bold; }

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
}
.file-left { display: flex; align-items: center; gap: 10px; }
.fname { font-size: 14px; color: #303133; }
</style>