<script setup>
import { ref, reactive, computed, watch, defineAsyncComponent } from 'vue'
import { ElMessage } from 'element-plus'
import { createDataset } from '@/api/dataset'
import { generateConfigPayload } from '@/utils/datasetAdapter' // 引入上一阶段写的 Adapter

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

// 异步加载步骤组件 (避免一次性加载所有代码)
const StepUpload = defineAsyncComponent(() => import('./wizard/ImportStepUpload.vue'))
const StepMapping = defineAsyncComponent(() => import('./wizard/ImportStepMapping.vue'))
const StepConfig = defineAsyncComponent(() => import('./wizard/ImportStepConfig.vue'))

// ==========================================
// 1. 状态管理 (State)
// ==========================================
const activeStep = ref(0)
const submitting = ref(false)
const stepRef = ref(null) // 用于调用子组件的 validate 方法

// 核心状态对象：在所有步骤中共享
const importState = reactive({
  // Step 1 Data
  meta: {
    name: '',
    category: '',
    description: ''
  },
  file: null,          // 原始 File 对象
  fileHeaders: [],     // 解析出的 CSV/JSONL 表头 ['col1', 'col2']
  previewRows: [],     // 预览用的前5行数据
  
  // Step 2 Data
  taskType: '',        // 'choice' | 'qa'
  columnMapping: {},   // { question: 'q_col', answer: 'ans_col' ... }
  
  // Step 3 Data
  metrics: [],         // ['Accuracy', 'ROUGE'...]
  postProcess: ''      // 'first_option' | 'jieba' ...
})

// ==========================================
// 2. 流程控制 (Flow)
// ==========================================
const steps = [
  { component: StepUpload, title: '上传文件' },
  { component: StepMapping, title: '字段映射' },
  { component: StepConfig, title: '评测配置' }
]

const currentComponent = computed(() => steps[activeStep.value].component)
const isLastStep = computed(() => activeStep.value === steps.length - 1)

// 重置状态
watch(() => props.visible, (val) => {
  if (val) {
    activeStep.value = 0
    importState.meta = { name: '', category: '', description: '' }
    importState.file = null
    importState.fileHeaders = []
    importState.previewRows = []
    importState.taskType = ''
    importState.columnMapping = {}
    importState.metrics = []
    importState.postProcess = ''
  }
})

const handleNext = async () => {
  // 调用子组件的校验方法 (如果存在)
  if (stepRef.value && stepRef.value.validate) {
    const valid = await stepRef.value.validate()
    if (!valid) return
  }
  
  if (activeStep.value < steps.length - 1) {
    activeStep.value++
  } else {
    handleFinalSubmit()
  }
}

const handlePrev = () => {
  if (activeStep.value > 0) activeStep.value--
}

// ==========================================
// 3. 提交逻辑 (Submit)
// ==========================================
const handleFinalSubmit = async () => {
  submitting.value = true
  try {
    // 1. 使用 Adapter 生成 Configs JSON
    const configs = generateConfigPayload(importState)
    
    // 2. 构建 FormData
    const formData = new FormData()
    formData.append('name', importState.meta.name)
    formData.append('category', importState.meta.category)
    formData.append('description', importState.meta.description || '')
    formData.append('file', importState.file)
    formData.append('configs_json', JSON.stringify(configs))
    
    // 3. 发送请求
    await createDataset(formData)
    
    ElMessage.success('导入成功')
    emit('update:visible', false)
    emit('success')
  } catch (error) {
    console.error(error)
    ElMessage.error('创建失败: ' + (error.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog 
    :model-value="visible" 
    @update:model-value="(val) => emit('update:visible', val)"
    title="导入数据集 (向导模式)" 
    width="800px" 
    :close-on-click-modal="false"
    destroy-on-close
    top="5vh"
  >
    <div class="step-header">
      <el-steps :active="activeStep" finish-status="success" align-center>
        <el-step v-for="step in steps" :key="step.title" :title="step.title" />
      </el-steps>
    </div>

    <div class="step-content">
      <keep-alive>
        <component 
          :is="currentComponent" 
          :state="importState"
          ref="stepRef"
        />
      </keep-alive>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button v-if="activeStep > 0" @click="handlePrev">上一步</el-button>
        <el-button type="primary" @click="handleNext" :loading="submitting">
          {{ isLastStep ? '完成导入' : '下一步' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.step-header { margin-bottom: 25px; padding: 0 20px; }
.step-content { 
  min-height: 350px; 
  max-height: 550px; 
  overflow-y: auto; 
  padding: 0 20px;
}
.dialog-footer { display: flex; justify-content: flex-end; gap: 10px; }
</style>