<template>
  <div class="report-wrapper">
    <div class="report-header">
      <div class="header-left">
        <el-button @click="$emit('back')" icon="ArrowLeft" circle class="back-btn" />
        <div class="title-block">
          <h1 class="page-title">评测对比报告</h1>
          <span class="report-date">生成时间: {{ new Date().toLocaleString() }}</span>
        </div>
      </div>
      <el-button type="primary" @click="exportToImage" class="export-btn">
        <el-icon class="mr-1"><Camera /></el-icon> 导出长图
      </el-button>
    </div>

    <div ref="reportContainer" class="report-content">
      
      <div class="section-card scheme-info">
        <div class="info-row">
          <div class="info-label">评测方案</div>
          <div class="info-value scheme-name">
            <el-icon class="scheme-icon"><CollectionTag /></el-icon>
            {{ report.scheme_name }}
          </div>
        </div>
        <el-divider direction="horizontal" class="my-3" border-style="dashed" />
        <div class="info-row">
          <div class="info-label">包含数据集</div>
          <div class="info-value dataset-list">
            <el-tag 
              v-for="ds in uniqueDatasets" 
              :key="ds" 
              type="info" 
              effect="plain" 
              size="small"
              class="ds-tag"
            >
              {{ ds }}
            </el-tag>
            <span class="ds-count">共 {{ uniqueDatasets.length }} 个评测集</span>
          </div>
        </div>
      </div>

      <div class="section-card models-section">
        <div class="card-title">
          <span class="text">参评模型配置</span>
          <span class="sub-text">Models Configuration</span>
        </div>
        
        <div class="models-grid">
          <div 
            v-for="(model, index) in report.models" 
            :key="model.task_id"
            class="model-card"
            :class="{ 'is-base': index === 0 }"
          >
            <div class="model-role" :class="index === 0 ? 'role-base' : 'role-candidate'">
              {{ index === 0 ? '基准 (Base)' : `对照 ${index}` }}
            </div>
            
            <div class="model-body">
              <div class="icon-wrapper">
                <el-icon><Cpu /></el-icon>
              </div>
              <div class="model-meta">
                <div class="model-name" :title="model.model_name">
                  {{ model.model_name }}
                </div>
                <div class="task-id-tag">
                  Task #{{ model.task_id }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="section-card radar-section">
        <div class="card-title">
          <span class="text">能力维度对比</span>
          <span class="sub-text">Capability Radar</span>
        </div>
        <div class="chart-container">
          <div ref="radarChartRef" class="echarts-dom"></div>
        </div>
      </div>

      <div class="section-card table-section">
        <div class="card-title">
          <span class="text">详细指标差异</span>
          <span class="sub-text">Detailed Metrics</span>
        </div>
        <el-table 
          :data="report.table_data" 
          border 
          stripe
          :header-cell-style="{ background: '#f8fafc', color: '#4b5563', fontWeight: '600' }"
        >
          <el-table-column prop="dataset" label="数据集" fixed width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="dataset-name">{{ row.dataset }}</span>
              <span class="metric-name">{{ row.metric }}</span>
            </template>
          </el-table-column>
          
          <el-table-column 
            v-for="(model, index) in report.models" 
            :key="model.task_id"
            min-width="160"
            align="center"
          >
            <template #header>
              <div class="col-header">
                <span class="col-model-name">{{ model.model_name }}</span>
                <span v-if="index===0" class="col-badge-base">Base</span>
              </div>
            </template>
            
            <template #default="{ row }">
              <div class="score-value">{{ formatScore(row['task_' + model.task_id]) }}</div>
              
              <div v-if="index > 0 && row['diff_' + model.task_id] != null" 
                   class="diff-badge"
                   :class="getDiffClass(row['diff_' + model.task_id])">
                <el-icon v-if="row['diff_' + model.task_id] > 0"><Top /></el-icon>
                <el-icon v-else-if="row['diff_' + model.task_id] < 0"><Bottom /></el-icon>
                <span v-else>=</span>
                {{ Math.abs(row['diff_' + model.task_id]).toFixed(2) }}
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import html2canvas from 'html2canvas'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Camera, Top, Bottom, CollectionTag, Cpu } from '@element-plus/icons-vue'

const props = defineProps({
  report: { type: Object, required: true }
})

defineEmits(['back'])

const radarChartRef = ref(null)
const reportContainer = ref(null)
let chartInstance = null

// --- 数据处理 ---

// 提取唯一数据集名称用于展示方案内容
const uniqueDatasets = computed(() => {
  if (!props.report.table_data) return []
  const sets = new Set(props.report.table_data.map(row => row.dataset))
  return Array.from(sets)
})

const formatScore = (val) => (val == null ? '-' : Number(val).toFixed(2))

const getDiffClass = (d) => {
  if (d > 0) return 'is-up'
  if (d < 0) return 'is-down'
  return 'is-flat'
}

// --- 图表逻辑 ---

const initChart = () => {
  if (!radarChartRef.value) return
  if (chartInstance) chartInstance.dispose()
  
  chartInstance = echarts.init(radarChartRef.value)
  const option = {
    color: ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399'],
    tooltip: { trigger: 'item' },
    legend: { 
        bottom: 0,
        // 使用干净的名字
        data: props.report.models.map(m => m.model_name),
        textStyle: { color: '#606266' },
        icon: 'circle'
    },
    radar: {
      indicator: props.report.radar_indicators,
      radius: '68%',
      center: ['50%', '48%'],
      shape: 'circle',
      splitNumber: 4,
      axisName: { color: '#64748b', fontSize: 12, fontWeight: 'bold' },
      splitArea: { areaStyle: { color: ['#fff', '#f8fafc'] } },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      splitLine: { lineStyle: { color: '#e2e8f0' } }
    },
    series: [{
      type: 'radar',
      // 将 data 里的 name 也替换为 clean name
      data: props.report.radar_data.map((item, idx) => ({
        ...item,
        name: props.report.models[idx].model_name
      })),
      symbol: 'circle',
      symbolSize: 6,
      areaStyle: { opacity: 0.2 },
      lineStyle: { width: 2 }
    }]
  }
  chartInstance.setOption(option)
}

onMounted(() => {
  nextTick(initChart)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) chartInstance.dispose()
})

const handleResize = () => chartInstance && chartInstance.resize()

const exportToImage = async () => {
    if (!reportContainer.value) return
    try {
        const canvas = await html2canvas(reportContainer.value, { 
            scale: 2, 
            useCORS: true, 
            backgroundColor: '#f1f5f9', // 与主背景色一致
            logging: false
        })
        const link = document.createElement('a')
        link.download = `Compare_Report_${Date.now()}.png`
        link.href = canvas.toDataURL('image/png')
        link.click()
    } catch (e) { ElMessage.error("导出失败") }
}
</script>

<style scoped>
.report-wrapper {
  max-width: 1200px;
  margin: 0 auto;
}

/* 顶部 Header */
.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.back-btn {
  border: 1px solid #e5e7eb;
  color: #6b7280;
}
.back-btn:hover {
  background-color: #f3f4f6;
  color: #111827;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #111827;
  margin: 0;
  line-height: 1.2;
}
.report-date {
  font-size: 13px;
  color: #9ca3af;
  margin-top: 2px;
  display: block;
}

/* 报告容器 */
.report-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  /* 导出时的背景色 */
  background-color: #f1f5f9; 
  padding: 20px;
  border-radius: 12px;
}

/* 通用卡片样式 */
.section-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  border: 1px solid rgba(229, 231, 235, 0.5);
}

.card-title {
  margin-bottom: 20px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  border-left: 4px solid #3b82f6;
  padding-left: 12px;
}
.card-title .text {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}
.card-title .sub-text {
  font-size: 12px;
  color: #9ca3af;
  text-transform: uppercase;
  font-weight: 500;
  letter-spacing: 0.5px;
}

/* --- 评测方案详情 --- */
.scheme-info {
  background: linear-gradient(to right, #ffffff, #f8fafc);
}
.info-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.info-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
  min-width: 80px;
  padding-top: 4px;
}
.info-value {
  flex: 1;
}
.scheme-name {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 8px;
}
.scheme-icon {
  color: #3b82f6;
}
.dataset-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.ds-count {
  font-size: 12px;
  color: #9ca3af;
  margin-left: 8px;
}

/* --- 模型列表 (UI 统一化) --- */
.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.model-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s;
  position: relative;
}
.model-card:hover {
  border-color: #bfdbfe;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
  transform: translateY(-2px);
}
/* 基准模型特殊边框 */
.model-card.is-base {
  border-color: #bfdbfe;
  background-color: #fbfdff;
}

.model-role {
  font-size: 11px;
  text-align: center;
  padding: 4px 0;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.role-base {
  background-color: #eff6ff;
  color: #3b82f6;
}
.role-candidate {
  background-color: #f3f4f6;
  color: #6b7280;
}

.model-body {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.icon-wrapper {
  width: 40px;
  height: 40px;
  background: #f3f4f6;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4b5563;
  font-size: 20px;
}
.is-base .icon-wrapper {
  background: #eff6ff;
  color: #3b82f6;
}

.model-meta {
  flex: 1;
  min-width: 0; /* 允许文本截断 */
}
.model-name {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.task-id-tag {
  display: inline-block;
  font-size: 11px;
  color: #9ca3af;
  background: #f9fafb;
  padding: 1px 6px;
  border: 1px solid #f3f4f6;
  border-radius: 4px;
}

/* --- 图表区 --- */
.chart-container {
  height: 450px;
  padding: 10px;
}
.echarts-dom {
  width: 100%;
  height: 100%;
}

/* --- 表格区 --- */
.dataset-name {
  display: block;
  font-weight: 600;
  color: #374151;
  font-size: 13px;
}
.metric-name {
  font-size: 12px;
  color: #9ca3af;
}

.col-header {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.col-model-name {
  font-weight: 600;
  color: #374151;
  line-height: 1.2;
}
.col-badge-base {
  font-size: 10px;
  background: #eff6ff;
  color: #3b82f6;
  padding: 1px 6px;
  border-radius: 10px;
  margin-top: 4px;
}

.score-value {
  font-family: 'Roboto Mono', monospace;
  font-size: 14px;
  font-weight: 500;
  color: #111827;
}

.diff-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  margin-top: 4px;
  font-weight: 700;
}
.is-up { background: #f0fdf4; color: #16a34a; }
.is-down { background: #fef2f2; color: #dc2626; }
.is-flat { background: #f3f4f6; color: #9ca3af; }
</style>