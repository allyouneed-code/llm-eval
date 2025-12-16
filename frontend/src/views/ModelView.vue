<script setup>
import { ref, onMounted, reactive } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Folder, Connection, CircleCheck, CircleClose } from '@element-plus/icons-vue'

// === 1. 数据定义 ===
const tableData = ref([]) 
const dialogVisible = ref(false)
const submitting = ref(false)

// 校验状态 (仅保留 name)
const validationState = reactive({
  name: null,   // null: 未校验, true: 通过, false: 失败
  nameMsg: ''
})

// 表单数据
const form = reactive({
  name: '',
  path: '',
  type: 'local', // 默认 local
  param_size: '7B',
  description: ''
})

const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 2. 核心逻辑 ===

// 重置表单
const resetForm = () => {
  form.name = ''
  form.path = ''
  form.type = 'local'
  form.param_size = '7B'
  form.description = ''
  
  validationState.name = null
  validationState.nameMsg = ''
}

const openDialog = () => {
  resetForm()
  dialogVisible.value = true
}

// 获取列表
const fetchModels = async () => {
  try {
    const res = await axios.get(`${API_BASE}/models/`)
    tableData.value = res.data
  } catch (error) {
    ElMessage.error('获取模型列表失败')
  }
}

// --- 旅程图优化 A: 实时校验名称 (Input失去焦点时) ---
const handleNameBlur = async () => {
  if (!form.name) return
  try {
    const res = await axios.post(`${API_BASE}/models/validate/name`, { name: form.name })
    if (res.data.unique) {
      validationState.name = true
      validationState.nameMsg = ''
    } else {
      validationState.name = false
      validationState.nameMsg = '该模型名称已存在'
    }
  } catch (e) {
    console.error(e)
  }
}

// 提交注册
const handleSubmit = async () => {
  if (!form.name || !form.path) {
    return ElMessage.warning('请填写完整信息')
  }
  if (validationState.name === false) {
    return ElMessage.error('模型名称重复，请修改')
  }

  submitting.value = true
  try {
    await axios.post(`${API_BASE}/models/`, form)
    ElMessage.success('注册成功')
    dialogVisible.value = false
    fetchModels()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '注册失败')
  } finally {
    submitting.value = false
  }
}

// 删除模型
const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除模型 "${row.name}" 吗?`, '警告', { type: 'warning' })
    .then(async () => {
      await axios.delete(`${API_BASE}/models/${row.id}`)
      ElMessage.success('删除成功')
      fetchModels()
    })
}

onMounted(fetchModels)
</script>

<template>
  <div class="model-view">
    <div style="margin-bottom: 20px;">
      <el-button type="primary" size="large" @click="openDialog">
        <el-icon style="margin-right: 5px"><Plus /></el-icon> 注册新模型
      </el-button>
    </div>

    <el-table :data="tableData" border style="width: 100%" stripe>
      <el-table-column prop="id" label="ID" width="60" align="center" />
      <el-table-column prop="name" label="模型名称" min-width="150" show-overflow-tooltip>
        <template #default="scope">
          <span style="font-weight: 600">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="type" label="接入方式" width="120" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.type === 'api' ? 'warning' : 'info'" effect="light" round>
            {{ scope.row.type === 'api' ? 'API 接入' : '本地加载' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="param_size" label="参数量" width="100" align="center" />
      <el-table-column prop="path" label="路径 / URL" min-width="250" show-overflow-tooltip />
      <el-table-column label="操作" width="100" align="center">
        <template #default="scope">
          <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="模型资产接入" width="600px" destroy-on-close>
      
      <div style="margin-bottom: 20px; padding: 0 10px;">
        <el-steps :active="1" simple>
          <el-step title="基础信息" icon="Edit" />
          <el-step title="接入配置" icon="Connection" />
        </el-steps>
      </div>

      <el-form :model="form" label-position="top" size="large">
        
        <el-form-item label="接入方式">
          <div class="mode-selection">
            <div 
              class="mode-card" 
              :class="{ active: form.type === 'local' }"
              @click="form.type = 'local'"
            >
              <el-icon :size="24"><Folder /></el-icon>
              <div class="card-title">本地加载</div>
              <div class="card-desc">使用服务器本地存储的模型权重文件</div>
            </div>
            
            <div 
              class="mode-card" 
              :class="{ active: form.type === 'api' }"
              @click="form.type = 'api'"
            >
              <el-icon :size="24"><Connection /></el-icon>
              <div class="card-title">API 接入</div>
              <div class="card-desc">连接 OpenAI 格式或 vLLM 远程接口</div>
            </div>
          </div>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="16">
            <el-form-item label="模型显示名称" :error="validationState.nameMsg">
              <el-input 
                v-model="form.name" 
                placeholder="例如: Llama3-8B-Instruct" 
                @blur="handleNameBlur"
              >
                <template #suffix>
                  <el-icon v-if="validationState.name === true" color="#67C23A"><CircleCheck /></el-icon>
                  <el-icon v-if="validationState.name === false" color="#F56C6C"><CircleClose /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="参数量级">
              <el-select v-model="form.param_size">
                <el-option label="7B" value="7B" />
                <el-option label="13B" value="13B" />
                <el-option label="70B+" value="70B+" />
                <el-option label="Unknown" value="Unknown" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item :label="form.type === 'local' ? '服务器绝对路径' : 'API Base URL'">
          <el-input 
            v-model="form.path" 
            :placeholder="form.type === 'local' ? '/data/models/llama3...' : 'http://192.168.1.100:8000/v1'" 
          />
        </el-form-item>

      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            保 存
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mode-selection {
  display: flex;
  gap: 20px;
  width: 100%;
}

.mode-card {
  flex: 1;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s;
  text-align: center;
}

.mode-card:hover {
  border-color: #409EFF;
  background-color: #ecf5ff;
}

.mode-card.active {
  border-color: #409EFF;
  background-color: #ecf5ff;
  color: #409EFF;
}

.card-title {
  font-weight: bold;
  margin-top: 8px;
  font-size: 16px;
}

.card-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>