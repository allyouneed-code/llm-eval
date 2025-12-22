<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Folder, Filter, Setting } from '@element-plus/icons-vue'
import { createTask } from '@/api/task'
import { getCapColor } from '@/utils/style'

const props = defineProps({
  visible: { type: Boolean, default: false },
  models: { type: Array, default: () => [] },
  datasets: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:visible', 'success'])

// 表单与UI状态
const submitting = ref(false)
const searchText = ref('')
const showPrivateOnly = ref(false)
const activeNames = ref([]) 
const selectedMetaMap = reactive({})
const selectedConfigMap = reactive({})

const form = reactive({
  model_id: null,
  config_ids: []
})

// 监听打开，初始化状态
watch(() => props.visible, (val) => {
  if (val) {
    initForm()
  }
})

// 计算属性：分组过滤后的数据集
const filteredGroupedMetas = computed(() => {
  const groups = {}
  if (!props.datasets.length) return groups
  
  const keyword = searchText.value.toLowerCase().trim()
  
  const filtered = props.datasets.filter(meta => {
    if (showPrivateOnly.value && meta.is_system) return false
    if (!keyword) return true
    return meta.name.toLowerCase().includes(keyword) || 
           meta.category.toLowerCase().includes(keyword)
  })

  filtered.forEach(meta => {
    const cap = meta.category || 'Others'
    if (!groups[cap]) groups[cap] = []
    groups[cap].push(meta)
  })
  
  return groups
})

// 自动展开/收起逻辑
watch([searchText, showPrivateOnly], ([txt]) => {
  if (txt?.trim() || showPrivateOnly.value) {
    activeNames.value = Object.keys(filteredGroupedMetas.value)
  }
})

const initForm = () => {
  searchText.value = ''
  showPrivateOnly.value = false
  form.model_id = null
  form.config_ids = []
  Object.keys(selectedMetaMap).forEach(k => delete selectedMetaMap[k])
  Object.keys(selectedConfigMap).forEach(k => delete selectedConfigMap[k])
  
  // 初始化默认选中配置
  props.datasets.forEach(meta => {
    if (meta.configs && meta.configs.length > 0) {
      selectedConfigMap[meta.id] = meta.configs[0].id
    }
  })
}

const handleMetaCheckChange = (meta, isChecked) => {
  if (isChecked) {
    if (!selectedConfigMap[meta.id] && meta.configs.length > 0) {
      selectedConfigMap[meta.id] = meta.configs[0].id
    }
  }
  syncToForm()
}

const handleConfigChange = (metaId) => {
  if (selectedMetaMap[metaId]) {
    syncToForm()
  }
}

const syncToForm = () => {
  const ids = []
  for (const [metaId, isChecked] of Object.entries(selectedMetaMap)) {
    if (isChecked) {
      const configId = selectedConfigMap[metaId]
      if (configId) ids.push(configId)
    }
  }
  form.config_ids = ids
}

const handleSubmit = async () => {
  if (!form.model_id || form.config_ids.length === 0) {
    return ElMessage.warning('请至少选择一个模型和一个评测配置')
  }
  
  submitting.value = true
  try {
    await createTask({
      model_id: form.model_id,
      config_ids: form.config_ids
    })
    ElMessage.success('🚀 评测任务已启动')
    emit('update:visible', false)
    emit('success')
  } catch (e) {
    // 错误处理
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog 
    :model-value="visible" 
    @update:model-value="(val) => emit('update:visible', val)"
    title="新建评测任务" 
    width="1000px" 
    top="5vh" 
    :close-on-click-modal="false" 
    class="custom-dialog"
  >
    <div class="dialog-body">
      <el-form label-position="top">
        <div class="section-card">
          <div class="section-title">Step 1. 选择待测模型</div>
          <el-select v-model="form.model_id" placeholder="搜索模型..." style="width: 100%" size="large" filterable>
            <template #prefix><el-icon><Search /></el-icon></template>
            <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id">
              <div class="model-option">
                <span class="model-name">{{ m.name }}</span>
                <span class="model-path-opt"><el-icon><Folder /></el-icon> {{ m.path }}</span>
              </div>
            </el-option>
          </el-select>
        </div>

        <div class="section-card" style="margin-top: 15px; display: flex; flex-direction: column;">
          <div class="section-title">
            Step 2. 选择数据集 (按能力)
            <span class="sub-text">已选配置: {{ form.config_ids.length }}</span>
          </div>

          <div class="search-bar">
             <div class="filter-box" :class="{ active: showPrivateOnly }" @click="showPrivateOnly = !showPrivateOnly">
                <span class="filter-label">
                  <el-icon class="mr-1"><Filter /></el-icon> 只看私有
                </span>
                <el-switch v-model="showPrivateOnly" size="small" style="--el-switch-on-color: #9b59b6;" @click.stop />
             </div>

             <el-input 
               v-model="searchText" 
               placeholder="搜索数据集名称..." 
               prefix-icon="Search" 
               clearable 
               style="width: 300px"
             />
          </div>
          
          <div class="dataset-scroll-area">
            <el-collapse v-model="activeNames">
              <el-collapse-item v-for="(metas, capability) in filteredGroupedMetas" :key="capability" :name="capability">
                <template #title>
                  <div class="group-title">
                    <el-tag :color="getCapColor(capability)" effect="dark" style="border:none; color:white" round size="small" class="mr-1">
                      {{ capability }}
                    </el-tag>
                    <span class="count-badge">{{ metas.length }} datasets</span>
                  </div>
                </template>
                
                <div class="dataset-grid">
                  <div 
                    v-for="meta in metas" 
                    :key="meta.id" 
                    class="dataset-card"
                    :class="{ 'is-selected': selectedMetaMap[meta.id], 'is-official': meta.is_system }"
                  >
                    <div class="card-header">
                      <el-checkbox 
                        v-model="selectedMetaMap[meta.id]" 
                        @change="(val) => handleMetaCheckChange(meta, val)"
                      >
                        <span class="card-title" :title="meta.name">{{ meta.name }}</span>
                      </el-checkbox>
                      
                      <div v-if="meta.is_system" class="mini-badge official">Off.</div>
                      <div v-else class="mini-badge private">Pri.</div>
                    </div>
                    
                    <div class="card-body">
                       <div v-if="meta.configs && meta.configs.length > 1" class="mode-selector">
                          <span class="label">Mode:</span>
                          <el-select 
                            v-model="selectedConfigMap[meta.id]" 
                            size="small" 
                            style="width: 100px"
                            @change="handleConfigChange(meta.id)"
                            :disabled="!selectedMetaMap[meta.id]"
                          >
                             <el-option 
                               v-for="cfg in meta.configs" 
                               :key="cfg.id" 
                               :label="cfg.mode.toUpperCase()" 
                               :value="cfg.id" 
                             />
                          </el-select>
                       </div>
                       <div v-else-if="meta.configs && meta.configs.length === 1" class="mode-text">
                          <el-icon><Setting /></el-icon> 
                          <span>Mode: {{ meta.configs[0].mode.toUpperCase() }}</span>
                       </div>
                       <div v-else class="mode-text error">
                          暂无配置
                       </div>
                    </div>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
            
            <div v-if="!Object.keys(filteredGroupedMetas).length" class="empty-tip">未找到匹配的数据集</div>
          </div>
        </div>
      </el-form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('update:visible', false)" size="large">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting" size="large" style="width: 150px;">
          立即启动 ({{ form.config_ids.length }})
        </el-button>
      </div>
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