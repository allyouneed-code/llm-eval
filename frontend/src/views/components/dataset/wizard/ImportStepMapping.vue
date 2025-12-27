<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, VideoPlay } from '@element-plus/icons-vue'
import { TASK_TYPES, TASK_SLOTS, TASK_METRICS } from '@/utils/datasetAdapter'

const props = defineProps(['state'])
const emit = defineEmits(['validate'])

// 常量
const taskTypes = [TASK_TYPES.CHOICE, TASK_TYPES.QA]

// ------------------------------------------
// 1. 核心逻辑：字段自动匹配 (Auto Mapping)
// ------------------------------------------
const autoMapColumns = () => {
  const headers = props.state.fileHeaders || []
  const currentSlots = TASK_SLOTS[props.state.taskType] || []
  
  // 简单的关键词匹配字典
  const keywordMap = {
    question: ['question', 'q_text', 'input', 'query'],
    optA: ['opt1', 'option_a', 'a', 'choice_a'],
    optB: ['opt2', 'option_b', 'b', 'choice_b'],
    optC: ['opt3', 'option_c', 'c', 'choice_c'],
    optD: ['opt4', 'option_d', 'd', 'choice_d'],
    answer: ['ans', 'answer', 'target', 'key', 'label', 'ground_truth'],
    prompt: ['prompt', 'input', 'question', 'src'],
    target: ['target', 'output', 'answer', 'dest']
  }

  // 遍历当前任务需要的插槽
  currentSlots.forEach(slot => {
    // 如果已经有值了，就不覆盖
    if (props.state.columnMapping[slot.key]) return

    // 尝试去 headers 里找
    const keywords = keywordMap[slot.key] || []
    const match = headers.find(h => {
      const lowerH = h.toLowerCase()
      // 1. 完全相等
      if (lowerH === slot.key.toLowerCase()) return true
      // 2. 包含关键词
      return keywords.some(k => lowerH.includes(k))
    })

    if (match) {
      props.state.columnMapping[slot.key] = match
    }
  })
}

// 监听任务类型切换，重置或重新匹配
const handleTaskTypeChange = (val) => {
  props.state.columnMapping = {} // 清空旧映射
  props.state.metrics = []       // 清空指标
  
  // 预选默认指标
  const defaultMetrics = TASK_METRICS[val]?.filter(m => m.default).map(m => m.value)
  if (defaultMetrics) props.state.metrics = defaultMetrics
  
  autoMapColumns()
}

// 初始化
onMounted(() => {
  if (!props.state.taskType) {
    props.state.taskType = TASK_TYPES.CHOICE.value // 默认选中选择题
    handleTaskTypeChange(TASK_TYPES.CHOICE.value)
  }
})

// ------------------------------------------
// 2. 预览逻辑 (Real-time Preview)
// ------------------------------------------
const previewContent = computed(() => {
  const { taskType, columnMapping, previewRows } = props.state
  if (!previewRows || previewRows.length === 0) return '等待数据解析...'
  
  const row = previewRows[0] // 拿第一行数据做演示
  const mapping = columnMapping

  if (taskType === TASK_TYPES.CHOICE.value) {
    // 没选题目列时，显示占位符
    const q = mapping.question ? row[mapping.question] : '{Question}'
    const a = mapping.optA ? row[mapping.optA] : '{A}'
    const b = mapping.optB ? row[mapping.optB] : '{B}'
    const c = mapping.optC ? row[mapping.optC] : ''
    const d = mapping.optD ? row[mapping.optD] : ''
    
    let text = `Question: ${q}\nA. ${a}\nB. ${b}`
    if (c) text += `\nC. ${c}`
    if (d) text += `\nD. ${d}`
    text += `\nAnswer:`
    return text
  }
  
  if (taskType === TASK_TYPES.QA.value) {
    const p = mapping.prompt ? row[mapping.prompt] : '{Input}'
    return `Question: ${p}\nAnswer:`
  }
  
  return '请选择任务类型'
})

// ------------------------------------------
// 3. 校验逻辑 (供父组件调用)
// ------------------------------------------
const validate = async () => {
  const slots = TASK_SLOTS[props.state.taskType]
  for (const slot of slots) {
    if (slot.required && !props.state.columnMapping[slot.key]) {
      ElMessage.warning(`请完成 [${slot.label}] 的字段映射`)
      return false
    }
  }
  return true
}

defineExpose({ validate })
</script>

<template>
  <div class="step-mapping">
    
    <div class="task-selector">
      <div 
        v-for="type in taskTypes" 
        :key="type.value"
        class="task-card"
        :class="{ active: state.taskType === type.value }"
        @click="state.taskType = type.value; handleTaskTypeChange(type.value)"
      >
        <div class="radio-circle"></div>
        <div class="task-info">
          <div class="task-label">{{ type.label }}</div>
          <div class="task-desc">{{ type.desc }}</div>
        </div>
      </div>
    </div>

    <el-row :gutter="30" style="margin-top: 25px;">
      
      <el-col :span="14">
        <div class="section-title"><el-icon><Connection /></el-icon> 字段映射 (Mapping)</div>
        <div class="mapping-container">
          <el-form label-position="left" label-width="140px">
            <template v-if="state.taskType">
              <el-form-item 
                v-for="slot in TASK_SLOTS[state.taskType]" 
                :key="slot.key" 
                :required="slot.required"
              >
                <template #label>
                  <span class="slot-label" :title="slot.label">{{ slot.label }}</span>
                </template>
                <el-select 
                  v-model="state.columnMapping[slot.key]" 
                  placeholder="请选择对应列" 
                  style="width: 100%"
                  clearable
                >
                  <el-option 
                    v-for="col in state.fileHeaders" 
                    :key="col" 
                    :label="col" 
                    :value="col" 
                  />
                </el-select>
              </el-form-item>
            </template>
          </el-form>
        </div>
      </el-col>

      <el-col :span="10">
        <div class="section-title"><el-icon><VideoPlay /></el-icon> 效果预览 (Preview)</div>
        <div class="preview-box">
          <div class="preview-tag">Prompt Template (Row 1)</div>
          <pre class="preview-content">{{ previewContent }}</pre>
          <div class="preview-tip" v-if="state.taskType === 'choice'">
             * 系统将自动拼接 Question + Options + Answer Trigger
          </div>
        </div>
      </el-col>

    </el-row>
  </div>
</template>

<style scoped>
.task-selector { display: flex; gap: 15px; }
.task-card { 
  flex: 1; border: 1px solid #dcdfe6; border-radius: 8px; padding: 15px; 
  cursor: pointer; display: flex; align-items: center; transition: all 0.2s;
}
.task-card:hover { border-color: #b3d8ff; background-color: #f0f9eb; }
.task-card.active { border-color: #409eff; background-color: #ecf5ff; box-shadow: 0 2px 8px rgba(64,158,255,0.15); }

.radio-circle { 
  width: 16px; height: 16px; border: 2px solid #dcdfe6; border-radius: 50%; margin-right: 12px; 
  position: relative; 
}
.active .radio-circle { border-color: #409eff; background-color: #409eff; }
.active .radio-circle::after {
  content: ''; position: absolute; width: 6px; height: 6px; background: #fff; 
  border-radius: 50%; top: 3px; left: 3px;
}

.task-label { font-weight: bold; color: #303133; font-size: 14px; }
.task-desc { font-size: 12px; color: #909399; margin-top: 4px; }

.section-title { font-size: 14px; font-weight: bold; color: #606266; margin-bottom: 15px; display: flex; align-items: center; gap: 6px; }
.slot-label { font-size: 13px; color: #606266; }

.preview-box { 
  background: #282c34; border-radius: 6px; padding: 0; overflow: hidden; height: 260px; 
  display: flex; flex-direction: column; 
}
.preview-tag { 
  background: #21252b; color: #abb2bf; font-size: 11px; padding: 6px 10px; font-family: monospace; 
  border-bottom: 1px solid #3e4451;
}
.preview-content { 
  flex: 1; margin: 0; padding: 15px; color: #98c379; font-family: 'Consolas', 'Monaco', monospace; 
  font-size: 13px; white-space: pre-wrap; overflow-y: auto; line-height: 1.5;
}
.preview-tip { background: #333842; color: #d19a66; font-size: 11px; padding: 5px 10px; font-style: italic; }
</style>