<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

// === 1. 数据定义 ===
const tableData = ref([])      // 任务列表
const modelList = ref([])      // 模型列表（用于下拉选项 + ID转名称）
const datasetList = ref([])    // 数据集列表（用于下拉选项）

const dialogVisible = ref(false)
const submitting = ref(false)

// 表单数据
const form = reactive({
  model_id: null,
  dataset_ids: []
})

const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 2. 辅助函数 ===
// 通过 model_id 查找 model_name
const getModelName = (id) => {
  const found = modelList.value.find(m => m.id === id)
  return found ? found.name : `Unknown (ID: ${id})`
}

// 解析后端存的 JSON 字符串列表 '["GSM8K", "C-Eval"]'
const parseDatasets = (jsonStr) => {
  try {
    return JSON.parse(jsonStr)
  } catch (e) {
    return []
  }
}

// 状态对应的颜色
const getStatusTag = (status) => {
  const map = {
    pending: 'info',
    running: 'primary',
    success: 'success',
    failed: 'danger',
    aborted: 'warning'
  }
  return map[status] || 'info'
}

// === 3. API 交互 ===

// 一次性加载所有需要的数据
const fetchData = async () => {
  try {
    // 并行请求：任务列表、模型列表、数据集列表
    const [taskRes, modelRes, datasetRes] = await Promise.all([
      axios.get(`${API_BASE}/tasks/`),
      axios.get(`${API_BASE}/models/`),
      axios.get(`${API_BASE}/datasets/`)
    ])
    
    tableData.value = taskRes.data
    modelList.value = modelRes.data
    datasetList.value = datasetRes.data
    
  } catch (error) {
    ElMessage.error('数据加载失败，请检查后端服务')
  }
}

// 提交新任务
const handleSubmit = async () => {
  if (!form.model_id) return ElMessage.warning('请选择模型')
  if (form.dataset_ids.length === 0) return ElMessage.warning('请至少选择一个数据集')

  submitting.value = true
  try {
    await axios.post(`${API_BASE}/tasks/`, form)
    ElMessage.success('任务创建成功，开始评测！')
    dialogVisible.value = false
    
    // 重置表单
    form.model_id = null
    form.dataset_ids = []
    
    // 刷新列表（实际项目中可以做一个定时轮询 Polling 来刷新进度）
    fetchData()
    
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '任务创建失败')
  } finally {
    submitting.value = false
  }
}

// === 4. 生命周期 ===
onMounted(() => {
  fetchData()
  
  // 可选：每 5 秒自动刷新一次列表进度
  // setInterval(fetchData, 5000)
})
</script>

<template>
  <div>
    <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
      <el-button type="primary" @click="dialogVisible = true">
        <el-icon style="margin-right: 5px"><VideoPlay /></el-icon> 新建评测任务
      </el-button>
      
      <el-button @click="fetchData" icon="Refresh" circle />
    </div>

    <el-table :data="tableData" border style="width: 100%">
      
      <el-table-column prop="id" label="ID" width="60" align="center" />
      
      <el-table-column label="评测模型" min-width="150">
        <template #default="scope">
          <span style="font-weight: bold;">{{ getModelName(scope.row.model_id) }}</span>
        </template>
      </el-table-column>
      
      <el-table-column label="数据集" min-width="200">
        <template #default="scope">
          <el-tag 
            v-for="name in parseDatasets(scope.row.datasets_list)" 
            :key="name" 
            size="small" 
            style="margin-right: 5px; margin-bottom: 5px;"
          >
            {{ name }}
          </el-tag>
        </template>
      </el-table-column>
      
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="scope">
          <el-tag :type="getStatusTag(scope.row.status)">
            {{ scope.row.status }}
          </el-tag>
        </template>
      </el-table-column>
      
      <el-table-column prop="progress" label="进度" width="180" align="center">
        <template #default="scope">
          <el-progress 
            :percentage="scope.row.progress" 
            :status="scope.row.status === 'failed' ? 'exception' : (scope.row.status === 'success' ? 'success' : '')"
          />
        </template>
      </el-table-column>
      
      <el-table-column prop="created_at" label="提交时间" width="180" align="center">
        <template #default="scope">
          {{ new Date(scope.row.created_at).toLocaleString() }}
        </template>
      </el-table-column>
      
    </el-table>

    <el-dialog v-model="dialogVisible" title="新建评测任务" width="500px">
      <el-form :model="form" label-position="top">
        
        <el-form-item label="选择模型 (Model)">
          <el-select v-model="form.model_id" placeholder="请选择模型" style="width: 100%">
            <el-option 
              v-for="item in modelList" 
              :key="item.id" 
              :label="item.name" 
              :value="item.id" 
            >
              <span style="float: left">{{ item.name }}</span>
              <span style="float: right; color: #8492a6; font-size: 13px">{{ item.type }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        
        <el-form-item label="选择数据集 (Datasets)">
          <el-select 
            v-model="form.dataset_ids" 
            multiple 
            placeholder="请选择数据集 (可多选)" 
            style="width: 100%"
          >
            <el-option 
              v-for="item in datasetList" 
              :key="item.id" 
              :label="item.name" 
              :value="item.id" 
            >
              <span style="float: left">{{ item.name }}</span>
              <span style="float: right; color: #8492a6; font-size: 13px">{{ item.metric_name }}</span>
            </el-option>
          </el-select>
        </el-form-item>

      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            提交评测
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>