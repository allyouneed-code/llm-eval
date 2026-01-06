<script setup>
import { ref, reactive, computed, watch, defineAsyncComponent } from 'vue'
import { ElMessage } from 'element-plus'
import { createDataset } from '@/api/dataset'
import { generateConfigPayload } from '@/utils/datasetAdapter'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

// 异步加载步骤组件
const StepUpload = defineAsyncComponent(() => import('./wizard/ImportStepUpload.vue'))
const StepMapping = defineAsyncComponent(() => import('./wizard/ImportStepMapping.vue'))
const StepConfig = defineAsyncComponent(() => import('./wizard/ImportStepConfig.vue'))

// ==========================================
// 1. 状态管理 (State)
// ==========================================
const activeStep = ref(0)
const submitting = ref(false)
const stepRef = ref(null)
const uploadMode = ref('text') // 🌟 新增：'text' | 'multimodal'

// 核心状态对象
const importState = reactive({
  // Meta
  meta: { name: '', category: '', description: '' },
  modality: 'Text', // 🌟 新增
  
  // File
  file: null,
  fileHeaders: [],
  previewRows: [],
  
  // Logic
  taskType: '',
  columnMapping: {},
  
  // Config
  metrics: [],
  postProcess: ''
})

// ==========================================
// 2. 流程控制 (Flow)
// ==========================================

// 🌟 动态计算步骤：多模态模式跳过“字段映射”
const steps = computed(() => {
  const list = [
    { component: StepUpload, title: '上传文件' }
  ]
  
  // 仅文本模式需要映射
  if (uploadMode.value === 'text') {
    list.push({ component: StepMapping, title: '字段映射' })
  }
  
  list.push({ component: StepConfig, title: '评测配置' })
  return list
})

const currentComponent = computed(() => steps.value[activeStep.value].component)
const isLastStep = computed(() => activeStep.value === steps.value.length - 1)

// 监听弹窗打开，重置状态
watch(() => props.visible, (val) => {
  if (val) {
    activeStep.value = 0
    uploadMode.value = 'text' // 默认重置为文本
    resetState()
  }
})

// 监听模式切换
watch(uploadMode, (val) => {
  activeStep.value = 0
  resetState()
  
  if (val === 'text') {
    importState.modality = 'Text'
    importState.taskType = '' // 文本模式由 Mapping 步骤决定任务类型
  } else {
    // 多模态默认初始化
    importState.modality = 'Image' 
    importState.taskType = 'qa' // 多模态默认走 QA/Gen 逻辑，以便加载指标
  }
})

function resetState() {
  importState.meta = { name: '', category: '', description: '' }
  importState.file = null
  importState.fileHeaders = []
  importState.previewRows = []
  importState.columnMapping = {}
  importState.metrics = []
  importState.postProcess = ''
  // taskType 和 modality 由 watch uploadMode 单独处理
}

const handleNext = async () => {
  // 子组件校验
  if (stepRef.value && stepRef.value.validate) {
    const valid = await stepRef.value.validate()
    if (!valid) return
  }
  
  if (activeStep.value < steps.value.length - 1) {
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
    // 1. 生成配置 JSON
    const configs = generateConfigPayload(importState)
    
    // 2. 构建 FormData
    const formData = new FormData()
    formData.append('name', importState.meta.name)
    formData.append('category', importState.meta.category)
    formData.append('modality', importState.modality) // 🌟 传给后端
    formData.append('description', importState.meta.description || '')
    formData.append('file', importState.file)
    formData.append('configs_json', JSON.stringify(configs))
    
    // 3. 发送
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
    title="导入数据集" 
    width="800px" 
    :close-on-click-modal="false"
    destroy-on-close
    top="5vh"
  >
    <div class="mode-switch-container">
      <el-radio-group v-model="uploadMode">
        <el-radio-button label="text">文本数据集 (Text)</el-radio-button>
        <el-radio-button label="multimodal">多模态数据集 (Image/Video)</el-radio-button>
      </el-radio-group>
    </div>

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
          :upload-mode="uploadMode"
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
.mode-switch-container { display: flex; justify-content: center; margin-bottom: 20px; }
.step-header { margin-bottom: 25px; padding: 0 20px; }
.step-content { 
  min-height: 350px; 
  max-height: 550px; 
  overflow-y: auto; 
  padding: 0 20px;
}
.dialog-footer { display: flex; justify-content: flex-end; gap: 10px; }
</style>