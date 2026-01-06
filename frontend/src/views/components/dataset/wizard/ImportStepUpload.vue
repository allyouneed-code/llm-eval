<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Loading, Delete, VideoCamera } from '@element-plus/icons-vue'
import { getDatasetStats, previewDatasetFile } from '@/api/dataset'

const props = defineProps(['state', 'uploadMode'])
const formRef = ref(null)

// 本地状态
const isPreviewing = ref(false)
const categoryOptions = ref(['Knowledge', 'Reasoning', 'Coding', 'Math', 'Safety'])

// 表单校验规则
const rules = {
  name: [
    { required: true, message: '请输入数据集名称', trigger: 'blur' },
    { min: 3, max: 50, message: '长度在 3 到 50 个字符', trigger: 'blur' }
  ],
  category: [
    { required: true, message: '请选择或输入能力维度', trigger: 'change' }
  ]
}

// 🌟 核心逻辑 1：监听具体模态选择，强制覆盖 Category
watch(() => props.state.modality, (newVal) => {
  if (props.uploadMode === 'multimodal' && newVal && newVal !== 'Text') {
    // 强制将能力维度设为模态名称 (Image/Video/Audio)
    props.state.meta.category = newVal
  }
})

// 🌟 核心逻辑 2：监听大模式切换
watch(() => props.uploadMode, (val) => {
  if (val === 'multimodal') {
    // 切入多模态：立即触发一次填充
    if (props.state.modality && props.state.modality !== 'Text') {
      props.state.meta.category = props.state.modality
    }
  } else {
    // 切回文本模式：如果当前填的是模态名，则清空，让用户自己填
    if (['Image', 'Video', 'Audio'].includes(props.state.meta.category)) {
      props.state.meta.category = ''
    }
  }
})

// 初始化获取分类
onMounted(async () => {
  try {
    const stats = await getDatasetStats()
    const existCategories = stats.map(i => i.category).filter(c => c)
    categoryOptions.value = Array.from(new Set([...categoryOptions.value, ...existCategories]))
  } catch (e) { /* ignore */ }
})

// 处理文件选择
const handleFileChange = async (uploadFileObj) => {
  const rawFile = uploadFileObj.raw
  props.state.file = rawFile
  
  // 多模态模式：跳过解析
  if (props.uploadMode === 'multimodal') {
    props.state.fileHeaders = ['__skip__'] 
    ElMessage.success('资源包已就绪')
    return
  }
  
  // 文本模式：解析表头
  isPreviewing.value = true
  const formData = new FormData()
  
  let fileToPreview = rawFile
  if (rawFile.size > 50 * 1024) {
      fileToPreview = new File([rawFile.slice(0, 50 * 1024)], rawFile.name, { type: rawFile.type })
  }
  formData.append('file', fileToPreview)
  
  try {
    const data = await previewDatasetFile(formData)
    props.state.fileHeaders = data.columns || []
    props.state.previewRows = data.rows || []
    
    if (data.columns.length === 0) {
      ElMessage.warning('未能解析出表头，请检查文件格式')
    } else {
      ElMessage.success(`成功解析 ${data.columns.length} 个字段`)
    }
  } catch (e) {
    ElMessage.error('文件解析失败')
    props.state.fileHeaders = []
  } finally {
    isPreviewing.value = false
  }
}

const removeFile = () => {
  props.state.file = null
  props.state.fileHeaders = []
  props.state.previewRows = []
}

// 暴露给父组件的校验方法
const validate = async () => {
  if (!props.state.file) {
    ElMessage.warning('请上传数据文件')
    return false
  }
  if (props.uploadMode === 'text' && props.state.fileHeaders.length === 0) {
    ElMessage.warning('文件未成功解析，无法进入下一步')
    return false
  }
  return await formRef.value.validate()
}

defineExpose({ validate })
</script>

<template>
  <div class="step-upload">
    
    <el-alert
      v-if="uploadMode === 'multimodal'"
      title="多模态数据集要求"
      type="warning"
      show-icon
      :closable="false"
      class="mb-4"
      style="margin-bottom: 20px;"
    >
      <div style="font-size: 13px; line-height: 1.5;">
        <p>1. 请上传 <b>.zip</b> 压缩包，包含 <b>.jsonl</b> 索引文件及资源文件夹。</p>
        <p>2. 索引字段需包含标准字段：<code>question</code>, <code>answer</code>, <code>image</code> (或 video)。</p>
      </div>
    </el-alert>

    <el-form :model="state.meta" :rules="rules" ref="formRef" label-position="top">
      
      <div v-if="uploadMode === 'multimodal'" style="margin-bottom: 20px;">
         <el-form-item label="选择具体模态 (Modality)" required>
           <el-radio-group v-model="state.modality">
             <el-radio-button label="Image">
                <el-icon class="mr-1"><VideoCamera /></el-icon> 图像 (Image)
             </el-radio-button>
             <el-radio-button label="Video">
                <el-icon class="mr-1"><VideoCamera /></el-icon> 视频 (Video)
             </el-radio-button>
             <el-radio-button label="Audio">音频 (Audio)</el-radio-button>
           </el-radio-group>
         </el-form-item>
      </div>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="数据集名称 (Name)" prop="name">
            <el-input v-model="state.meta.name" placeholder="例如: My-VQA-Dataset" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="能力维度 (Category)" prop="category">
            <el-select 
              v-model="state.meta.category" 
              allow-create filterable 
              placeholder="选择或直接输入..." 
              style="width: 100%"
              :disabled="uploadMode === 'multimodal'"
            >
              <el-option v-for="item in categoryOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="描述信息 (Optional)">
        <el-input v-model="state.meta.description" type="textarea" :rows="2" placeholder="备注来源、用途等" />
      </el-form-item>

      <div class="upload-area">
        <el-form-item :label="uploadMode === 'text' ? '上传数据文件 (.jsonl / .csv)' : '上传资源包 (.zip)'" required>
          <el-upload
            v-if="!state.file"
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :show-file-list="false"
            :accept="uploadMode === 'text' ? '.json,.jsonl,.csv' : '.zip'"
            class="upload-box"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              {{ uploadMode === 'text' ? '拖拽 .jsonl / .csv 到此处' : '拖拽 .zip 资源包到此处' }}
            </div>
          </el-upload>

          <div v-else class="file-card">
            <div class="file-info">
              <el-icon :size="24" class="file-icon"><Document /></el-icon>
              <div>
                <div class="file-name">{{ state.file.name }}</div>
                <div class="file-meta">{{ (state.file.size / 1024).toFixed(1) }} KB</div>
              </div>
            </div>
            <el-button type="danger" link @click="removeFile"><el-icon><Delete /></el-icon></el-button>
          </div>
        </el-form-item>
      </div>
      
      <div v-if="isPreviewing" class="status-box"><el-icon class="is-loading"><Loading /></el-icon> 正在解析文件结构...</div>
      <div v-if="uploadMode === 'text' && state.fileHeaders.length > 0" class="preview-table">
        <div class="preview-header">
           <span>✅ 解析成功 (识别到 {{ state.fileHeaders.length }} 列)</span>
        </div>
        <el-table :data="state.previewRows" border size="small" style="width: 100%">
           <el-table-column v-for="col in state.fileHeaders" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.upload-area { margin-top: 10px; }
.upload-box { width: 100%; }
:deep(.el-upload-dragger) { padding: 20px; }

.file-card { 
  display: flex; justify-content: space-between; align-items: center; 
  padding: 15px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fcfcfc; 
}
.file-info { display: flex; align-items: center; gap: 12px; }
.file-icon { color: #409eff; }
.file-name { font-weight: 500; font-size: 14px; }
.file-meta { font-size: 12px; color: #909399; }

.status-box { padding: 10px; text-align: center; color: #909399; font-size: 13px; }

.preview-table { margin-top: 15px; border: 1px solid #ebeef5; border-radius: 4px; overflow: hidden; }
.preview-header { 
  background: #f0f9eb; color: #67c23a; font-size: 12px; font-weight: bold; 
  padding: 8px 12px; border-bottom: 1px solid #ebeef5; 
}
.mr-1 { margin-right: 4px; }
</style>