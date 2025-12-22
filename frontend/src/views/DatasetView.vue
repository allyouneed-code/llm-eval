<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  UploadFilled, View, Download, Delete, 
  Search, Medal, User, Filter, Cpu, Loading 
} from '@element-plus/icons-vue'

// 1. 引入 Composables
import { useDatasetList } from '@/composables/useDataset'
import { getSavedDatasetPreview, getDownloadUrl } from '@/api/dataset'

// 2. 引入子组件
import CategorySidebar from './components/dataset/CategorySidebar.vue'
import DatasetImportDialog from './components/dataset/DatasetImportDialog.vue'
import KnowledgePopover from './components/dataset/KnowledgePopover.vue'

// 使用逻辑 Hooks
const { 
  tableData, totalItems, loading, categoryStats, 
  filter, fetchData, fetchStats, handleDelete, parseConfigInfo 
} = useDatasetList()

// UI 状态
const importDialogVisible = ref(false)
const savedDataVisible = ref(false)
const savedPreviewData = ref({ columns: [], rows: [] })
const savedDataLoading = ref(false)

// 交互逻辑
const handleSearch = () => {
  filter.value.page = 1
  // keyword 变化会触发 watch，自动 fetchData
}

const handleRefresh = () => {
  fetchStats()
  fetchData()
}

// 预览已保存数据 (这部分逻辑较轻，留在 View 层即可)
const handleViewData = async (row) => {
  savedDataVisible.value = true
  savedDataLoading.value = true
  savedPreviewData.value = { columns: [], rows: [] }
  try {
    const data = await getSavedDatasetPreview(row.id)
    savedPreviewData.value = data
  } catch (error) {
    ElMessage.error('无法读取数据预览')
  } finally {
    savedDataLoading.value = false
  }
}

const handleDownload = (row) => {
  window.open(getDownloadUrl(row.id), '_blank')
}
</script>

<template>
  <div class="dataset-view">
    <el-container style="height: calc(100vh - 80px);">
      <CategorySidebar 
        :stats="categoryStats" 
        v-model:active="filter.category" 
      />
      
      <el-main class="main-content">
        <div class="toolbar">
          <div class="toolbar-left">
            <h2 class="page-title">{{ filter.category === 'All' ? '所有数据集' : filter.category }}</h2>
            <el-tag type="info" round style="margin-left: 10px">{{ totalItems }} items</el-tag>
            <KnowledgePopover />
          </div>
          
          <div class="toolbar-right">
             <div class="filter-box" :class="{ active: filter.privateOnly }">
              <span class="filter-label" @click="filter.privateOnly = !filter.privateOnly">
                <el-icon class="mr-1"><Filter /></el-icon> 只看私有
              </span>
              <el-switch v-model="filter.privateOnly" style="--el-switch-on-color: #9b59b6;" />
            </div>

            <el-input 
              v-model="filter.keyword" 
              placeholder="搜索名称..." 
              :prefix-icon="Search"
              clearable
              style="width: 200px; margin-right: 15px;"
              @change="handleSearch"
            />
            
            <el-button type="primary" @click="importDialogVisible = true">
              <el-icon style="margin-right: 5px"><UploadFilled /></el-icon> 导入数据集
            </el-button>
          </div>
        </div>

        <el-table :data="tableData" v-loading="loading" border style="width: 100%" stripe>
           <el-table-column prop="id" label="ID" width="60" align="center" sortable />

            <el-table-column label="名称" min-width="160" show-overflow-tooltip>
              <template #default="scope">
                <span style="font-weight: 600; color: #303133;">{{ scope.row.name }}</span>
              </template>
            </el-table-column>
  
            <el-table-column label="来源" width="110" align="center">
              <template #default="scope">
                <div v-if="scope.row.is_system" class="source-badge official"><el-icon><Medal /></el-icon> 官方</div>
                <div v-else class="source-badge private"><el-icon><User /></el-icon> 私有</div>
              </template>
            </el-table-column>
  
            <el-table-column label="包含配置 (Config Details)" min-width="260">
              <template #default="scope">
                <div class="config-tags">
                  <el-popover
                    v-for="cfg in scope.row.configs"
                    :key="cfg.id"
                    placement="top"
                    :width="260" 
                    trigger="hover"
                    popper-class="custom-popover"
                  >
                    <template #reference>
                      <el-tag 
                        :type="cfg.mode === 'gen' ? 'warning' : 'info'"
                        size="small"
                        effect="plain"
                        class="mr-1 config-tag-item"
                      >
                        <span style="font-weight: bold;">{{ cfg.mode.toUpperCase() }}</span>
                        <span style="margin: 0 4px; color: #ccc;">|</span>
                        <span>{{ cfg.display_metric }}</span>
                        <el-icon v-if="parseConfigInfo(cfg).isLLM" style="margin-left: 4px; color: #9b59b6;"><Cpu /></el-icon>
                      </el-tag>
                    </template>
                    
                    <div class="popover-wrapper">
                      <div class="pop-header">
                         <span class="pop-title" :title="cfg.config_name">{{ cfg.config_name }}</span>
                         <el-tag size="small" :type="cfg.mode === 'gen' ? 'warning' : 'info'" effect="dark">{{ cfg.mode.toUpperCase() }}</el-tag>
                      </div>
                      <div class="pop-divider"></div>
                      <div class="pop-body">
                         <div class="pop-row">
                            <span class="label">Evaluator</span>
                            <span class="value code-box">{{ parseConfigInfo(cfg).evaluator }}</span>
                         </div>
                         <div class="pop-row">
                            <span class="label">Metric</span>
                            <span class="value">{{ cfg.display_metric }}</span>
                         </div>
                         <div class="pop-row">
                            <span class="label">Prompt Ver</span>
                            <span class="value">{{ cfg.prompt_version || 'Default' }}</span>
                         </div>
                      </div>
                    </div>
                  </el-popover>
                  <span v-if="!scope.row.configs?.length" style="color:#999; font-size:12px">暂无配置</span>
                </div>
              </template>
            </el-table-column>
  
            <el-table-column prop="category" label="能力" width="130" align="center">
              <template #default="scope">
                <el-tag effect="light" type="success">{{ scope.row.category }}</el-tag>
              </template>
            </el-table-column>
  
            <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
            
            <el-table-column label="操作" width="180" align="center" fixed="right">
              <template #default="scope">
                <el-button-group>
                  <el-button size="small" :icon="View" @click="handleViewData(scope.row)" title="预览" />
                  <el-button size="small" :icon="Download" @click="handleDownload(scope.row)" title="下载" />
                  <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(scope.row)" :disabled="scope.row.is_system" title="删除" />
                </el-button-group>
              </template>
            </el-table-column>
        </el-table>

        <div class="pagination-container">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="totalItems"
            v-model:page-size="filter.pageSize"
            v-model:current-page="filter.page"
          />
        </div>
      </el-main>
    </el-container>
    
    <DatasetImportDialog 
      v-model:visible="importDialogVisible" 
      @success="handleRefresh" 
    />

    <el-dialog v-model="savedDataVisible" title="数据预览" width="700px">
      <div v-if="savedDataLoading" style="text-align: center; padding: 20px;">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon> Loading...
      </div>
      <div v-else>
        <el-table :data="savedPreviewData.rows" border stripe height="300" style="width: 100%">
          <el-table-column v-for="col in savedPreviewData.columns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 保持原有样式 */
.dataset-view { background: #fff; height: 100%; }
.main-content { padding: 20px; display: flex; flex-direction: column; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.toolbar-left { display: flex; align-items: center; }
.page-title { margin: 0; font-size: 20px; color: #303133; }
.toolbar-right { display: flex; align-items: center; }
.filter-box { display: flex; align-items: center; background: #f4f4f5; padding: 6px 12px; border-radius: 20px; margin-right: 20px; transition: all 0.3s; border: 1px solid transparent; }
.filter-box:hover { background: #ebeef5; }
.filter-box.active { background: #f2ebfb; border-color: #d6bbf5; }
.filter-label { font-size: 13px; color: #606266; margin-right: 10px; cursor: pointer; display: flex; align-items: center; }
.filter-box.active .filter-label { color: #8e44ad; font-weight: bold; }
.mr-1 { margin-right: 4px; }
.source-badge { display: flex; align-items: center; justify-content: center; gap: 4px; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; width: fit-content; margin: 0 auto; }
.source-badge.official { background-color: #ecf5ff; color: #409eff; border: 1px solid #c6e2ff; }
.source-badge.private { background-color: #f3e5f5; color: #7b1fa2; border: 1px solid #e1bee7; }
.config-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.config-tag-item { cursor: pointer; display: flex; align-items: center; }

/* Popover 内部样式 */
.popover-wrapper { padding: 4px; }
.pop-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pop-title { font-weight: 700; color: #303133; font-size: 14px; max-width: 160px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.pop-divider { height: 1px; background: #eee; margin: 8px 0; }
.pop-body { display: flex; flex-direction: column; gap: 8px; }
.pop-row { display: flex; align-items: center; justify-content: space-between; font-size: 13px; }
.pop-row .label { color: #909399; }
.pop-row .value { color: #606266; font-weight: 500; }
.code-box { font-family: monospace; background: #f0f2f5; padding: 2px 6px; border-radius: 4px; color: #d63384; font-size: 12px; }
.pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
</style>