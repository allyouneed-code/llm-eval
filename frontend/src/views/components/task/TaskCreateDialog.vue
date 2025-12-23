<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getModels } from '@/api/model'
import { getDatasets } from '@/api/dataset'
import { createTask } from '@/api/task'
import { getSchemes } from '@/api/scheme' // 🆕

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

const activeTab = ref('scheme') // 默认使用方案创建 'scheme' | 'custom'
const submitting = ref(false)

// 表单数据
const form = reactive({
  model_id: '',
  scheme_id: '',   // Tab 1 用
  config_ids: []   // Tab 2 用
})

// 数据源
const models = ref([])
const schemes = ref([])
const datasets = ref([]) // 用于 Tab 2 的树形选择

// 1. 初始化加载
const initData = async () => {
  // 加载模型
  const modelRes = await getModels()
  models.value = modelRes
  
  // 加载方案
  const schemeRes = await getSchemes()
  schemes.value = schemeRes
  
  // 加载数据集 (用于 Tab 2 和 Tab 1 的预览)
  const datasetRes = await getDatasets({ page: 1, page_size: 100 })
  datasets.value = datasetRes.items
}

watch(() => props.visible, (val) => {
  if (val) {
    form.model_id = ''
    form.scheme_id = ''
    form.config_ids = []
    activeTab.value = 'scheme'
    initData()
  }
})

// Tab 1: 选定方案后，计算预览信息
const currentScheme = computed(() => {
  return schemes.value.find(s => s.id === form.scheme_id)
})
const schemePreviewCount = computed(() => {
  return currentScheme.value ? currentScheme.value.dataset_config_ids.length : 0
})

// Tab 2: 树形数据转换
const treeData = computed(() => {
  return datasets.value.map(meta => ({
    label: `[${meta.category}] ${meta.name}`,
    value: `meta-${meta.id}`,
    children: meta.configs.map(cfg => ({
      label: `${cfg.config_name} (${cfg.display_metric})`,
      value: cfg.id // 实际选中的是这个 ID
    }))
  }))
})

const handleSubmit = async () => {
  if (!form.model_id) return ElMessage.warning('请选择评测模型')

  const payload = {
    model_id: form.model_id,
    scheme_id: null,
    config_ids: []
  }

  if (activeTab.value === 'scheme') {
    if (!form.scheme_id) return ElMessage.warning('请选择一个评测方案')
    payload.scheme_id = form.scheme_id
    // config_ids 留空，后端会自动填充
  } else {
    if (form.config_ids.length === 0) return ElMessage.warning('请至少选择一个数据集')
    // 过滤掉父节点 (meta-xx)，只保留数字 ID
    const realIds = form.config_ids.filter(id => typeof id === 'number')
    if (realIds.length === 0) return ElMessage.warning('请选择具体的配置项')
    payload.config_ids = realIds
  }

  submitting.value = true
  try {
    await createTask(payload)
    ElMessage.success('评测任务创建成功')
    emit('update:visible', false)
    emit('success')
  } catch (e) {
    // console.error(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog 
    title="新建评测任务" 
    :model-value="visible"
    @update:model-value="val => emit('update:visible', val)"
    width="600px"
  >
    <el-form label-position="top">
      <el-form-item label="待测模型 (Model)" required>
        <el-select v-model="form.model_id" placeholder="请选择模型" style="width: 100%">
          <el-option 
            v-for="m in models" 
            :key="m.id" 
            :label="m.name" 
            :value="m.id" 
          />
        </el-select>
      </el-form-item>

      <el-tabs v-model="activeTab" type="border-card" class="mb-4">
        
        <el-tab-pane label="引用方案 (推荐)" name="scheme">
          <div class="p-2">
            <el-form-item label="选择方案" style="margin-bottom: 10px;">
              <el-select v-model="form.scheme_id" placeholder="选择预设的 Benchmark..." style="width: 100%">
                <el-option 
                  v-for="s in schemes" 
                  :key="s.id" 
                  :label="s.name" 
                  :value="s.id" 
                />
              </el-select>
            </el-form-item>
            
            <div v-if="currentScheme" class="bg-gray-50 p-3 rounded text-sm text-gray-600">
              <div class="font-bold mb-1">方案详情：</div>
              <div class="mb-1">{{ currentScheme.description || '无描述' }}</div>
              <div>
                包含数据集配置：
                <el-tag type="success" size="small">{{ schemePreviewCount }} 个</el-tag>
              </div>
            </div>
            <div v-else class="text-gray-400 text-xs mt-2">
              <el-icon><InfoFilled /></el-icon> 选择方案后将自动加载其中定义的所有数据集配置。
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="自由组合 (Custom)" name="custom">
          <div class="p-2">
            <el-form-item label="勾选数据集配置" style="margin-bottom: 0;">
              <el-tree-select
                v-model="form.config_ids"
                :data="treeData"
                multiple
                show-checkbox
                collapse-tags
                placeholder="请展开分类勾选具体配置..."
                style="width: 100%"
              />
            </el-form-item>
          </div>
        </el-tab-pane>
      </el-tabs>

    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        立即评测
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
/* 样式与原 TaskView 保持一致，但范围缩小到组件内 */
.search-bar { margin-bottom: 10px; border-bottom: 1px solid #f0f0f0; padding-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
.filter-box { display: flex; align-items: center; background: #f4f4f5; padding: 4px 10px; border-radius: 16px; margin-right: 10px; cursor: pointer; transition: all 0.3s; border: 1px solid transparent; }
.filter-box:hover { background: #ebeef5; }
.filter-box.active { background: #f2ebfb; border-color: #d6bbf5; }
.filter-label { font-size: 12px; color: #606266; margin-right: 8px; display: flex; align-items: center; }
.filter-box.active .filter-label { color: #8e44ad; font-weight: bold; }
.mini-badge { font-size: 10px; padding: 1px 4px; border-radius: 4px; font-weight: bold; height: 16px; line-height: 14px; flex-shrink: 0; margin-left: 5px; }
.mini-badge.official { background-color: #ecf5ff; color: #409eff; border: 1px solid #c6e2ff; }
.mini-badge.private { background-color: #f3e5f5; color: #7b1fa2; border: 1px solid #e1bee7; }
.dataset-card.is-official { border-left: 3px solid #409EFF; }
.dataset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; padding: 12px; background: #fafafa; }
.dataset-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px; display: flex; flex-direction: column; justify-content: space-between; transition: all 0.2s; }
.dataset-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.05); transform: translateY(-1px); }
.dataset-card.is-selected { border-color: #409EFF; background-color: #ecf5ff; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.card-title { font-weight: 600; font-size: 14px; color: #303133; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-all; }
.card-body { padding-top: 5px; border-top: 1px dashed #eee; display: flex; align-items: center; justify-content: space-between; }
.mode-selector { display: flex; align-items: center; gap: 5px; width: 100%; }
.mode-selector .label { font-size: 12px; color: #909399; }
.mode-text { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; }
.mode-text.error { color: #F56C6C; }
.section-card { background: #fff; padding: 15px; border: 1px solid #ebeef5; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
.section-title { font-size: 15px; font-weight: bold; color: #303133; margin-bottom: 12px; border-left: 4px solid #409EFF; padding-left: 10px; display: flex; justify-content: space-between; }
.dataset-scroll-area { max-height: 50vh; overflow-y: auto; padding-right: 5px; }
.group-title { width: 100%; display: flex; align-items: center; }
.count-badge { margin-left: auto; font-size: 12px; color: #999; margin-right: 10px; }
.model-option { display: flex; flex-direction: column; }
.model-name { font-weight: bold; color: #303133; }
.model-path-opt { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; }
.sub-text { font-weight: normal; font-size: 12px; color: #909399; }
</style>