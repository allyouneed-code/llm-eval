<script setup>
import { ref, onMounted, reactive, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  UploadFilled, Document, Loading, Delete, View, Download, 
  Search, Medal, User, Odometer, Filter, DataLine,
  Cpu, Operation // 新增图标
} from '@element-plus/icons-vue'

// === 1. 数据定义 ===
const allDatasets = ref([]) 
const activeCapability = ref('All')

// 分页与搜索
const currentPage = ref(1)
const pageSize = ref(10)
const searchKeyword = ref('')
const showPrivateOnly = ref(false)

// 导入弹窗
const dialogVisible = ref(false)
const submitting = ref(false)
const isPreviewing = ref(false)
const uploadFile = ref(null)
const previewData = ref({ columns: [], rows: [] })

// 预览已保存数据
const savedDataVisible = ref(false)
const savedPreviewData = ref({ columns: [], rows: [] })
const savedDataLoading = ref(false)

const form = reactive({
  name: '',
  category: '', 
  description: '',
  mode: 'gen',  
  // 🌟 找回：评测方式字段
  evaluator_type: 'Rule', // 'Rule' or 'LLM'
  metric_name: 'Accuracy'
})

const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 2. 核心计算属性 ===
const capabilities = computed(() => {
  const caps = new Set(allDatasets.value.map(d => d.category || 'Uncategorized'))
  return ['All', ...Array.from(caps)]
})

const filteredDatasets = computed(() => {
  let result = allDatasets.value
  if (activeCapability.value !== 'All') {
    result = result.filter(d => d.category === activeCapability.value)
  }
  if (showPrivateOnly.value) {
    result = result.filter(d => !d.is_system)
  }
  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(d => 
      d.name.toLowerCase().includes(keyword) || 
      (d.description && d.description.toLowerCase().includes(keyword))
    )
  }
  return result
})

const paginatedDatasets = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredDatasets.value.slice(start, end)
})

watch([activeCapability, searchKeyword, showPrivateOnly], () => {
  currentPage.value = 1
})

// 🌟 联动逻辑：当评测方式改变时，自动切换默认指标
watch(() => form.evaluator_type, (newVal) => {
  if (newVal === 'Rule') {
    form.metric_name = 'Accuracy'
  } else {
    form.metric_name = 'Score' // LLM 评测通常是打分
  }
})

// === 3. 交互逻辑 ===

const fetchDatasets = async () => {
  try {
    const res = await axios.get(`${API_BASE}/datasets/`)
    // 模拟 system 标记
    allDatasets.value = res.data.map(d => ({
      ...d,
      is_system: d.name.includes('GSM8K') || d.name.includes('MMLU') || d.name.includes('C-Eval')
    }))
  } catch (error) {
    ElMessage.error('获取数据集列表失败')
  }
}

const resetForm = () => {
  form.name = ''
  form.category = ''
  form.description = ''
  form.mode = 'gen'
  form.evaluator_type = 'Rule' // 重置
  form.metric_name = 'Accuracy'
  removeFile()
}

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
    const res = await axios.post(`${API_BASE}/datasets/preview`, formData)
    previewData.value = res.data
    ElMessage.success('文件解析成功')
  } catch (e) {
    ElMessage.warning('预览失败，但不影响导入')
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
  
  // 🌟 构造 Evaluator Config JSON
  // 如果是 Rule，对应 AccEvaluator/BleuEvaluator 等
  // 如果是 LLM，对应 LLMEvaluator
  let evaluatorType = 'AccEvaluator'
  if (form.evaluator_type === 'LLM') {
    evaluatorType = 'LLMEvaluator'
  } else {
    // Rule mapping
    if (form.metric_name === 'BLEU') evaluatorType = 'BleuEvaluator'
    else if (form.metric_name === 'ROUGE') evaluatorType = 'RougeEvaluator'
    else evaluatorType = 'AccEvaluator'
  }
  
  const configObj = { type: evaluatorType }
  // 可以在这里扩展 LLM Judge 的配置，例如 { type: 'LLMEvaluator', judge_model: 'gpt-4' }
  
  formData.append('evaluator_config', JSON.stringify(configObj)) 
  formData.append('file', uploadFile.value)

  try {
    await axios.post(`${API_BASE}/datasets/`, formData)
    ElMessage.success('导入成功')
    dialogVisible.value = false
    fetchDatasets()
    resetForm()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    submitting.value = false
  }
}

// 预览数据
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

const handleDownload = (row) => {
  window.open(`${API_BASE}/datasets/${row.id}/download`, '_blank')
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除数据集 "${row.name}" 吗?`, '警告', { type: 'warning' })
    .then(async () => {
      await axios.delete(`${API_BASE}/datasets/${row.id}`)
      ElMessage.success('删除成功')
      fetchDatasets()
    })
}

const handleCurrentChange = (val) => {
  currentPage.value = val
}

onMounted(() => {
  fetchDatasets()
})
</script>

<template>
  <div class="dataset-view">
    <el-container style="height: calc(100vh - 80px);">
      <el-aside width="240px" style="background: #fff; border-right: 1px solid #eee;">
        <div class="cap-header">能力维度 (Category)</div>
        <el-menu 
          :default-active="activeCapability" 
          @select="(index) => activeCapability = index"
          style="border-right: none;"
        >
          <el-menu-item v-for="cap in capabilities" :key="cap" :index="cap">
            <el-icon><DataLine /></el-icon>
            <span>{{ cap }}</span>
            <span class="menu-badge">
              {{ cap === 'All' ? allDatasets.length : allDatasets.filter(d => d.category === cap).length }}
            </span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      
      <el-main class="main-content">
        <div class="toolbar">
          <div class="toolbar-left">
            <h2 class="page-title">{{ activeCapability === 'All' ? '所有数据集' : activeCapability }}</h2>
            <el-tag type="info" round style="margin-left: 10px">{{ filteredDatasets.length }} items</el-tag>
          </div>
          
          <div class="toolbar-right">
            <div class="filter-box" :class="{ active: showPrivateOnly }">
              <span class="filter-label" @click="showPrivateOnly = !showPrivateOnly">
                <el-icon class="mr-1"><Filter /></el-icon> 只看私有
              </span>
              <el-switch v-model="showPrivateOnly" style="--el-switch-on-color: #9b59b6;" />
            </div>

            <el-input 
              v-model="searchKeyword" 
              placeholder="搜索名称..." 
              :prefix-icon="Search"
              clearable
              style="width: 200px; margin-right: 15px;"
            />
            
            <el-button type="primary" @click="dialogVisible = true">
              <el-icon style="margin-right: 5px"><UploadFilled /></el-icon> 导入数据集
            </el-button>
          </div>
        </div>

        <el-table :data="paginatedDatasets" border style="width: 100%" stripe>
          <el-table-column prop="id" label="ID" width="60" align="center" sortable />

          <el-table-column label="名称" min-width="160" show-overflow-tooltip>
            <template #default="scope">
              <span style="font-weight: 600; color: #303133;">{{ scope.row.name }}</span>
            </template>
          </el-table-column>

          <el-table-column label="来源" width="110" align="center">
            <template #default="scope">
              <div v-if="scope.row.is_system" class="source-badge official"><el-icon><Medal /></el-icon> 官方</div>
              <div v-else class="source-badge private"><el-icon><User /></el-icon> 私有</div>
            </template>
          </el-table-column>

          <el-table-column label="包含配置" min-width="220">
            <template #default="scope">
              <div class="config-tags">
                <el-tag 
                  v-for="cfg in scope.row.configs" 
                  :key="cfg.id" 
                  :type="cfg.mode === 'gen' ? 'warning' : 'info'"
                  size="small"
                  effect="plain"
                  class="mr-1"
                >
                  {{ cfg.mode.toUpperCase() }} ({{ cfg.display_metric }})
                </el-tag>
                <span v-if="!scope.row.configs?.length" style="color:#999; font-size:12px">暂无配置</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="category" label="能力" width="110" align="center">
            <template #default="scope">
              <el-tag effect="light" type="success">{{ scope.row.category }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
          
          <el-table-column label="操作" width="180" align="center" fixed="right">
            <template #default="scope">
              <el-button-group>
                <el-button size="small" :icon="View" @click="handleViewData(scope.row)" title="预览" />
                <el-button size="small" :icon="Download" @click="handleDownload(scope.row)" title="下载" />
                <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(scope.row)" :disabled="scope.row.is_system" title="删除" />
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-container">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="filteredDatasets.length"
            :page-size="pageSize"
            :current-page="currentPage"
            @current-change="handleCurrentChange"
          />
        </div>
      </el-main>
    </el-container>

    <el-dialog v-model="dialogVisible" title="导入数据集" width="650px" destroy-on-close>
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
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确认导入</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-model="savedDataVisible" title="数据预览" width="700px">
      <div v-if="savedDataLoading" style="text-align: center; padding: 20px;">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon> Loading...
      </div>
      <div v-else>
        <el-table :data="savedPreviewData.rows" border stripe height="300" style="width: 100%">
          <el-table-column v-for="col in savedPreviewData.columns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.dataset-view { background: #fff; height: 100%; }
.main-content { padding: 20px; display: flex; flex-direction: column; }
.cap-header { padding: 15px 20px; font-weight: bold; color: #303133; border-bottom: 1px solid #eee; background: #f5f7fa; }
.menu-badge { float: right; background: #f0f2f5; padding: 0 8px; border-radius: 10px; color: #909399; font-size: 12px; height: 20px; line-height: 20px; margin-top: 18px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.toolbar-left { display: flex; align-items: center; }
.page-title { margin: 0; font-size: 20px; color: #303133; }
.toolbar-right { display: flex; align-items: center; }
.filter-box { display: flex; align-items: center; background: #f4f4f5; padding: 6px 12px; border-radius: 20px; margin-right: 20px; transition: all 0.3s; border: 1px solid transparent; }
.filter-box:hover { background: #ebeef5; }
.filter-box.active { background: #f2ebfb; border-color: #d6bbf5; }
.filter-label { font-size: 13px; color: #606266; margin-right: 10px; cursor: pointer; display: flex; align-items: center; }
.filter-box.active .filter-label { color: #8e44ad; font-weight: bold; }
.mr-1 { margin-right: 4px; }
.source-badge { display: flex; align-items: center; justify-content: center; gap: 4px; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; width: fit-content; margin: 0 auto; }
.source-badge.official { background-color: #ecf5ff; color: #409eff; border: 1px solid #c6e2ff; }
.source-badge.private { background-color: #f3e5f5; color: #7b1fa2; border: 1px solid #e1bee7; }
.config-tags { display: flex; flex-wrap: wrap; gap: 4px; }
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
.pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
</style>