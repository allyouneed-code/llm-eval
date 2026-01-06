<script setup>
import { computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, List } from '@element-plus/icons-vue' 
// 🌟 1. 引入 MODALITY_DEFAULT_TASK 用于自动推断
import { TASK_METRICS, MODALITY_DEFAULT_TASK } from '@/utils/datasetAdapter'

const props = defineProps(['state', 'uploadMode'])

// ==========================================
// 1. 动态获取配置选项
// ==========================================

const availableMetrics = computed(() => {
  const type = props.state.taskType
  return TASK_METRICS[type] || []
})

// ==========================================
// 2. 状态初始化
// ==========================================

onMounted(() => {
  // 🌟 2. 核心修复：多模态自动补全 Task Type
  // 如果当前是多模态数据（非 Text），且尚未设置 taskType（因为上一步可能隐藏了选择框），
  // 则根据模态自动填入默认值（例如 Image -> qa），确保下方能显示出指标。
  if (!props.state.taskType && props.state.modality && props.state.modality !== 'Text') {
    const defaultTask = MODALITY_DEFAULT_TASK[props.state.modality]
    if (defaultTask) {
      props.state.taskType = defaultTask
      console.log(`[Auto-Config] Detected ${props.state.modality}, auto-set taskType to '${defaultTask}'`)
    }
  }

  //原有逻辑：默认选中推荐指标
  const { metrics } = props.state
  if (metrics.length === 0) {
    // 注意：availableMetrics 是 computed，依赖上面的 taskType 赋值
    // Vue 的响应式系统会自动处理，但为了确保在 onMounted 内能立即拿到值，
    // 这里我们直接依赖 computed 的 .value
    const defaults = availableMetrics.value.filter(m => m.default).map(m => m.value)
    props.state.metrics = defaults
  }
})

// ==========================================
// 3. 生成预览清单
// ==========================================

const configPreviewList = computed(() => {
  const baseName = props.state.meta.name || 'Dataset'
  
  return props.state.metrics.map(metric => {
    return {
      name: `${baseName}_${metric}`,
      metric: metric,
      label: availableMetrics.value.find(m => m.value === metric)?.label
    }
  })
})

// ==========================================
// 4. 校验方法
// ==========================================
const validate = async () => {
  if (props.state.metrics.length === 0) {
    ElMessage.warning('请至少选择一个评测指标')
    return false
  }
  return true
}

defineExpose({ validate })
</script>

<template>
  <div class="step-config">
    <el-row :gutter="40">
      
      <el-col :span="14">
        
        <div class="config-section">
          <div class="section-title">
            <el-icon><DataAnalysis /></el-icon> 
            <span>评测指标 (Metrics)</span>
            <span class="sub-tip">可多选</span>
          </div>
          
          <div class="section-body">
            <el-checkbox-group v-model="state.metrics" class="metric-group">
              <div 
                v-for="item in availableMetrics" 
                :key="item.value"
                class="metric-item"
                :class="{ active: state.metrics.includes(item.value) }"
              >
                <el-checkbox :label="item.value">
                  <span class="m-label">{{ item.label }}</span>
                </el-checkbox>
              </div>
            </el-checkbox-group>
            
            <div class="empty-tip" v-if="availableMetrics.length === 0">
              暂无适用于当前模态 ({{ state.modality || '未知' }}) 或任务类型的指标。
            </div>
          </div>
        </div>

      </el-col>

      <el-col :span="10">
        <div class="summary-card">
          <div class="card-header">
            <el-icon><List /></el-icon> 导入概览 (Summary)
          </div>
          <div class="card-body">
            <div class="summary-row">
              <span class="label">数据集名称:</span>
              <span class="value">{{ state.meta.name }}</span>
            </div>

            <div class="summary-row" v-if="uploadMode === 'multimodal' || state.modality !== 'Text'">
              <span class="label">数据模态:</span>
              <span class="value">{{ state.modality }}</span>
            </div>

            <div class="summary-row">
              <span class="label">任务类型:</span>
              <span class="value">
                {{ state.taskType === 'choice' ? '客观选择题' : (state.taskType === 'qa' ? '开放式问答' : state.taskType || '-') }}
              </span>
            </div>
            
            <div class="divider"></div>
            
            <div class="sub-header">即将创建的配置 ({{ configPreviewList.length }}) :</div>
            <div class="config-list">
               <div v-for="cfg in configPreviewList" :key="cfg.name" class="config-item-preview">
                 <div class="cfg-top">
                   <span class="cfg-name">{{ cfg.name }}</span>
                 </div>
                 <div class="cfg-detail">
                    <span>{{ cfg.label }}</span>
                 </div>
               </div>
               <div v-if="configPreviewList.length === 0" class="no-config">
                 暂未选择指标
               </div>
            </div>
          </div>
        </div>
      </el-col>

    </el-row>
  </div>
</template>

<style scoped>
.config-section { background: #fff; }
.section-title { 
  font-size: 15px; font-weight: bold; color: #303133; margin-bottom: 15px; 
  display: flex; align-items: center; gap: 8px; 
}
.sub-tip { font-size: 12px; color: #909399; font-weight: normal; background: #f4f4f5; padding: 2px 6px; border-radius: 4px; }

.metric-group { display: flex; flex-direction: column; gap: 10px; }
.metric-item { 
  border: 1px solid #dcdfe6; border-radius: 6px; padding: 10px 15px; transition: all 0.2s; 
}
.metric-item:hover { border-color: #c6e2ff; background-color: #f0f9eb; }
.metric-item.active { border-color: #409eff; background-color: #ecf5ff; }
.m-label { font-weight: 500; color: #303133; }

/* Summary Card Styles */
.summary-card { 
  background: #f8f9fa; border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; height: 100%;
}
.card-header { 
  background: #eef1f6; padding: 12px 15px; font-weight: bold; color: #606266; font-size: 14px; 
  display: flex; align-items: center; gap: 6px; border-bottom: 1px solid #e4e7ed;
}
.card-body { padding: 15px; }

.summary-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; }
.summary-row .label { color: #909399; }
.summary-row .value { font-weight: 600; color: #303133; }

.divider { height: 1px; background: #ebeef5; margin: 15px 0; }
.sub-header { font-size: 12px; color: #909399; margin-bottom: 10px; font-weight: bold; }

.config-list { display: flex; flex-direction: column; gap: 8px; }
.config-item-preview { 
  background: #fff; border: 1px solid #ebeef5; padding: 10px; border-radius: 4px; 
  box-shadow: 0 1px 2px rgba(0,0,0,0.03); 
}
.cfg-top { margin-bottom: 4px; }
.cfg-name { font-size: 13px; font-weight: bold; color: #303133; }
.cfg-detail { font-size: 12px; color: #606266; }

.no-config { text-align: center; color: #ccc; font-size: 12px; padding: 20px; }
</style>