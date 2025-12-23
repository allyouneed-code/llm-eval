<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Loading, Delete, Operation, Cpu, Plus } from '@element-plus/icons-vue'
import { createDataset, previewDatasetFile, getDatasetStats } from '@/api/dataset'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

// ==========================================
// 1. 常量定义
// ==========================================
const defaultConfig = {
  mode: 'gen',  
  evaluator_type: 'Rule', 
  metric_name: 'Accuracy',
  post_process_type: '' 
}

// ==========================================
// 2. 状态定义
// ==========================================
const submitting = ref(false)
const isPreviewing = ref(false)
const uploadFile = ref(null)
const previewData = ref({ columns: [], rows: [] })

const categoryOptions = ref(['Knowledge', 'Reasoning', 'Coding', 'Math', 'Safety'])

const metaForm = reactive({
  name: '',
  category: '', 
  description: ''
})

const configList = ref([ JSON.parse(JSON.stringify(defaultConfig)) ])

// ==========================================
// 3. 核心逻辑方法
// ==========================================

watch(() => props.visible, (val) => {
  if (val) {
    resetForm()
    fetchCategories()
  }
})

const fetchCategories = async () => {
  try {
    const stats = await getDatasetStats()
    const existCategories = stats
      .map(item => item.category)
      .filter(c => c && c.trim() !== '')
      
    const merged = new Set([...categoryOptions.value, ...existCategories])
    categoryOptions.value = Array.from(merged)
  } catch (e) {
    console.error(e)
  }
}

const resetForm = () => {
  metaForm.name = ''
  metaForm.category = ''
  metaForm.description = ''
  configList.value = [ JSON.parse(JSON.stringify(defaultConfig)) ]
  removeFile()
}

const removeFile = () => {
  uploadFile.value = null
  previewData.value = { columns: [], rows: [] }
}

const addConfig = () => {
  configList.value.push(JSON.parse(JSON.stringify(defaultConfig)))
}

const removeConfig = (index) => {
  if (configList.value.length <= 1) return ElMessage.warning('至少保留一个评测配置')
  configList.value.splice(index, 1)
}

// ------------------------------------------
// 🌟 选项联动逻辑
// ------------------------------------------

// 判断是否显示答案提取 (仅 Gen + Rule + Accuracy 时显示)
const isPostProcessAvailable = (item) => {
  return item.mode === 'gen' && 
         item.evaluator_type === 'Rule' && 
         item.metric_name === 'Accuracy'
}

// 模式变化 (Gen/PPL)
const handleModeChange = (item) => {
  if (item.mode === 'ppl') {
    item.evaluator_type = 'Rule'
    item.metric_name = 'Accuracy'
    item.post_process_type = '' 
  } else {
    item.evaluator_type = 'Rule'
    item.metric_name = 'Accuracy'
  }
}

// 评测方式变化 (Rule/LLM)
const handleEvaluatorChange = (item) => {
  if (item.evaluator_type === 'LLM') {
    item.metric_name = 'Score'
    item.post_process_type = ''
  } else {
    item.metric_name = 'Accuracy'
    if (item.mode === 'gen') item.post_process_type = ''
  }
}

// 指标变化
const handleMetricChange = (item) => {
  if (item.metric_name !== 'Accuracy') {
    item.post_process_type = ''
  }
}

// ------------------------------------------
// 文件处理与提交
// ------------------------------------------

const handleFileChange = async (uploadFileObj) => {
  const rawFile = uploadFileObj.raw
  uploadFile.value = rawFile 
  
  isPreviewing.value = true
  const formData = new FormData()
  
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
    previewData.value = { columns: [], rows: [] }
  } finally {
    isPreviewing.value = false
  }
}

const handleSubmit = async () => {
  if (!metaForm.name || !metaForm.category || !uploadFile.value) {
    return ElMessage.warning('请填写完整信息并上传文件')
  }

  submitting.value = true
  const formData = new FormData()
  
  formData.append('name', metaForm.name)
  formData.append('category', metaForm.category) 
  formData.append('description', metaForm.description || '')
  formData.append('file', uploadFile.value)

  const configsPayload = configList.value.map((item, index) => {
    let evaluatorType = 'AccEvaluator'
    if (item.evaluator_type === 'LLM') {
      evaluatorType = 'LLMEvaluator'
    } else {
      if (item.metric_name === 'BLEU') evaluatorType = 'BleuEvaluator'
      else if (item.metric_name === 'ROUGE') evaluatorType = 'RougeEvaluator'
      else if (item.metric_name === 'Pass@1') evaluatorType = 'HumanevalEvaluator'
      else evaluatorType = 'AccEvaluator'
    }

    let postProcessCfg = {}
    if (item.post_process_type === 'first_capital') {
      postProcessCfg = { type: 'opencompass.utils.text_postprocessors.first_capital_postprocess' }
    } else if (item.post_process_type === 'math') {
      postProcessCfg = { type: 'opencompass.utils.text_postprocessors.math_postprocess' }
    } else if (item.post_process_type === 'general_cn') {
      postProcessCfg = { type: 'opencompass.utils.text_postprocessors.general_cn_postprocess' }
    }

    return {
      config_name: `${metaForm.name}_${item.mode}_v${index + 1}`,
      mode: item.mode,
      display_metric: item.metric_name,
      metric_config: JSON.stringify({ evaluator: { type: evaluatorType } }),
      post_process_cfg: JSON.stringify(postProcessCfg),
      few_shot_cfg: JSON.stringify({})
    }
  })
  
  formData.append('configs_json', JSON.stringify(configsPayload))

  try {
    await createDataset(formData)
    ElMessage.success('导入成功')
    emit('update:visible', false)
    emit('success') 
  } catch (error) {
    // console.error(error)
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
    width="700px" 
    destroy-on-close
    top="5vh"
  >
     <el-form :model="metaForm" label-position="top">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="数据集名称" required>
            <el-input v-model="metaForm.name" placeholder="例如: My-QA-Dataset" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="能力维度" required>
            <el-select v-model="metaForm.category" allow-create filterable placeholder="选择或输入..." style="width: 100%">
              <el-option v-for="item in categoryOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="描述">
        <el-input v-model="metaForm.description" type="textarea" :rows="2" placeholder="备注信息" />
      </el-form-item>

      <el-form-item label="上传数据文件" required>
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
          <el-button type="danger" link @click="removeFile"><el-icon><Delete /></el-icon> 重选</el-button>
        </div>
      </el-form-item>

      <div v-if="isPreviewing" class="loading-box"><el-icon class="is-loading"><Loading /></el-icon> 解析中...</div>
      
      <div v-if="previewData.columns.length > 0" class="preview-box">
        <div class="preview-title">Preview (Top 5 Rows):</div>
        <el-table :data="previewData.rows" border size="small" height="150" style="width: 100%">
          <el-table-column v-for="col in previewData.columns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>

      <div class="configs-container">
        <div class="section-header">
           <span>评测配置 ({{ configList.length }})</span>
           <el-button type="primary" link size="small" @click="addConfig">
             <el-icon><Plus /></el-icon> 添加配置
           </el-button>
        </div>

        <div v-for="(item, index) in configList" :key="index" class="config-card">
           <div class="card-header">
              <span class="config-idx">配置 #{{ index + 1 }}</span>
              <el-button v-if="configList.length > 1" type="danger" link size="small" @click="removeConfig(index)">
                <el-icon><Delete /></el-icon>
              </el-button>
           </div>
           
           <el-row :gutter="15">
             <el-col :span="8">
                <el-form-item label="模式 (Mode)" style="margin-bottom: 0">
                  <el-radio-group v-model="item.mode" size="small" @change="handleModeChange(item)">
                    <el-radio-button label="gen">Gen</el-radio-button>
                    <el-radio-button label="ppl">PPL</el-radio-button>
                  </el-radio-group>
                </el-form-item>
             </el-col>
             <el-col :span="16">
                <el-form-item label="评测方式 (Evaluator)" style="margin-bottom: 0">
                   <el-radio-group 
                     v-model="item.evaluator_type" 
                     size="small"
                     @change="handleEvaluatorChange(item)"
                     :disabled="item.mode === 'ppl'"
                   >
                      <el-radio-button label="Rule"><el-icon><Operation /></el-icon> 规则</el-radio-button>
                      <el-radio-button label="LLM"><el-icon><Cpu /></el-icon> LLM Judge</el-radio-button>
                   </el-radio-group>
                </el-form-item>
             </el-col>
           </el-row>

           <el-row :gutter="15" style="margin-top: 15px;">
             <el-col :span="12">
                <el-form-item label="主要指标 (Metric)" style="margin-bottom: 0">
                   <el-select 
                     v-model="item.metric_name" 
                     size="small" 
                     style="width: 100%"
                     @change="handleMetricChange(item)"
                   >
                      <template v-if="item.evaluator_type === 'Rule'">
                         <el-option label="Accuracy (准确率)" value="Accuracy"/>
                         <template v-if="item.mode === 'gen'">
                           <el-option label="BLEU (翻译质量)" value="BLEU"/>
                           <el-option label="ROUGE (摘要质量)" value="ROUGE"/>
                           <el-option label="Pass@1 (代码通过率)" value="Pass@1"/>
                         </template>
                      </template>
                      <template v-else>
                         <el-option label="Score (模型打分)" value="Score"/>
                         <el-option label="Pass (判断通过)" value="Pass"/>
                      </template>
                   </el-select>
                </el-form-item>
             </el-col>
             
             <el-col :span="12" v-if="isPostProcessAvailable(item)">
                <el-form-item label="答案提取 (Post-process)" style="margin-bottom: 0">
                   <el-select 
                     v-model="item.post_process_type" 
                     size="small" 
                     clearable 
                     placeholder="无 (严格匹配)"
                   >
                      <el-option label="首字母 (A/B/C/D)" value="first_capital" />
                      <el-option label="数学 (提取数字)" value="math" />
                      <el-option label="中文问答 (通用)" value="general_cn" />
                   </el-select>
                </el-form-item>
             </el-col>
           </el-row>
        </div>
      </div>

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
.configs-container {
  margin-top: 20px;
  background-color: #f5f7fa;
  padding: 10px 15px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  max-height: 350px;
  overflow-y: auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: bold;
  color: #606266;
}

.config-card {
  background-color: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 10px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.config-card:last-child { margin-bottom: 0; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 5px;
  border-bottom: 1px dashed #ebeef5;
}
.config-idx { font-size: 12px; font-weight: bold; color: #909399; }

.file-card { display: flex; justify-content: space-between; align-items: center; padding: 15px; border: 1px dashed #dcdfe6; border-radius: 6px; background-color: #f9fafc; }
.file-info { display: flex; align-items: center; }
.file-name { font-weight: 500; color: #303133; }

.preview-box { border: 1px solid #dcdfe6; border-radius: 4px; padding: 10px; background-color: #f9fafc; margin-top: 10px; }
.preview-title { font-size: 12px; color: #909399; margin-bottom: 5px; }
.loading-box { text-align: center; margin: 10px 0; font-size: 12px; color: #909399; }

.upload-demo { width: 100%; }
:deep(.el-upload) { width: 100%; display: block; }
:deep(.el-upload-dragger) { width: 100% !important; height: 140px; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 0; }
:deep(.el-upload-dragger .el-icon--upload) { font-size: 40px; margin-bottom: 10px; color: #C0C4CC; }
:deep(.el-form-item__label) { padding-bottom: 4px !important; font-size: 13px; font-weight: 500; }
</style>