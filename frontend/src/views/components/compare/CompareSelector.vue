<template>
  <div class="selector-container">
    <el-card class="box-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon class="header-icon"><DataAnalysis /></el-icon>
            <span class="title">发起新对比</span>
          </div>
          <el-tag type="info" effect="plain" round>多模型评测分析</el-tag>
        </div>
      </template>

      <div class="steps-wrapper">
        <el-steps :active="currentStep" finish-status="success" align-center>
          <el-step title="选择方案" description="确定评测基准" />
          <el-step title="选择任务" description="挑选对比模型" />
          <el-step title="生成报告" description="查看多维分析" />
        </el-steps>
      </div>

      <div class="form-content" v-loading="loading">
        <div class="step-section" :class="{ 'is-active': currentStep === 1 }">
          <h3 class="step-title">1. 选择评测方案</h3>
          <el-select 
            v-model="selectedSchemeId" 
            placeholder="请选择一个评测方案..." 
            size="large"
            class="scheme-select"
            @change="handleSchemeChange"
          >
            <el-option v-for="s in schemes" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>

        <transition name="el-fade-in-linear">
          <div class="step-section" v-if="selectedSchemeId" :class="{ 'is-active': currentStep === 2 }">
            <h3 class="step-title">
              2. 勾选需要对比的任务 
              <span class="sub-title">(至少 2 个，第一个默认为基准)</span>
            </h3>
            
            <div class="table-wrapper">
              <el-table 
                :data="filteredTasks" 
                stripe
                highlight-current-row
                @selection-change="handleSelectionChange"
                max-height="450"
                :row-key="row => row.id"
                header-cell-class-name="table-header"
              >
                <el-table-column type="selection" width="55" align="center" />
                <el-table-column label="模型" min-width="180">
                  <template #default="{row}">
                    <div class="model-cell">
                      <el-icon><Cpu /></el-icon>
                      <span class="model-name">Model-{{ row.model_id }}</span>
                      <el-tag v-if="row.id === firstSelectedId" size="small" effect="dark" class="base-tag">BASE</el-tag>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="创建时间" prop="created_at" width="180" align="center">
                   <template #default="{row}">{{ new Date(row.created_at).toLocaleString() }}</template>
                </el-table-column>
                <el-table-column label="状态" width="100" align="center">
                  <template #default="{row}">
                      <el-tag type="success" effect="light" round v-if="row.status==='success'">完成</el-tag>
                      <el-tag v-else effect="plain">{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div class="action-bar">
              <div class="selection-info">
                <template v-if="selectedTaskIds.length >= 2">
                  <el-icon color="#67C23A" size="18"><CircleCheckFilled /></el-icon>
                  <span class="valid-text">已选择 <b>{{ selectedTaskIds.length }}</b> 个任务，准备就绪</span>
                </template>
                <template v-else>
                  <span class="invalid-text">已选择 <b>{{ selectedTaskIds.length }}</b> 个 (需至少 2 个)</span>
                </template>
              </div>
              
              <el-button 
                type="primary" 
                size="large" 
                :disabled="selectedTaskIds.length < 2" 
                @click="handleSubmit"
                class="submit-btn"
              >
                开始对比分析 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
              </el-button>
            </div>
          </div>
        </transition>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getTasks } from '@/api/task'
import { getSchemes } from '@/api/scheme'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Cpu, CircleCheckFilled, ArrowRight } from '@element-plus/icons-vue'

const emit = defineEmits(['submit'])

const loading = ref(false)
const schemes = ref([])
const allTasks = ref([])
const selectedSchemeId = ref(null)
const selectedTaskIds = ref([])

const currentStep = computed(() => {
  if (!selectedSchemeId.value) return 1
  if (selectedTaskIds.value.length < 2) return 2
  return 3 // Ready
})

const filteredTasks = computed(() => {
  if (!selectedSchemeId.value) return []
  return allTasks.value.filter(t => t.scheme_id === selectedSchemeId.value)
})

const firstSelectedId = computed(() => selectedTaskIds.value[0])

const loadData = async () => {
  loading.value = true
  try {
    const [sRes, tRes] = await Promise.all([
      getSchemes(),
      getTasks({ page_size: 1000 })
    ])
    schemes.value = Array.isArray(sRes) ? sRes : (sRes.items || sRes.data || [])
    const tItems = Array.isArray(tRes) ? tRes : (tRes.items || tRes.data || [])
    allTasks.value = tItems.filter(t => t.status === 'success')
  } catch (e) {
    ElMessage.error("加载基础数据失败")
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

const handleSchemeChange = () => { selectedTaskIds.value = [] }
const handleSelectionChange = (rows) => { selectedTaskIds.value = rows.map(r => r.id) }
const handleSubmit = () => { emit('submit', selectedTaskIds.value) }
</script>

<style scoped>
.selector-container {
  max-width: 900px;
  margin: 40px auto;
}

.box-card {
  border-radius: 12px;
  border: 1px solid #ebeef5;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.header-icon {
  font-size: 22px;
  color: #409EFF;
}

.steps-wrapper {
  margin: 30px 0 40px;
  padding: 0 40px;
}

.form-content {
  padding: 0 20px 20px;
}

.step-section {
  margin-bottom: 30px;
}

.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 15px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.sub-title {
  font-size: 13px;
  color: #909399;
  font-weight: normal;
}

.scheme-select {
  width: 100%;
  max-width: 500px;
}

.table-wrapper {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.model-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.base-tag {
  transform: scale(0.85);
  margin-left: auto;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px dashed #e4e7ed;
}

.selection-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.valid-text {
  color: #67C23A;
}

.invalid-text {
  color: #909399;
}

.submit-btn {
  font-weight: 600;
  padding-left: 30px;
  padding-right: 30px;
}

:deep(.table-header) {
  background-color: #f5f7fa !important;
  color: #606266;
  font-weight: 600;
}
</style>