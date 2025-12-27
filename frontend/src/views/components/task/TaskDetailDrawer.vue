<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
// 1. 引入你在 task.js 中定义的 getTask 方法
import { getTask } from '@/api/task'
import { CircleCheck, CircleClose, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  taskId: { type: [Number, String], default: null }, // 接收任务 ID
  initialTask: { type: Object, default: null }       // 接收列表页传来的初始数据（快照）
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
const taskDetail = ref(null) // 存储接口返回的完整详情
const terminalLogs = ref([]) // 模拟日志存储
let logInterval = null       // 轮询定时器
let myChart = null           // ECharts 实例

// 核心：优先使用接口返回的详情，如果没有则回退到 initialTask
const task = computed(() => taskDetail.value || props.initialTask)

// 解析后端返回的 JSON 结果字符串
const taskResult = computed(() => {
  if (!task.value?.result_summary) return null
  try {
    return JSON.parse(task.value.result_summary)
  } catch (e) {
    console.error("Result parse error:", e)
    return null
  }
})

// 监听弹窗打开状态
watch(() => props.visible, async (val) => {
  if (val && props.taskId) {
    // 打开时立即获取最新数据
    await fetchTaskDetail()
    
    // 根据状态决定下一步操作
    if (task.value?.status === 'success') {
      nextTick(() => initRadarChart())
    } else if (task.value?.status === 'running' || task.value?.status === 'pending') {
      startLogPolling()
    }
  } else {
    // 关闭时清理状态
    stopPolling()
    taskDetail.value = null
    terminalLogs.value = []
  }
})

// 主动调用 API 获取详情
const fetchTaskDetail = async () => {
  if (!props.taskId) return
  // 仅在初次无数据时显示 loading，避免轮询时闪烁
  if (!taskDetail.value) loading.value = true
  
  try {
    // 调用 task.js 中的 getTask
    const res = await getTask(props.taskId)
    taskDetail.value = res
  } catch (e) {
    console.error("Failed to fetch task detail:", e)
  } finally {
    loading.value = false
  }
}

// 开启轮询 (用于实时更新日志和进度)
const startLogPolling = () => {
  if (logInterval) clearInterval(logInterval)
  terminalLogs.value = ['> Connecting to runner...', '> Waiting for updates...']
  
  logInterval = setInterval(async () => {
    // 1. 刷新任务状态
    await fetchTaskDetail()
    
    // 2. 检查状态变化
    if (task.value?.status === 'success') {
      terminalLogs.value.push(`> [System] Task Finished successfully.`)
      stopPolling()
      nextTick(() => initRadarChart())
      return
    }
    if (task.value?.status === 'failed') {
      terminalLogs.value.push(`> [System] Task Failed: ${task.value.error_msg}`)
      stopPolling()
      return
    }

    // 3. 模拟滚动日志 (因为目前后端暂无实时日志流接口，这里仅做演示效果)
    // 实际项目中，你可以将 taskDetail.value.latest_log 展示在这里
    const msgs = ['Running inference...', 'Evaluating batch...', 'Processing metrics...', 'GPU utility: 85%']
    if (task.value?.status === 'running') {
       terminalLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msgs[Math.floor(Math.random()*msgs.length)]}`)
       scrollToBottom()
    }
    
  }, 2000) // 每2秒轮询一次
}

const stopPolling = () => {
  if (logInterval) {
    clearInterval(logInterval)
    logInterval = null
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    const terminal = document.getElementById('terminal-box')
    if(terminal) terminal.scrollTop = terminal.scrollHeight
  })
}

// 初始化雷达图
const initRadarChart = () => {
  const chartDom = document.getElementById('result-radar')
  if (!chartDom || !taskResult.value?.radar) return
  
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
  window.addEventListener('resize', () => myChart?.resize())
}

onUnmounted(() => {
  stopPolling()
  if (myChart) myChart.dispose()
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
          <div id="result-radar" style="width: 100%; height: 300px;"></div>
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
          <div v-if="task.status === 'running'" class="log-line blink">_</div>
        </div>
      </div>

    </div>
  </el-drawer>
</template>

<style scoped>
.loading-box { height: 200px; display: flex; align-items: center; justify-content: center; }
.detail-container { padding: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }

/* 状态 Banner */
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
.chart-wrapper { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; margin-bottom: 15px; padding: 10px; }

/* 终端模拟 */
.terminal-box { 
  background: #1e1e1e; color: #a6e22e; padding: 15px; height: 250px; 
  overflow-y: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; 
  border-radius: 8px; line-height: 1.5; box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
}
.log-line { white-space: pre-wrap; word-break: break-all; }
.blink { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>