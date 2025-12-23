<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Plus, ArrowRight } from '@element-plus/icons-vue'
import { getDatasets } from '@/api/dataset'
import { createScheme } from '@/api/scheme'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

// ===========================
// 状态定义
// ===========================
const submitting = ref(false)
const form = reactive({
  name: '',
  description: ''
})

// 原始数据源
const allDatasetsMeta = ref([]) // 所有的 Dataset Meta 信息

// 1. 筛选区状态
const filterCategory = ref('') // 选中的能力维度
const filterDatasetId = ref('') // 选中的数据集 ID
const tempSelectedConfigIds = ref([]) // 当前正在勾选的配置（尚未加入最终列表）

// 2. 结果区状态
const finalSelectedConfigIds = ref([]) // 最终已选的配置 ID 集合 (Set 逻辑)

// ===========================
// 计算属性 (核心逻辑)
// ===========================

// A. 提取所有的能力维度 (去重)
const categoryOptions = computed(() => {
  const cats = new Set(allDatasetsMeta.value.map(d => d.category))
  return Array.from(cats).filter(c => c)
})

// B. 根据选中的能力维度，筛选数据集选项
const datasetOptions = computed(() => {
  if (!filterCategory.value) return []
  return allDatasetsMeta.value.filter(d => d.category === filterCategory.value)
})

// C. 获取当前选中数据集的完整信息 (包含 configs)
const currentTargetDataset = computed(() => {
  if (!filterDatasetId.value) return null
  return allDatasetsMeta.value.find(d => d.id === filterDatasetId.value)
})

// D. 生成“已选配置”的详细列表 (用于底部表格展示)
const selectedConfigsDetails = computed(() => {
  const list = []
  // 遍历所有数据找到 ID 对应的详情
  // (虽然效率不是最高，但对于前端数据量完全够用，且实现简单)
  allDatasetsMeta.value.forEach(meta => {
    meta.configs.forEach(cfg => {
      if (finalSelectedConfigIds.value.includes(cfg.id)) {
        list.push({
          id: cfg.id,
          datasetName: meta.name,
          category: meta.category,
          configName: cfg.config_name,
          mode: cfg.mode,
          metric: cfg.display_metric
        })
      }
    })
  })
  return list
})

// ===========================
// 方法逻辑
// ===========================

// 加载数据
const fetchConfigs = async () => {
  try {
    const res = await getDatasets({ page: 1, page_size: 100 })
    allDatasetsMeta.value = res.items || []
  } catch (e) {
    console.error(e)
  }
}

// 监听弹窗打开
watch(() => props.visible, (val) => {
  if (val) {
    // 重置表单
    form.name = ''
    form.description = ''
    filterCategory.value = ''
    filterDatasetId.value = ''
    tempSelectedConfigIds.value = []
    finalSelectedConfigIds.value = []
    fetchConfigs()
  }
})

// 监听筛选变化：重置下级
watch(filterCategory, () => {
  filterDatasetId.value = ''
  tempSelectedConfigIds.value = []
})
watch(filterDatasetId, () => {
  tempSelectedConfigIds.value = []
})

// 添加到已选列表
const handleAddConfigs = () => {
  if (tempSelectedConfigIds.value.length === 0) return
  
  // 合并并去重
  const newSet = new Set([...finalSelectedConfigIds.value, ...tempSelectedConfigIds.value])
  finalSelectedConfigIds.value = Array.from(newSet)
  
  // 清空临时勾选，方便继续选下一个
  tempSelectedConfigIds.value = []
  ElMessage.success('配置已添加')
}

// 移除已选
const handleRemove = (id) => {
  finalSelectedConfigIds.value = finalSelectedConfigIds.value.filter(cid => cid !== id)
}

// 提交保存
const handleSubmit = async () => {
  if (!form.name) return ElMessage.warning('请输入方案名称')
  if (finalSelectedConfigIds.value.length === 0) return ElMessage.warning('请至少添加一个数据集配置')

  submitting.value = true
  try {
    await createScheme({
      name: form.name,
      description: form.description,
      dataset_config_ids: finalSelectedConfigIds.value
    })
    ElMessage.success('方案创建成功')
    emit('update:visible', false)
    emit('success')
  } catch (e) {
    // error
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog 
    title="创建评测方案" 
    :model-value="visible"
    @update:model-value="val => emit('update:visible', val)"
    width="850px"
    top="5vh"
  >
    <el-form :model="form" label-position="top">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="方案名称" required>
            <el-input v-model="form.name" placeholder="例如：Standard Benchmark v1" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="描述">
            <el-input v-model="form.description" placeholder="备注信息" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">配置选择</el-divider>

      <div class="selection-box">
        <el-row :gutter="15" align="middle">
          <el-col :span="7">
             <div class="step-label">1. 选择维度</div>
             <el-select v-model="filterCategory" placeholder="能力维度 (Category)" style="width: 100%">
               <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
             </el-select>
          </el-col>
          
          <el-col :span="1" class="text-center text-gray-400"><el-icon><ArrowRight /></el-icon></el-col>

          <el-col :span="7">
             <div class="step-label">2. 选择数据集</div>
             <el-select 
               v-model="filterDatasetId" 
               placeholder="数据集 (Dataset)" 
               style="width: 100%"
               :disabled="!filterCategory"
               filterable
             >
               <el-option v-for="d in datasetOptions" :key="d.id" :label="d.name" :value="d.id" />
             </el-select>
          </el-col>

          <el-col :span="1" class="text-center text-gray-400"><el-icon><ArrowRight /></el-icon></el-col>

          <el-col :span="8" style="display: flex; align-items: flex-end; justify-content: flex-start;">
             <el-button 
               type="primary" 
               :disabled="tempSelectedConfigIds.length === 0"
               @click="handleAddConfigs"
               style="margin-top: 22px; width: 100%;"
             >
               <el-icon class="mr-1"><Plus /></el-icon> 
               添加选中配置 ({{ tempSelectedConfigIds.length }})
             </el-button>
          </el-col>
        </el-row>

        <div v-if="currentTargetDataset" class="config-picker-area">
          <div class="picker-header">
            <span>{{ currentTargetDataset.name }} 的可选配置：</span>
          </div>
          
          <el-checkbox-group v-model="tempSelectedConfigIds">
             <div class="config-grid">
               <el-checkbox 
                 v-for="cfg in currentTargetDataset.configs" 
                 :key="cfg.id" 
                 :label="cfg.id"
                 border
                 class="config-item"
               >
                 <span class="cfg-name">{{ cfg.config_name }}</span>
                 <el-tag size="small" type="info" effect="plain" class="ml-2">{{ cfg.display_metric }}</el-tag>
                 <el-tag v-if="cfg.mode === 'gen'" size="small" type="warning" effect="plain" class="ml-1">Gen</el-tag>
               </el-checkbox>
             </div>
          </el-checkbox-group>
        </div>
        <div v-else-if="filterCategory" class="empty-tip">
          请选择数据集以加载配置...
        </div>
      </div>

      <div class="result-box">
        <div class="result-header">
          <span>已选配置清单 ({{ finalSelectedConfigIds.length }})</span>
          <el-button v-if="finalSelectedConfigIds.length > 0" type="danger" link size="small" @click="finalSelectedConfigIds = []">清空</el-button>
        </div>
        
        <el-table :data="selectedConfigsDetails" height="250" border size="small" stripe style="width: 100%">
          <el-table-column prop="category" label="能力维度" width="120" />
          <el-table-column prop="datasetName" label="数据集" width="150" show-overflow-tooltip />
          <el-table-column prop="configName" label="配置名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="mode" label="模式" width="80">
            <template #default="scope">
              <el-tag :type="scope.row.mode === 'gen' ? 'warning' : 'info'" size="small">{{ scope.row.mode.toUpperCase() }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="metric" label="指标" width="100">
            <template #default="scope">
              <el-tag type="success" size="small">{{ scope.row.metric }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70" fixed="right" align="center">
            <template #default="scope">
               <el-button type="danger" link :icon="Delete" @click="handleRemove(scope.row.id)" />
            </template>
          </el-table-column>
        </el-table>
      </div>

    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确认创建方案</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.step-label { font-size: 12px; color: #606266; margin-bottom: 5px; font-weight: bold; }
.selection-box { background-color: #f5f7fa; padding: 15px; border-radius: 6px; border: 1px solid #ebeef5; margin-bottom: 20px; }

.config-picker-area { margin-top: 15px; background: #fff; padding: 10px; border-radius: 4px; border: 1px dashed #dcdfe6; }
.picker-header { font-size: 13px; font-weight: bold; margin-bottom: 10px; color: #303133; }
.config-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.config-item { width: 100%; margin-right: 0 !important; display: flex; align-items: center; }
.cfg-name { font-weight: 500; }

.empty-tip { margin-top: 15px; text-align: center; color: #909399; font-size: 13px; padding: 20px 0; border: 1px dashed #dcdfe6; border-radius: 4px; background: #fff; }

.result-box { border: 1px solid #e4e7ed; border-radius: 4px; overflow: hidden; }
.result-header { background-color: #fafafa; padding: 8px 12px; font-size: 13px; font-weight: bold; border-bottom: 1px solid #ebeef5; display: flex; justify-content: space-between; align-items: center; }

:deep(.el-checkbox__label) { display: flex; align-items: center; width: 100%; }
</style>