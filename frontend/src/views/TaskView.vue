<script setup>
import { ref } from 'vue'
import { VideoPlay, Refresh, Delete, DataLine, Cpu, ArrowRight, CollectionTag } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskData } from '@/composables/useTask'
import { getCapColor } from '@/utils/style'
import { deleteTask } from '@/api/task'

// 引入子组件
import TaskStatusTag from './components/task/TaskStatusTag.vue'
import TaskCreateDialog from './components/task/TaskCreateDialog.vue'
import TaskDetailDrawer from './components/task/TaskDetailDrawer.vue'

// 使用 Composable
const { 
  taskList, modelList, datasetList, fetchTasks, fetchBasicData,
  pagination, handlePageChange, handleSizeChange 
} = useTaskData()

// UI 状态
const createDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
// 🌟 修改：改用 ID 和 初始数据 的组合，以支持详情页的独立刷新
const currentTaskId = ref(null) 
const currentTaskInitial = ref(null)

// 辅助函数：获取模型名称
const getModelName = (id) => {
  const found = modelList.value.find(m => m.id === id)
  return found ? found.name : `Model-${id}`
}

// 辅助函数：解析数据集配置用于展示
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

// 打开详情/报告
const handleViewDetail = (row) => {
  currentTaskId.value = row.id          // 传递 ID 给 Drawer 以便轮询
  currentTaskInitial.value = row        // 传递当前行数据作为初始展示
  detailDrawerVisible.value = true
}

// 删除任务
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务 #${row.id} 吗？\n删除后相关的评测结果也将一并清除，此操作无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        icon: Delete,
        draggable: true
      }
    )
    
    await deleteTask(row.id)
    ElMessage.success('任务删除成功')
    fetchTasks()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

// 刷新列表
const handleRefresh = () => {
  fetchTasks()
  fetchBasicData()
}
</script>

<template>
  <div class="task-view-container">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">评测任务管理</h2>
        <span class="page-subtitle">管理模型评测任务及其运行状态</span>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" circle @click="handleRefresh" class="action-btn" title="刷新列表" />
        <el-button type="primary" size="large" @click="createDialogVisible = true" class="create-btn">
          <el-icon class="mr-2"><VideoPlay /></el-icon> 新建任务
        </el-button>
      </div>
    </div>

    <div class="table-card">
      <el-table 
        :data="taskList" 
        style="width: 100%" 
        :header-cell-style="{ background: '#f8fafc', color: '#475569', fontWeight: '600' }"
        :row-class-name="'custom-row'"
      >
        <el-table-column prop="id" label="ID" width="80" align="center">
          <template #default="scope">
            <span class="id-badge">#{{ scope.row.id }}</span>
          </template>
        </el-table-column>
        
        <el-table-column label="模型" min-width="150">
          <template #default="scope">
            <div class="model-info">
              <el-icon class="model-icon"><Cpu /></el-icon>
              <span class="model-name">{{ getModelName(scope.row.model_id) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="评测方案" min-width="160">
          <template #default="scope">
            <div v-if="scope.row.scheme_name" class="scheme-tag">
              <el-icon><CollectionTag /></el-icon>
              <span>{{ scope.row.scheme_name }}</span>
            </div>
            <div v-else-if="scope.row.scheme_id" class="scheme-missing">
               <el-tooltip content="原方案可能已被删除" placement="top">
                 <span>未知方案 (ID:{{ scope.row.scheme_id }})</span>
               </el-tooltip>
            </div>
            <div v-else class="scheme-none">-</div>
          </template>
        </el-table-column>
        
        <el-table-column label="包含数据集" min-width="340">
          <template #default="scope">
            <div class="content-container">
              <div v-for="(items, cap) in getTaskDatasetDisplay(scope.row)" :key="cap" class="cap-group">
                <div class="cap-label" :style="{ color: getCapColor(cap), borderColor: getCapColor(cap) + '30' }">
                  {{ cap }}
                </div>
                <div class="tag-wrap">
                  <el-tag 
                    v-for="(item, idx) in items" 
                    :key="idx" 
                    :type="item.mode === 'gen' ? 'warning' : 'info'" 
                    size="small" 
                    effect="plain"
                    class="ds-tag"
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
            <div class="progress-wrap">
              <el-progress 
                :percentage="scope.row.progress" 
                :status="scope.row.status === 'failed' ? 'exception' : (scope.row.status === 'success' ? 'success' : '')" 
                :stroke-width="8"
                :show-text="false"
              />
              <span class="progress-text">{{ scope.row.progress }}%</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="创建时间" width="160" prop="created_at" align="center">
          <template #default="scope">
            <div class="time-col">
              <span class="date">{{ new Date(scope.row.created_at).toLocaleDateString() }}</span>
              <span class="time">{{ new Date(scope.row.created_at).toLocaleTimeString() }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="scope">
            <div class="action-buttons">
              <el-button 
                type="primary" 
                link 
                class="btn-detail"
                @click="handleViewDetail(scope.row)"
              >
                <el-icon class="mr-1"><component :is="scope.row.status === 'success' ? 'DataLine' : 'ArrowRight'" /></el-icon>
                {{ scope.row.status === 'success' ? '报告' : '详情' }}
              </el-button>

              <div class="divider-vertical"></div>

              <el-button 
                type="danger" 
                link 
                class="btn-delete"
                @click="handleDelete(scope.row)"
              >
                <el-icon class="mr-1"><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
          background
        />
      </div>
    </div>

    <TaskCreateDialog 
      v-model:visible="createDialogVisible"
      :models="modelList"
      :datasets="datasetList"
      @success="fetchTasks"
    />

    <TaskDetailDrawer 
      v-model:visible="detailDrawerVisible"
      :task-id="currentTaskId"
      :initial-task="currentTaskInitial"
    />
  </div>
</template>

<style scoped>
/* 容器样式 */
.task-view-container {
  padding: 24px;
  background-color: #f1f5f9;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 顶部 Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.header-left .page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
}
.header-left .page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin-top: 4px;
  display: block;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.create-btn {
  box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.2);
}

/* 表格卡片 */
.table-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 8px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.06);
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* ID Badge */
.id-badge {
  background: #f1f5f9;
  color: #64748b;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}

/* 模型信息 */
.model-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.model-icon {
  background: #eff6ff;
  color: #3b82f6;
  padding: 6px;
  border-radius: 6px;
  font-size: 16px;
}
.model-name {
  font-weight: 600;
  color: #334155;
  font-size: 14px;
}

/* 方案标签 */
.scheme-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background-color: #ecfdf5; /* 浅绿色背景 */
  color: #059669; /* 深绿色文字 */
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}
.scheme-missing {
  color: #94a3b8;
  font-size: 12px;
  font-style: italic;
}
.scheme-none {
  color: #cbd5e1;
}

/* 评测配置 */
.content-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}
.cap-group {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.cap-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  background: #fafafa;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #eee;
  white-space: nowrap;
  min-width: 80px;
  justify-content: center;
}
.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.ds-tag {
  border: none;
  background-color: #f8fafc;
  color: #475569;
}

/* 进度条 */
.progress-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-wrap .el-progress {
  flex: 1;
}
.progress-text {
  font-size: 12px;
  color: #94a3b8;
  width: 32px;
  text-align: right;
}

/* 时间 */
.time-col {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}
.time-col .date {
  color: #334155;
  font-size: 13px;
}
.time-col .time {
  color: #94a3b8;
  font-size: 12px;
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
}
.btn-detail {
  font-weight: 500;
  padding: 0 12px;
}
.btn-delete {
  color: #ef4444;
  padding: 0 12px;
}
.btn-delete:hover {
  color: #dc2626;
  background-color: #fef2f2;
  border-radius: 4px;
}
.divider-vertical {
  width: 1px;
  height: 14px;
  background-color: #cbd5e1;
  margin: 0 4px;
}

/* 自定义表格行 hover 效果 */
:deep(.el-table__row:hover) > td {
  background-color: #f8fafc !important;
}

.pagination-container {
  padding: 16px 8px;
  display: flex;
  justify-content: flex-end;
}
</style>