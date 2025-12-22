<script setup>
import { ref } from 'vue'
import { VideoPlay, Refresh } from '@element-plus/icons-vue'
import { useTaskData } from '@/composables/useTask'
import { getCapColor, getCapIcon } from '@/utils/style'

// 引入子组件
import TaskStatusTag from './components/task/TaskStatusTag.vue'
import TaskCreateDialog from './components/task/TaskCreateDialog.vue'
import TaskDetailDrawer from './components/task/TaskDetailDrawer.vue'

// 使用 Composable
const { taskList, modelList, datasetList, fetchTasks, fetchBasicData } = useTaskData()

// UI 状态
const createDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const currentTask = ref(null)

// 辅助函数：列表页仍需使用 (因为 Table 渲染需要)
const getModelName = (id) => {
  const found = modelList.value.find(m => m.id === id)
  return found ? found.name : `Model-${id}`
}

const getTaskDatasetDisplay = (taskRow) => {
  let configIds = []
  try { configIds = JSON.parse(taskRow.datasets_list) } catch { return [] }
  if (!configIds.length) return []
  
  const displayItems = []
  configIds.forEach(cid => {
    for (const meta of datasetList.value) {
      const foundCfg = meta.configs.find(c => c.id === cid)
      if (foundCfg) {
        displayItems.push({
          cap: meta.category,
          label: `${meta.name} (${foundCfg.mode})`,
          mode: foundCfg.mode
        })
        break
      }
    }
  })
  
  const grouped = {}
  displayItems.forEach(item => {
    if (!grouped[item.cap]) grouped[item.cap] = []
    grouped[item.cap].push(item)
  })
  return grouped
}

const handleViewDetail = (row) => {
  currentTask.value = row
  detailDrawerVisible.value = true
}

const handleRefresh = () => {
  fetchTasks()
  fetchBasicData()
}
</script>

<template>
  <div class="task-view">
    <div class="header-actions">
      <el-button type="primary" size="large" @click="createDialogVisible = true" class="create-btn">
        <el-icon class="mr-1"><VideoPlay /></el-icon> 新建评测任务
      </el-button>
      <el-button :icon="Refresh" circle @click="handleRefresh" />
    </div>

    <el-table :data="taskList" border style="width: 100%" stripe highlight-current-row class="main-table">
      <el-table-column prop="id" label="ID" width="70" align="center" sortable />
      
      <el-table-column label="模型 (Model)" min-width="140">
        <template #default="scope">
          <div style="font-weight:600">{{ getModelName(scope.row.model_id) }}</div>
        </template>
      </el-table-column>
      
      <el-table-column label="评测配置 (Content)" min-width="320">
        <template #default="scope">
          <div class="content-container">
            <div v-for="(items, cap) in getTaskDatasetDisplay(scope.row)" :key="cap" class="cap-row">
              <div class="cap-header" :style="{ color: getCapColor(cap) }">
                <el-icon class="cap-icon"><component :is="getCapIcon(cap)" /></el-icon>
                <span class="cap-name">{{ cap }}</span>
              </div>
              <div class="ds-list">
                <el-tag 
                  v-for="(item, idx) in items" 
                  :key="idx" 
                  :type="item.mode === 'gen' ? 'warning' : 'info'" 
                  size="small" 
                  effect="light"
                  class="ds-pill"
                >
                  {{ item.label }}
                </el-tag>
              </div>
            </div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column label="状态" width="100" align="center">
        <template #default="scope">
          <TaskStatusTag :status="scope.row.status" />
        </template>
      </el-table-column>
      
      <el-table-column label="进度" width="140">
        <template #default="scope">
          <el-progress 
            :percentage="scope.row.progress" 
            :status="scope.row.status === 'failed' ? 'exception' : ''" 
            :stroke-width="8" 
          />
        </template>
      </el-table-column>
      
      <el-table-column label="创建时间" width="160" sortable prop="created_at">
        <template #default="scope">
          <span class="time-text">{{ new Date(scope.row.created_at).toLocaleString() }}</span>
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="100" fixed="right" align="center">
        <template #default="scope">
          <el-button type="primary" link @click="handleViewDetail(scope.row)">
            {{ scope.row.status === 'success' ? '报告' : '详情' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <TaskCreateDialog 
      v-model:visible="createDialogVisible"
      :models="modelList"
      :datasets="datasetList"
      @success="fetchTasks"
    />

    <TaskDetailDrawer 
      v-model:visible="detailDrawerVisible"
      :task="currentTask"
      :model-name="currentTask ? getModelName(currentTask.model_id) : ''"
    />
  </div>
</template>

<style scoped>
.task-view { background: #fff; padding: 20px; height: 100%; display: flex; flex-direction: column; }
.header-actions { display: flex; justify-content: space-between; margin-bottom: 20px; }
.content-container { display: flex; flex-direction: column; gap: 6px; }
.cap-row { display: flex; align-items: flex-start; }
.cap-header { display: flex; align-items: center; gap: 4px; width: 120px; flex-shrink: 0; font-weight: bold; font-size: 13px; justify-content: flex-end; padding-right: 12px; border-right: 2px solid #eee; margin-right: 12px; height: 24px; }
.ds-list { display: flex; flex-wrap: wrap; gap: 4px; }
.time-text { font-size: 12px; color: #606266; }
</style>