<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled, Cpu, CollectionTag, Odometer, DataAnalysis, List } from '@element-plus/icons-vue' 
import { getModels } from '@/api/model'
import { getDatasets } from '@/api/dataset'
import { createTask } from '@/api/task'
import { getSchemes } from '@/api/scheme'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

const submitting = ref(false)

// 表单数据
const form = reactive({
  model_id: '',
  scheme_id: ''
})

// 数据源
const models = ref([])
const schemes = ref([])
const allDatasets = ref([]) 

// 初始化加载
const initData = async () => {
  try {
    const [modelRes, schemeRes, datasetRes] = await Promise.all([
      getModels(),
      getSchemes(),
      getDatasets({ page: 1, page_size: 500 }) 
    ])
    
    models.value = modelRes
    schemes.value = schemeRes
    allDatasets.value = datasetRes.items
  } catch (e) {
    console.error("加载基础数据失败", e)
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    form.model_id = ''
    form.scheme_id = ''
    initData()
  }
})

// 计算选中方案的详细信息
const selectedSchemeRichInfo = computed(() => {
  if (!form.scheme_id) return null
  
  const scheme = schemes.value.find(s => s.id === form.scheme_id)
  if (!scheme) return null

  const configIds = scheme.dataset_config_ids || []
  const details = []
  
  allDatasets.value.forEach(meta => {
    if (meta.configs) {
      meta.configs.forEach(cfg => {
        if (configIds.includes(cfg.id)) {
          details.push({
            id: cfg.id,
            datasetName: meta.name,
            category: meta.category,
            configName: cfg.config_name,
            mode: cfg.mode,
            metric: cfg.display_metric
          })
        }
      })
    }
  })

  const categories = Array.from(new Set(details.map(d => d.category)))

  return { ...scheme, details, categories }
})

const handleSubmit = async () => {
  if (!form.model_id) return ElMessage.warning('请选择评测模型')
  if (!form.scheme_id) return ElMessage.warning('请选择一个评测方案')

  const payload = {
    model_id: form.model_id,
    scheme_id: form.scheme_id,
    config_ids: [] 
  }

  submitting.value = true
  try {
    await createTask(payload)
    ElMessage.success('评测任务创建成功，正在后台运行...')
    emit('update:visible', false)
    emit('success')
  } catch (e) {
    // error handled by request interceptor
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
    width="750px"
    top="8vh"
    destroy-on-close
    class="custom-dialog"
  >
    <div class="dialog-body">
      
      <div class="control-panel">
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="input-label"><el-icon><Cpu /></el-icon> 待测模型</div>
            <el-select 
              v-model="form.model_id" 
              placeholder="选择模型..." 
              style="width: 100%" 
              size="large"
              filterable
            >
              <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </el-col>

          <el-col :span="12">
            <div class="input-label"><el-icon><CollectionTag /></el-icon> 评测方案</div>
            <el-select 
              v-model="form.scheme_id" 
              placeholder="选择评测方案..." 
              style="width: 100%" 
              size="large"
              filterable
            >
              <el-option v-for="s in schemes" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-col>
        </el-row>
      </div>

      <transition name="el-zoom-in-top">
        
        <div v-if="selectedSchemeRichInfo" class="scheme-detail-card">
          
          <div class="card-header">
            <div class="scheme-title">
              <el-icon class="mr-1 text-blue-500"><DataAnalysis /></el-icon> 
              {{ selectedSchemeRichInfo.name }}
            </div>
            <div class="scheme-desc">
              {{ selectedSchemeRichInfo.description || '暂无描述信息' }}
            </div>
          </div>

          <div class="summary-bar">
            <div class="sum-item">
              <span class="lbl">能力维度</span>
              <span class="val">{{ selectedSchemeRichInfo.categories.length }}</span>
            </div>
            <div class="divider"></div>
            <div class="sum-item">
              <span class="lbl">数据集配置</span>
              <span class="val">{{ selectedSchemeRichInfo.details.length }}</span>
            </div>
            <div class="divider"></div>
            <div class="tags-container">
              <el-tag 
                v-for="cat in selectedSchemeRichInfo.categories.slice(0, 4)" 
                :key="cat" 
                type="info" effect="plain" size="small"
                class="cat-tag"
              >
                {{ cat }}
              </el-tag>
              <span v-if="selectedSchemeRichInfo.categories.length > 4" class="more-text">...</span>
            </div>
          </div>

          <div class="table-wrapper">
            <el-table 
              :data="selectedSchemeRichInfo.details" 
              size="small" 
              height="240" 
              style="width: 100%"
              :header-cell-style="{ background: '#f5f7fa', color: '#606266' }"
            >
              <el-table-column prop="datasetName" label="数据集名称" min-width="140" show-overflow-tooltip>
                <template #default="scope">
                  <span class="font-medium text-gray-700">{{ scope.row.datasetName }}</span>
                </template>
              </el-table-column>
              
              <el-table-column prop="category" label="维度" width="110" show-overflow-tooltip />
              
              <el-table-column prop="configName" label="配置子项" min-width="130" show-overflow-tooltip />
              
              <el-table-column prop="mode" label="模式" width="80" align="center">
                <template #default="scope">
                   <el-tag v-if="scope.row.mode==='gen'" type="warning" size="small" effect="plain" round>GEN</el-tag>
                   <el-tag v-else type="info" size="small" effect="plain" round>PPL</el-tag>
                </template>
              </el-table-column>
              
              <el-table-column prop="metric" label="指标" width="100" align="right">
                 <template #default="scope">
                   <div class="metric-cell">
                     <el-icon><Odometer /></el-icon>
                     <span>{{ scope.row.metric }}</span>
                   </div>
                 </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
        
        <div v-else class="empty-placeholder">
           <div class="placeholder-content">
             <el-icon class="icon-lg"><List /></el-icon>
             <p class="main-text">请先选择一个评测方案</p>
             <p class="sub-text">选择后将在此处展示方案包含的详细数据集和配置信息</p>
           </div>
        </div>

      </transition>

    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('update:visible', false)" size="large">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit" size="large" icon="VideoPlay">
          立即评测
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-body { padding: 0 10px; }

/* 1. 顶部控制区 */
.control-panel { margin-bottom: 20px; }
.input-label { 
  font-size: 13px; font-weight: 600; color: #303133; margin-bottom: 8px; 
  display: flex; align-items: center; gap: 6px;
}

/* 2. 详情卡片容器 */
.scheme-detail-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.03);
}

/* 卡片头部 */
.card-header {
  background: linear-gradient(to right, #f8fafc, #fff);
  padding: 15px 20px;
  border-bottom: 1px solid #ebeef5;
}
.scheme-title { font-size: 16px; font-weight: 700; color: #303133; display: flex; align-items: center; }
.scheme-desc { font-size: 13px; color: #909399; margin-top: 5px; padding-left: 20px; }

/* 统计摘要条 */
.summary-bar {
  display: flex; align-items: center; padding: 12px 20px; background-color: #fff;
  border-bottom: 1px solid #ebeef5;
}
.sum-item { display: flex; flex-direction: column; align-items: center; min-width: 60px; }
.sum-item .lbl { font-size: 10px; color: #909399; text-transform: uppercase; }
.sum-item .val { font-size: 16px; font-weight: bold; color: #409EFF; }
.divider { width: 1px; height: 24px; background: #ebeef5; margin: 0 15px; }

.tags-container { flex-grow: 1; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.cat-tag { border-radius: 4px; }
.more-text { font-size: 12px; color: #C0C4CC; margin-left: 4px; }

/* 表格区域 */
.table-wrapper { padding: 0; }
.metric-cell { display: flex; align-items: center; justify-content: flex-end; gap: 4px; color: #67c23a; font-family: monospace; font-weight: 600; }

/* 3. 空状态占位 */
.empty-placeholder {
  height: 300px;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  background-color: #f9fafc;
  display: flex; align-items: center; justify-content: center;
}
.placeholder-content { text-align: center; color: #909399; }
.icon-lg { font-size: 48px; margin-bottom: 15px; color: #dcdfe6; }
.main-text { font-size: 14px; font-weight: 500; margin-bottom: 5px; color: #606266; }
.sub-text { font-size: 12px; color: #C0C4CC; }

.font-medium { font-weight: 500; }
</style>