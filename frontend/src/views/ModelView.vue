<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Folder, Connection, CircleCheck, CircleClose, Key, Link } from '@element-plus/icons-vue'
import { getModels, createModel, deleteModel, validateModelName } from '@/api/model'
import { getDicts } from '@/api/dict'

// === 数据定义 ===
const tableData = ref([]) 
const dialogVisible = ref(false)
const submitting = ref(false)
const paramSizeOptions = ref([])

const validationState = reactive({
  name: null, 
  nameMsg: ''
})

// ✅ 保持原有 reactive 结构
const form = reactive({
  name: '',
  type: 'local', // 'local' | 'api'
  param_size: '7B',
  description: '',
  path: '', 
  base_url: '',
  api_key: ''
})

// === 核心逻辑 ===

// ✅ 采用手动赋值，避开 Object.assign 可能导致的类型错误
const resetForm = () => {
  form.name = ''
  form.type = 'local'
  form.path = ''
  form.base_url = ''
  form.api_key = ''
  form.param_size = '7B'
  form.description = ''
  
  validationState.name = null
  validationState.nameMsg = ''
}

const openDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const fetchModels = async () => {
  try {
    const data = await getModels()
    tableData.value = data
  } catch (error) {
    console.error(error)
  }
}

const handleNameBlur = async () => {
  if (!form.name) return
  try {
    const data = await validateModelName(form.name)
    if (data.unique) {
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

// ✅ 修改：提交逻辑加固，处理本地服务器 API
const handleSubmit = async () => {
  if (!form.name) return ElMessage.warning('请输入模型名称')
  
  if (form.type === 'local' && !form.path) {
    return ElMessage.warning('请输入本地模型路径')
  }
  if (form.type === 'api') {
    if (!form.path) return ElMessage.warning('请输入 API 模型 ID (如 gpt-4)')
    if (!form.base_url) return ElMessage.warning('请输入 API 地址')
  }

  if (validationState.name === false) {
    return ElMessage.error('模型名称重复，请修改')
  }

  submitting.value = true
  try {
    // 构造 payload
    const payload = {
      name: form.name,
      type: form.type === 'local' ? 'huggingface' : 'api', // 适配后端类型映射
      path: form.path,
      base_url: form.base_url,
      // ✅ 逻辑注入：如果 API Key 为空且是 API 模式，传入 EMPTY 占位符以适配本地服务器
      api_key: (form.type === 'api' && !form.api_key) ? 'EMPTY' : form.api_key,
      param_size: form.param_size,
      description: form.description,
      config_json: '{}'
    }

    await createModel(payload)
    ElMessage.success('注册成功')
    dialogVisible.value = false
    fetchModels()
  } catch (error) {
    // 错误由拦截器处理
  } finally {
    submitting.value = false
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除模型 "${row.name}" 吗?`, '警告', { type: 'warning' })
    .then(async () => {
      await deleteModel(row.id)
      ElMessage.success('删除成功')
      fetchModels()
    })
    .catch(() => {})
}

onMounted(async () => {
  fetchModels()
  try {
    const res = await getDicts({ category: 'model_param_size' })
    paramSizeOptions.value = res
  } catch (e) {
    console.error("字典加载失败", e)
  }
})
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
          <el-tag :type="scope.row.type === 'api' ? 'success' : 'info'" effect="light" round>
            {{ scope.row.type === 'api' ? 'API 服务' : '本地加载' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="path" label="路径 / 模型ID" min-width="200" show-overflow-tooltip>
         <template #default="scope">
            <div>{{ scope.row.path }}</div>
            <div v-if="scope.row.type === 'api' && scope.row.base_url" style="font-size: 12px; color: #909399;">
              <el-icon style="vertical-align: middle"><Link /></el-icon> {{ scope.row.base_url }}
            </div>
         </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center">
        <template #default="scope">
          <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="模型资产接入" width="650px" destroy-on-close>
      <div style="margin-bottom: 20px; padding: 0 10px;">
        <el-steps :active="1" simple>
          <el-step title="基础信息" icon="Edit" />
          <el-step title="配置详情" icon="Connection" />
        </el-steps>
      </div>

      <el-form :model="form" label-position="top" size="large">
        <el-form-item label="接入方式">
          <div class="mode-selection">
            <div class="mode-card" :class="{ active: form.type === 'local' }" @click="form.type = 'local'">
              <el-icon :size="24"><Folder /></el-icon>
              <div class="card-title">本地加载</div>
              <div class="card-desc">使用服务器本地权重文件</div>
            </div>
            <div class="mode-card" :class="{ active: form.type === 'api' }" @click="form.type = 'api'">
              <el-icon :size="24"><Connection /></el-icon>
              <div class="card-title">API 接入</div>
              <div class="card-desc">连接 OpenAI / vLLM 远程接口</div>
            </div>
          </div>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="16">
            <el-form-item label="模型显示名称" :error="validationState.nameMsg">
              <el-input v-model="form.name" placeholder="例如: DeepSeek-V3" @blur="handleNameBlur">
                <template #suffix>
                  <el-icon v-if="validationState.name === true" color="#67C23A"><CircleCheck /></el-icon>
                  <el-icon v-if="validationState.name === false" color="#F56C6C"><CircleClose /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="参数量级">
              <el-select v-model="form.param_size" placeholder="请选择参数量">
                  <el-option v-for="item in paramSizeOptions" :key="item.id" :label="item.label" :value="item.code" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <template v-if="form.type === 'local'">
          <el-form-item label="本地路径 (Path)">
            <el-input v-model="form.path" placeholder="/app/models/llama3-8b">
              <template #prefix><el-icon><Folder /></el-icon></template>
            </el-input>
          </el-form-item>
        </template>

        <template v-if="form.type === 'api'">
          <el-form-item label="模型 ID (Model ID)">
            <el-input v-model="form.path" placeholder="例如: gpt-4, llama3" />
            <div class="form-tip">对应 OpenCompass 配置中的 <code>path</code> 字段</div>
          </el-form-item>

          <el-form-item label="接口地址 (Base URL)">
            <el-input v-model="form.base_url" placeholder="http://localhost:11434/v1">
               <template #prefix><el-icon><Link /></el-icon></template>
            </el-input>
            <div class="form-tip" style="color: #E6A23C;">提示：Docker 环境访问宿主机请尝试用 http://host.docker.internal:端口/v1</div>
          </el-form-item>

          <el-form-item label="API Key">
            <el-input v-model="form.api_key" type="password" show-password placeholder="本地服务若无 Key 可不填">
              <template #prefix><el-icon><Key /></el-icon></template>
            </el-input>
          </el-form-item>
        </template>

        <el-form-item label="描述 (可选)">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="备注信息..." />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">保 存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* ✅ 严格保留原有的 CSS 样式 */
.mode-selection { display: flex; gap: 20px; width: 100%; }
.mode-card { flex: 1; border: 2px solid #e4e7ed; border-radius: 8px; padding: 15px; cursor: pointer; transition: all 0.3s; text-align: center; position: relative; overflow: hidden; }
.mode-card:hover { border-color: #409EFF; background-color: #f0f9eb; }
.mode-card.active { border-color: #409EFF; background-color: #ecf5ff; color: #409EFF; box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1); }
.mode-card.active::after { content: ""; position: absolute; top: 0; right: 0; width: 0; height: 0; border-top: 20px solid #409EFF; border-left: 20px solid transparent; }
.card-title { font-weight: bold; margin-top: 8px; font-size: 16px; }
.card-desc { font-size: 12px; color: #909399; margin-top: 4px; }
.form-tip { font-size: 12px; color: #909399; line-height: 1.4; margin-top: 4px; }
</style>