<script setup>
import { ref, onMounted, reactive } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

// === 1. 数据定义 ===
const tableData = ref([]) // 表格数据
const dialogVisible = ref(false) // 弹窗是否显示
const formRef = ref(null)

// 表单数据模型 (对应后端的 Schema)
const form = reactive({
  name: '',
  path: '',
  type: 'local',
  param_size: '7B',
  description: ''
})

// === 2. API 交互函数 ===
const API_BASE = 'http://127.0.0.1:8000/api/v1'

// 获取列表
const fetchModels = async () => {
  try {
    const res = await axios.get(`${API_BASE}/models/`)
    tableData.value = res.data
  } catch (error) {
    ElMessage.error('获取模型列表失败')
  }
}

// 提交新模型
const handleSubmit = async () => {
  try {
    await axios.post(`${API_BASE}/models/`, form)
    ElMessage.success('模型注册成功')
    dialogVisible.value = false // 关闭弹窗
    fetchModels() // 刷新列表
    // 重置表单
    form.name = ''
    form.path = ''
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '注册失败')
  }
}

// 删除模型
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除模型 "${row.name}" 吗?`,
    '警告',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    await axios.delete(`${API_BASE}/models/${row.id}`)
    ElMessage.success('删除成功')
    fetchModels()
  })
}

// === 3. 生命周期 ===
onMounted(() => {
  fetchModels() // 页面一加载就请求数据
})
</script>

<template>
  <div>
    <div style="margin-bottom: 20px;">
      <el-button type="primary" @click="dialogVisible = true">
        <el-icon style="margin-right: 5px"><Plus /></el-icon> 注册新模型
      </el-button>
    </div>

    <el-table :data="tableData" border style="width: 100%">
      
      <el-table-column prop="id" label="ID" width="60" align="center" />
      
      <el-table-column prop="name" label="模型名称" min-width="150" show-overflow-tooltip />
      
      <el-table-column prop="type" label="类型" width="100" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.type === 'api' ? 'success' : 'info'">
            {{ scope.row.type }}
          </el-tag>
        </template>
      </el-table-column>
      
      <el-table-column prop="param_size" label="参数量" width="100" align="center" />
      
      <el-table-column 
        prop="path" 
        label="路径/URL" 
        min-width="300" 
        show-overflow-tooltip 
      />
      
      <el-table-column prop="created_at" label="注册时间" width="180" align="center">
        <template #default="scope">
          {{ new Date(scope.row.created_at).toLocaleString() }}
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="100" align="center">
        <template #default="scope">
          <el-button link type="danger" size="small" @click="handleDelete(scope.row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="注册新模型" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如: Llama3-8B" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio label="local">本地路径</el-radio>
            <el-radio label="api">云端 API</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="路径/URL">
          <el-input v-model="form.path" placeholder="本地绝对路径或API地址" />
        </el-form-item>
        <el-form-item label="参数量">
          <el-select v-model="form.param_size" placeholder="请选择">
            <el-option label="7B" value="7B" />
            <el-option label="13B" value="13B" />
            <el-option label="72B" value="72B" />
            <el-option label="Unknown" value="Unknown" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit">确认注册</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>