<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  visible: { type: Boolean, default: false },
  task: { type: Object, default: null },
  modelName: { type: String, default: '' }
})

const emit = defineEmits(['update:visible'])

const terminalLogs = ref([])
let logInterval = null
let myChart = null

const taskResult = computed(() => {
  if (!props.task?.result_summary) return null
  try { return JSON.parse(props.task.result_summary) } catch { return null }
})

// 监听任务变化，控制日志和图表
watch(() => props.task, (newVal) => {
  if (!newVal || !props.visible) return

  if (newVal.status === 'running' || newVal.status === 'pending') {
    startFakeLogs()
  } else if (newVal.status === 'success') {
    stopLogs()
    nextTick(() => initRadarChart())
  }
}, { immediate: true })

// 监听可见性变化
watch(() => props.visible, (val) => {
  if (!val) {
    stopLogs()
  } else if (props.task) {
    // 重新打开时恢复状态
    if (props.task.status === 'running') startFakeLogs()
    if (props.task.status === 'success') nextTick(() => initRadarChart())
  }
})

const startFakeLogs = () => {
  if (logInterval) clearInterval(logInterval)
  if (terminalLogs.value.length === 0) terminalLogs.value = ['> System init...']
  
  const logPool = ['Loading weights...', 'Allocating GPU...', 'Inference batch...', 'Calculating metrics...']
  
  logInterval = setInterval(() => {
    if (props.task?.status !== 'running') { stopLogs(); return }
    const msg = logPool[Math.floor(Math.random() * logPool.length)]
    terminalLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
    const terminal = document.getElementById('terminal-box')
    if(terminal) terminal.scrollTop = terminal.scrollHeight
  }, 1500)
}

const stopLogs = () => {
  if (logInterval) {
    clearInterval(logInterval)
    logInterval = null
  }
}

const initRadarChart = () => {
  const chartDom = document.getElementById('result-radar')
  if (!chartDom || !taskResult.value?.radar) return
  
  if (myChart) myChart.dispose()
  myChart = echarts.init(chartDom)
  
  const option = {
    tooltip: {},
    radar: { 
      indicator: taskResult.value.radar.map(r => ({ name: r.name, max: r.max })), 
      radius: '65%' 
    },
    series: [{ 
      type: 'radar', 
      data: [{ 
        value: taskResult.value.radar.map(r => r.score), 
        name: 'Model Score', 
        itemStyle: { color: '#409EFF' }, 
        areaStyle: { opacity: 0.2 } 
      }] 
    }]
  }
  myChart.setOption(option)
}

onUnmounted(() => {
  stopLogs()
  if (myChart) myChart.dispose()
})
</script>

<template>
  <el-drawer 
    :model-value="visible" 
    @update:model-value="(val) => emit('update:visible', val)"
    :title="task ? `Task #${task.id}` : '详情'" 
    size="50%"
    destroy-on-close
  >
    <div v-if="task" class="detail-container">
      <div class="status-banner" :class="task.status">
        <div class="status-text">
          <h2>{{ task.status.toUpperCase() }}</h2>
          <p>{{ modelName }}</p>
        </div>
        <el-progress type="dashboard" :percentage="task.progress" :width="60" />
      </div>
      
      <div v-if="task.status === 'running' || task.status === 'pending'" class="terminal-box" id="terminal-box">
        <div v-for="(log,i) in terminalLogs" :key="i">{{ log }}</div>
      </div>
      
      <div v-if="task.status === 'success' && taskResult">
        <div id="result-radar" style="width:100%;height:300px;"></div>
        <el-table :data="taskResult.table" border size="small" style="margin-top:10px;">
          <el-table-column prop="capability" label="Capability" width="100"/>
          <el-table-column prop="dataset" label="Dataset" />
          <el-table-column prop="score" label="Score" />
        </el-table>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.detail-container { padding: 20px; }
.status-banner { display: flex; justify-content: space-between; background: #409EFF; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
.status-banner.success { background: #67C23A; }
.status-banner.failed { background: #F56C6C; }
.status-banner.pending { background: #909399; }
.status-text h2 { margin: 0; font-size: 24px; }
.status-text p { margin: 5px 0 0; opacity: 0.9; }
.terminal-box { background: #1e1e1e; color: #67c23a; padding: 15px; height: 300px; overflow-y: auto; font-family: monospace; border-radius: 6px; }
</style>