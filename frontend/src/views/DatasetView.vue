<script setup>
import { ref, onMounted, reactive, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Document, Loading, Delete, View, Download } from '@element-plus/icons-vue'

// === 1. 数据定义 ===
const allDatasets = ref([]) 
const activeCapability = ref('All')

// 导入弹窗控制
const dialogVisible = ref(false)
const isPreviewing = ref(false)
const submitting = ref(false)
const uploadFile = ref(null)
const previewData = ref({ columns: [], rows: [] }) // 导入时的预览数据

// 查看已保存数据弹窗控制
const savedDataVisible = ref(false)
const savedPreviewData = ref({ columns: [], rows: [] })
const savedDataLoading = ref(false)

const judgeModels = ref([])

const capabilities = computed(() => {
  const caps = new Set(allDatasets.value.map(d => d.capability))
  return ['All', ...Array.from(caps)]
})

const filteredDatasets = computed(() => {
  if (activeCapability.value === 'All') return allDatasets.value
  return allDatasets.value.filter(d => d.capability === activeCapability.value)
})

const form = reactive({
  name: '',
  capability: '',
  description: '',
  evaluator_type: 'Rule', 
  metric_name: 'Accuracy',
  judge_model_id: null 
})

const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 2. 逻辑处理 ===

watch(() => form.evaluator_type, (newType) => {
  if (newType === 'Rule') {
    form.metric_name = 'Accuracy'
    form.judge_model_id = null
  } else {
    form.metric_name = 'Score'
    if (judgeModels.value.length === 0) {
      fetchModels()
    }
  }
})

const fetchDatasets = async () => {
  try {
    const res = await axios.get(`${API_BASE}/datasets/`)
    allDatasets.value = res.data
    if (activeCapability.value !== 'All' && !capabilities.value.includes(activeCapability.value)) {
      activeCapability.value = 'All'
    }
  } catch (error) {
    ElMessage.error('获取数据集列表失败')
  }
}

const fetchModels = async () => {
  try {
    const res = await axios.get(`${API_BASE}/models/`)
    judgeModels.value = res.data
  } catch (error) {
    console.error('Failed to fetch models')
  }
}

// --- 文件上传逻辑 ---
const handleFileChange = async (uploadFileObj) => {
  const rawFile = uploadFileObj.raw
  uploadFile.value = rawFile 
  
  let fileToPreview = rawFile
  const fileName = rawFile.name.toLowerCase()
  
  // 预览切片优化
  if (fileName.endsWith('.csv') || fileName.endsWith('.jsonl') || fileName.endsWith('.txt')) {
    const chunk = rawFile.slice(0, 50 * 1024) 
    fileToPreview = new File([chunk], rawFile.name, { type: rawFile.type })
  }

  const formData = new FormData()
  formData.append('file', fileToPreview)
  
  isPreviewing.value = true
  try {
    const res = await axios.post(`${API_BASE}/datasets/preview`, formData)
    previewData.value = res.data
    ElMessage.success('文件解析成功')
  } catch (e) {
    ElMessage.error('预览失败，请检查文件格式')
    previewData.value = { columns: [], rows: [] }
  } finally {
    isPreviewing.value = false
  }
}

const removeFile = () => {
  uploadFile.value = null
  previewData.value = { columns: [], rows: [] }
}

const handleSubmit = async () => {
  if (!form.name || !form.capability || !uploadFile.value) {
    return ElMessage.warning('请填写完整信息并上传文件')
  }
  if (form.evaluator_type === 'LLM' && !form.judge_model_id) {
    return ElMessage.warning('请选择裁判模型')
  }

  submitting.value = true
  
  let configObj = {}
  if (form.evaluator_type === 'Rule') {
    configObj = { type: 'RuleEvaluator', metric: form.metric_name }
  } else {
    const judgeModel = judgeModels.value.find(m => m.id === form.judge_model_id)
    configObj = { 
      type: 'LLMEvaluator', 
      metric: 'Score',
      judge_model_id: form.judge_model_id,
      judge_model_name: judgeModel ? judgeModel.name : 'Unknown'
    }
  }

  const formData = new FormData()
  formData.append('name', form.name)
  formData.append('capability', form.capability)
  formData.append('metric_name', form.metric_name)
  formData.append('evaluator_config', JSON.stringify(configObj))
  formData.append('description', form.description || '')
  formData.append('file', uploadFile.value)

  try {
    await axios.post(`${API_BASE}/datasets/`, formData)
    ElMessage.success('导入成功')
    dialogVisible.value = false
    fetchDatasets()
    
    // Reset
    form.name = ''
    form.capability = ''
    form.description = ''
    form.evaluator_type = 'Rule'
    form.metric_name = 'Accuracy'
    form.judge_model_id = null
    removeFile()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    submitting.value = false
  }
}

// --- 下载与预览已保存数据 ---

const handleDownload = (row) => {
  window.open(`${API_BASE}/datasets/${row.id}/download`, '_blank')
}

const handleViewData = async (row) => {
  savedDataVisible.value = true
  savedDataLoading.value = true
  savedPreviewData.value = { columns: [], rows: [] }
  
  try {
    const res = await axios.get(`${API_BASE}/datasets/${row.id}/preview`)
    savedPreviewData.value = res.data
  } catch (error) {
    ElMessage.error('无法读取数据预览')
  } finally {
    savedDataLoading.value = false
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除 "${row.name}" 吗?`, '警告', { type: 'warning' })
    .then(async () => {
      await axios.delete(`${API_BASE}/datasets/${row.id}`)
      ElMessage.success('删除成功')
      fetchDatasets()
    })
}

onMounted(() => {
  fetchDatasets()
  fetchModels()
})
</script>

<template>
  <div class="dataset-view">
    <el-container style="height: calc(100vh - 80px);">
      
      <el-aside width="240px" style="background: #fff; border-right: 1px solid #eee;">
        <div class="cap-header">能力维度</div>
        <el-menu 
          :default-active="activeCapability" 
          @select="(index) => activeCapability = index"
          style="border-right: none;"
        >
          <el-menu-item v-for="cap in capabilities" :key="cap" :index="cap">
            <el-icon><Document /></el-icon>
            <span>{{ cap }}</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      
      <el-main>
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
          <h2 style="margin: 0; font-size: 18px;">{{ activeCapability === 'All' ? '所有数据集' : activeCapability }}</h2>
          <el-button type="primary" @click="dialogVisible = true">
            <el-icon style="margin-right: 5px"><UploadFilled /></el-icon> 导入数据集
          </el-button>
        </div>

        <el-table :data="filteredDatasets" border style="width: 100%">
          <el-table-column prop="name" label="名称" width="180" show-overflow-tooltip />
          <el-table-column prop="capability" label="能力归属" width="100" align="center">
            <template #default="scope">
              <el-tag effect="light">{{ scope.row.capability }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="metric_name" label="指标" width="100" align="center">
            <template #default="scope">
              <el-tag type="info" v-if="scope.row.metric_name">{{ scope.row.metric_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="评测方式" width="110" align="center">
            <template #default="scope">
              <el-tag v-if="scope.row.evaluator_config.includes('LLMEvaluator')" type="warning">LLM Judge</el-tag>
              <el-tag v-else type="success">Rule Match</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
          
          <el-table-column label="数据文件" width="140" align="center">
            <template #default="scope">
              <el-button-group>
                <el-button size="small" :icon="View" @click="handleViewData(scope.row)">预览</el-button>
                <el-button size="small" :icon="Download" @click="handleDownload(scope.row)"></el-button>
              </el-button-group>
            </template>
          </el-table-column>
          
          <el-table-column label="操作" width="80" align="center">
            <template #default="scope">
              <el-button link type="danger" size="small" :icon="Delete" @click="handleDelete(scope.row)"></el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-main>
    </el-container>

    <el-dialog v-model="dialogVisible" title="导入数据集" width="700px" destroy-on-close>
      <el-form :model="form" label-position="top">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="数据集名称">
              <el-input v-model="form.name" placeholder="例如: GSM8K-Test" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属能力">
              <el-select 
                v-model="form.capability" 
                allow-create 
                filterable 
                default-first-option
                placeholder="选择或输入新能力"
                style="width: 100%"
              >
                <el-option label="Knowledge (知识)" value="Knowledge" />
                <el-option label="Reasoning (推理)" value="Reasoning" />
                <el-option label="Coding (编程)" value="Coding" />
                <el-option label="Understanding (理解)" value="Understanding" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <div class="config-section">
          <div class="section-title">评测配置</div>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="评测方式">
                <el-select v-model="form.evaluator_type" style="width: 100%">
                  <el-option label="规则匹配" value="Rule" />
                  <el-option label="模型打分" value="LLM" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="主要指标">
                <el-select v-model="form.metric_name" style="width: 100%" :disabled="form.evaluator_type === 'LLM'">
                  <el-option v-if="form.evaluator_type === 'Rule'" label="Accuracy (准确率)" value="Accuracy" />
                  <el-option v-if="form.evaluator_type === 'Rule'" label="Pass@1 (通过率)" value="Pass@1" />
                  <el-option v-if="form.evaluator_type === 'Rule'" label="F1 Score" value="F1" />
                  <el-option v-if="form.evaluator_type === 'LLM'" label="Score (0-10分)" value="Score" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8" v-if="form.evaluator_type === 'LLM'">
              <el-form-item label="裁判模型" required>
                <el-select v-model="form.judge_model_id" placeholder="请选择裁判模型" style="width: 100%">
                  <el-option 
                    v-for="model in judgeModels" 
                    :key="model.id" 
                    :label="model.name" 
                    :value="model.id" 
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <el-form-item label="数据文件" style="margin-top: 20px;">
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
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">支持 .csv, .json, .jsonl, .xlsx 文件</div>
            </template>
          </el-upload>

          <div v-else class="file-card">
            <div class="file-info">
              <el-icon :size="20" style="color: #409EFF; margin-right: 10px;"><Document /></el-icon>
              <span class="file-name">{{ uploadFile.name }}</span>
              <el-tag size="small" type="info" style="margin-left: 10px;">{{ (uploadFile.size / 1024).toFixed(1) }} KB</el-tag>
            </div>
            <el-button type="danger" link @click="removeFile">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </div>
        </el-form-item>

        <div v-if="isPreviewing" style="text-align: center; margin: 20px 0;">
          <el-icon class="is-loading"><Loading /></el-icon> 正在解析文件...
        </div>

        <div v-if="previewData.columns.length > 0" class="preview-box">
          <div style="font-size: 12px; color: #909399; margin-bottom: 5px;">数据预览 (Top 5):</div>
          <el-table :data="previewData.rows" border size="small" height="150" style="width: 100%">
            <el-table-column 
              v-for="col in previewData.columns" 
              :key="col" 
              :prop="col" 
              :label="col" 
              min-width="120"
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <el-form-item label="描述" style="margin-top: 15px;">
          <el-input v-model="form.description" type="textarea" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            确认导入
          </el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-model="savedDataVisible" title="数据预览" width="700px">
      <div v-if="savedDataLoading" style="text-align: center; padding: 20px;">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <div style="margin-top: 10px;">正在从服务器读取数据...</div>
      </div>
      
      <div v-else>
        <el-table :data="savedPreviewData.rows" border stripe height="300" style="width: 100%">
          <el-table-column 
            v-for="col in savedPreviewData.columns" 
            :key="col" 
            :prop="col" 
            :label="col" 
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.dataset-view {
  background: #fff;
  height: 100%; 
}
.cap-header {
  padding: 15px 20px;
  font-weight: bold;
  color: #303133;
  border-bottom: 1px solid #eee;
  background: #f5f7fa;
}
.config-section {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 10px;
}
.section-title {
  font-size: 14px;
  font-weight: bold;
  color: #606266;
  margin-bottom: 10px;
}
.file-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  border: 1px dashed #dcdfe6; 
  border-radius: 6px;
  background-color: #f9fafc;
}
.file-info {
  display: flex;
  align-items: center;
}
.file-name {
  font-weight: 500;
  color: #303133;
}
.preview-box {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 10px;
  background-color: #f9fafc;
  margin-top: 10px;
}

/* --- 核心修复：强制上传拖拽区域内容居中 --- */
/* 1. 让组件占满父容器 */
.upload-demo {
  width: 100%;
}
/* 2. 强制 el-upload 变为块级元素，否则宽度不生效 */
:deep(.el-upload) {
  width: 100%;
  display: block;
}
/* 3. 设置 dragger 为 flex 容器，实现绝对居中 */
:deep(.el-upload-dragger) {
  width: 100% !important;
  height: 180px;
  display: flex;
  flex-direction: column;
  justify-content: center; /* 垂直居中 */
  align-items: center;     /* 水平居中 */
  padding: 0;              /* 清除内边距影响 */
}

/* 4. 调整图标大小和间距 */
:deep(.el-upload-dragger .el-icon--upload) {
  font-size: 48px;
  margin-bottom: 10px;
  color: #C0C4CC;
}
</style>