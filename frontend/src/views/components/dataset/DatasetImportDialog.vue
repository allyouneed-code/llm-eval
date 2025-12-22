<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Loading, Delete, Operation, Cpu } from '@element-plus/icons-vue'
import { createDataset, previewDatasetFile } from '@/api/dataset'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

// 表单状态
const submitting = ref(false)
const isPreviewing = ref(false)
const uploadFile = ref(null)
const previewData = ref({ columns: [], rows: [] })

const form = reactive({
  name: '',
  category: '', 
  description: '',
  mode: 'gen',  
  evaluator_type: 'Rule', 
  metric_name: 'Accuracy'
})

// 监听打开时重置
watch(() => props.visible, (val) => {
  if (val) resetForm()
})

const resetForm = () => {
  form.name = ''
  form.category = ''
  form.description = ''
  form.mode = 'gen'
  form.evaluator_type = 'Rule'
  form.metric_name = 'Accuracy'
  removeFile()
}

const removeFile = () => {
  uploadFile.value = null
  previewData.value = { columns: [], rows: [] }
}

const handleFileChange = async (uploadFileObj) => {
  const rawFile = uploadFileObj.raw
  uploadFile.value = rawFile 
  
  isPreviewing.value = true
  const formData = new FormData()
  
  // 预览前 50KB
  let fileToPreview = rawFile
  if (rawFile.size > 50 * 1024) {
      fileToPreview = new File([rawFile.slice(0, 50 * 1024)], rawFile.name, { type: rawFile.type })
  }
  formData.append('file', fileToPreview)
  
  try {
    const data = await previewDatasetFile(formData)
    previewData.value = data
    ElMessage.success('文件解析成功')
  } catch (e) {
    ElMessage.warning('预览失败，但不影响导入')
    previewData.value = { columns: [], rows: [] }
  } finally {
    isPreviewing.value = false
  }
}

const handleSubmit = async () => {
  if (!form.name || !form.category || !uploadFile.value) {
    return ElMessage.warning('请填写完整信息并上传文件')
  }

  submitting.value = true
  const formData = new FormData()
  
  formData.append('name', form.name)
  formData.append('category', form.category) 
  formData.append('description', form.description || '')
  formData.append('mode', form.mode)
  formData.append('metric_name', form.metric_name)
  
  let evaluatorType = 'AccEvaluator'
  if (form.evaluator_type === 'LLM') {
    evaluatorType = 'LLMEvaluator'
  } else {
    if (form.metric_name === 'BLEU') evaluatorType = 'BleuEvaluator'
    else if (form.metric_name === 'ROUGE') evaluatorType = 'RougeEvaluator'
    else evaluatorType = 'AccEvaluator'
  }
  
  formData.append('evaluator_config', JSON.stringify({ type: evaluatorType })) 
  formData.append('file', uploadFile.value)

  try {
    await createDataset(formData)
    ElMessage.success('导入成功')
    emit('update:visible', false)
    emit('success') // 通知父组件刷新
  } catch (error) {
    // 拦截器处理错误
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog 
    :model-value="visible" 
    @update:model-value="(val) => emit('update:visible', val)"
    title="导入数据集" 
    width="650px" 
    destroy-on-close
  >
     <el-form :model="form" label-position="top">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="数据集名称" required>
            <el-input v-model="form.name" placeholder="例如: My-QA-Dataset" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="能力维度" required>
            <el-select v-model="form.category" allow-create filterable placeholder="选择或输入..." style="width: 100%">
              <el-option label="Knowledge" value="Knowledge" />
              <el-option label="Reasoning" value="Reasoning" />
              <el-option label="Coding" value="Coding" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <div class="config-section">
        <div class="section-title">默认评测配置</div>
        <el-row :gutter="20">
           <el-col :span="12">
              <el-form-item label="数据集模式 (Data Mode)">
                <el-radio-group v-model="form.mode">
                  <el-radio-button label="gen">Gen (生成)</el-radio-button>
                  <el-radio-button label="ppl">PPL (判别)</el-radio-button>
                </el-radio-group>
              </el-form-item>
           </el-col>
           <el-col :span="12">
              <el-form-item label="评测方式 (Evaluator)">
                 <el-radio-group v-model="form.evaluator_type">
                    <el-radio-button label="Rule">
                      <el-icon><Operation /></el-icon> 规则
                    </el-radio-button>
                    <el-radio-button label="LLM">
                      <el-icon><Cpu /></el-icon> LLM
                    </el-radio-button>
                 </el-radio-group>
              </el-form-item>
           </el-col>
        </el-row>
        <el-row>
           <el-col :span="24">
              <el-form-item label="主要指标 (Metric)">
                 <el-select v-model="form.metric_name" style="width: 100%">
                    <template v-if="form.evaluator_type === 'Rule'">
                       <el-option label="Accuracy (准确率)" value="Accuracy"/>
                       <el-option label="BLEU (翻译质量)" value="BLEU"/>
                       <el-option label="ROUGE (摘要质量)" value="ROUGE"/>
                       <el-option label="Pass@1 (代码通过率)" value="Pass@1"/>
                    </template>
                    <template v-else>
                       <el-option label="Score (模型打分)" value="Score"/>
                       <el-option label="Pass (判断通过)" value="Pass"/>
                    </template>
                 </el-select>
              </el-form-item>
           </el-col>
        </el-row>
      </div>
      <el-form-item label="上传数据文件" style="margin-top: 15px;">
        <el-upload
          v-if="!uploadFile"
          class="upload-demo"
          drag
          action="#"
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :show-file-list="false"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
          <template #tip><div class="el-upload__tip">支持 .csv, .jsonl 格式</div></template>
        </el-upload>
        <div v-else class="file-card">
          <div class="file-info">
            <el-icon :size="20" style="color: #409EFF; margin-right: 10px;"><Document /></el-icon>
            <span class="file-name">{{ uploadFile.name }}</span>
            <el-tag size="small" type="info" style="margin-left: 10px;">{{ (uploadFile.size / 1024).toFixed(1) }} KB</el-tag>
          </div>
          <el-button type="danger" link @click="removeFile"><el-icon><Delete /></el-icon> 删除</el-button>
        </div>
      </el-form-item>
      <div v-if="isPreviewing" style="text-align: center; margin: 10px 0;"><el-icon class="is-loading"><Loading /></el-icon> 解析中...</div>
      <div v-if="previewData.columns.length > 0" class="preview-box">
        <div style="font-size: 12px; color: #909399; margin-bottom: 5px;">Preview (Top 5 Rows):</div>
        <el-table :data="previewData.rows" border size="small" height="150" style="width: 100%">
          <el-table-column v-for="col in previewData.columns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>

      <el-form-item label="描述" style="margin-top: 15px;">
        <el-input v-model="form.description" type="textarea" placeholder="备注信息" />
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确认导入</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
.config-section { background-color: #f5f7fa; padding: 15px; border-radius: 4px; margin-bottom: 10px; }
.section-title { font-size: 13px; font-weight: bold; color: #606266; margin-bottom: 10px; }
.file-card { display: flex; justify-content: space-between; align-items: center; padding: 15px; border: 1px dashed #dcdfe6; border-radius: 6px; background-color: #f9fafc; }
.file-info { display: flex; align-items: center; }
.file-name { font-weight: 500; color: #303133; }
.preview-box { border: 1px solid #dcdfe6; border-radius: 4px; padding: 10px; background-color: #f9fafc; margin-top: 10px; }
.upload-demo { width: 100%; }
:deep(.el-upload) { width: 100%; display: block; }
:deep(.el-upload-dragger) { width: 100% !important; height: 160px; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 0; }
:deep(.el-upload-dragger .el-icon--upload) { font-size: 48px; margin-bottom: 10px; color: #C0C4CC; }
</style>