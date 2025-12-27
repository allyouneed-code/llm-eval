<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { getTask } from '@/api/task'
import { CircleCheck, CircleClose, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  taskId: { type: [Number, String], default: null },
  initialTask: { type: Object, default: null }
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
const taskDetail = ref(null)
const terminalLogs = ref([]) 
const logAbortController = ref(null) // 用于中断日志流连接
let statusInterval = null          // 仅用于更新进度条和状态
let myChart = null

// 优先使用详情接口数据
const task = computed(() => taskDetail.value || props.initialTask)

// 结果解析
const taskResult = computed(() => {
  if (!task.value?.result_summary) return null
  try {
    const res = JSON.parse(task.value.result_summary)
    if (!res || !res.radar || !res.table) return { radar: [], table: [] }
    return res
  } catch (e) {
    return { radar: [], table: [] }
  }
})

// 监听弹窗打开
watch(() => props.visible, async (val) => {
  if (val && props.taskId) {
    // 1. 先获取一次最新状态
    await fetchTaskDetail()
    
    // 2. 无论状态如何，都尝试拉取日志（如果是已完成任务，后端会一次性返回全部日志）
    startLogStream()

    // 3. 如果任务未完成，开启状态轮询以更新进度条
    if (['pending', 'running'].includes(task.value?.status)) {
      startStatusPolling()
    } else if (task.value?.status === 'success') {
      // 如果已完成，延迟渲染图表
      setTimeout(() => nextTick(() => initRadarChart()), 350)
    }
  } else {
    stopAll()
  }
})

// 获取任务详情 API
const fetchTaskDetail = async () => {
  if (!props.taskId) return
  if (!taskDetail.value) loading.value = true
  try {
    const res = await getTask(props.taskId)
    taskDetail.value = res
  } catch (e) {
    console.error("Fetch detail failed:", e)
  } finally {
    loading.value = false
  }
}

// 🌟 核心：实时日志流处理
const startLogStream = async () => {
  // 清理旧连接
  if (logAbortController.value) logAbortController.value.abort()
  logAbortController.value = new AbortController()
  
  terminalLogs.value = []
  let buffer = '' // 用于处理分块数据

  try {
    // 构造流式接口 URL (复用 Vite 环境变量)
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
    const url = `${baseUrl.replace(/\/$/, '')}/v1/tasks/${props.taskId}/log`

    const response = await fetch(url, {
      signal: logAbortController.value.signal
    })

    if (!response.ok) {
      terminalLogs.value.push(`> Failed to connect log stream: ${response.statusText}`)
      return
    }

    // 获取 Reader
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk
      
      // 按行切分处理
      if (buffer.includes('\n')) {
        const lines = buffer.split('\n')
        // 保留最后一段可能不完整的数据
        buffer = lines.pop() 
        
        lines.forEach(line => {
          terminalLogs.value.push(line)
        })
        scrollToBottom()
      }
    }
    
    // 流结束（任务完成或出错），再刷新一次最终状态
    await fetchTaskDetail()
    if (task.value?.status === 'success') {
      setTimeout(() => nextTick(() => initRadarChart()), 100)
    }

  } catch (e) {
    if (e.name !== 'AbortError') {
      terminalLogs.value.push(`> Connection interrupted: ${e.message}`)
    }
  }
}

// 状态轮询 (仅更新进度和 Status)
const startStatusPolling = () => {
  if (statusInterval) clearInterval(statusInterval)
  
  statusInterval = setInterval(async () => {
    await fetchTaskDetail()
    
    // 如果任务结束，停止轮询 (日志流可能还在读最后一点数据，所以日志流单独管理退出)
    if (['success', 'failed'].includes(task.value?.status)) {
      clearInterval(statusInterval)
      statusInterval = null
    }
  }, 3000)
}

const stopAll = () => {
  if (statusInterval) {
    clearInterval(statusInterval)
    statusInterval = null
  }
  if (logAbortController.value) {
    logAbortController.value.abort()
    logAbortController.value = null
  }
  taskDetail.value = null
  terminalLogs.value = []
  if (myChart) {
    myChart.dispose()
    myChart = null
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    const terminal = document.getElementById('terminal-box')
    if(terminal) terminal.scrollTop = terminal.scrollHeight
  })
}

// 初始化图表 (保持之前的修复版本)
const initRadarChart = () => {
  const chartDom = document.getElementById('result-radar')
  if (!chartDom) return
  if (!taskResult.value?.radar || taskResult.value.radar.length === 0) return
  if (chartDom.clientWidth === 0) {
    setTimeout(initRadarChart, 100)
    return
  }

  if (myChart) myChart.dispose()
  myChart = echarts.init(chartDom)
  
  const radarData = taskResult.value.radar
  const option = {
    tooltip: {},
    radar: { 
      indicator: radarData.map(r => ({ name: r.name, max: 100 })), 
      radius: '65%',
      splitNumber: 4,
      axisName: { color: '#666' }
    },
    series: [{ 
      type: 'radar', 
      data: [{ 
        value: radarData.map(r => r.score), 
        name: 'Model Capabilities', 
        itemStyle: { color: '#409EFF' }, 
        areaStyle: { opacity: 0.2 },
        symbol: 'circle',
        symbolSize: 6
      }] 
    }]
  }
  myChart.setOption(option)
  myChart.resize()
  window.addEventListener('resize', () => myChart && myChart.resize())
}

onUnmounted(() => {
  stopAll()
  window.removeEventListener('resize', () => myChart && myChart.resize())
})
</script>

<template>
  <el-drawer 
    :model-value="visible" 
    @update:model-value="(val) => emit('update:visible', val)"
    :title="`任务详情 #${taskId}`" 
    size="600px"
    destroy-on-close
  >
    <div v-if="loading && !task" class="loading-box" v-loading="true"></div>
    
    <div v-else-if="task" class="detail-container">
      <div class="status-banner" :class="task.status">
        <div class="status-icon">
          <el-icon :size="40">
            <CircleCheck v-if="task.status === 'success'" />
            <CircleClose v-else-if="task.status === 'failed'" />
            <Loading v-else class="is-loading" />
          </el-icon>
        </div>
        <div class="status-info">
          <div class="status-label">{{ task.status.toUpperCase() }}</div>
          <div class="model-label">Model ID: {{ task.model_id }}</div>
        </div>
        <div class="progress-circle">
          <el-progress 
            type="circle" 
            :percentage="task.progress" 
            :width="50" 
            :stroke-width="4" 
            :show-text="false" 
            color="#fff" 
            track-color="rgba(255,255,255,0.3)"
          />
          <span class="progress-val">{{ task.progress }}%</span>
        </div>
      </div>
      
      <el-alert 
        v-if="task.error_msg" 
        :title="task.error_msg" 
        type="error" 
        :closable="false" 
        show-icon 
        style="margin-bottom: 20px;" 
      />

      <div v-if="task.status === 'success' && taskResult" class="result-section">
        <div class="section-title">评测结果分析</div>
        <div class="chart-wrapper">
          <div id="result-radar" style="width: 100%; height: 300px; min-height: 300px;"></div>
           <el-empty 
             v-if="!taskResult.radar || taskResult.radar.length === 0" 
             description="暂无维度分析数据" 
             :image-size="100" 
             style="height: 300px; display: none;" 
             :style="{ display: (!taskResult.radar || taskResult.radar.length === 0) ? 'flex' : 'none' }"
          />
        </div>
        
        <el-table :data="taskResult.table" border stripe size="small">
          <el-table-column prop="capability" label="能力维度" width="100" />
          <el-table-column prop="dataset" label="数据集" show-overflow-tooltip />
          <el-table-column prop="metric" label="指标" width="80" />
          <el-table-column prop="score" label="得分" width="80" align="right">
             <template #default="scope">
               <b>{{ Number(scope.row.score).toFixed(1) }}</b>
             </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="log-section">
        <div class="section-title">运行日志</div>
        <div class="terminal-box" id="terminal-box">
          <div v-for="(log, i) in terminalLogs" :key="i" class="log-line">{{ log }}</div>
          <div v-if="task.status === 'running' || task.status === 'pending'" class="log-line blink">_</div>
        </div>
      </div>

    </div>
  </el-drawer>
</template>

<style scoped>
.loading-box { height: 200px; display: flex; align-items: center; justify-content: center; }
.detail-container { padding: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }

.status-banner { 
  display: flex; align-items: center; justify-content: space-between; 
  padding: 20px; border-radius: 12px; margin-bottom: 24px; color: #fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transition: all 0.3s;
}
.status-banner.success { background: linear-gradient(135deg, #67c23a 0%, #42b983 100%); }
.status-banner.failed { background: linear-gradient(135deg, #f56c6c 0%, #e54d42 100%); }
.status-banner.running, .status-banner.pending { background: linear-gradient(135deg, #409eff 0%, #3a8ee6 100%); }

.status-info { flex: 1; margin-left: 15px; }
.status-label { font-size: 20px; font-weight: bold; letter-spacing: 1px; }
.model-label { font-size: 13px; opacity: 0.9; margin-top: 4px; }
.progress-circle { position: relative; width: 50px; height: 50px; }
.progress-val { 
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); 
  font-size: 12px; font-weight: bold; 
}

.section-title { 
  font-size: 16px; font-weight: 600; color: #303133; 
  margin-bottom: 12px; border-left: 4px solid #409eff; padding-left: 10px; 
}

.result-section { margin-bottom: 30px; }
.chart-wrapper { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; margin-bottom: 15px; padding: 10px; position: relative; }

/* 终端模拟 */
.terminal-box { 
  background: #1e1e1e; color: #a6e22e; padding: 15px; height: 350px; /* 增加高度以便查看更多日志 */
  overflow-y: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; 
  border-radius: 8px; line-height: 1.5; box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
}
.log-line { white-space: pre-wrap; word-break: break-all; margin-bottom: 2px; }
.blink { animation: blink 1s infinite; font-weight: bold; }
@keyframes blink { 50% { opacity: 0; } }
</style>