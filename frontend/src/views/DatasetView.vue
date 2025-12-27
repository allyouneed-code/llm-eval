<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  UploadFilled, View, Download, Delete, 
  Search, Medal, User, Filter, Document, Loading 
} from '@element-plus/icons-vue'

// 1. 引入 Composables & API
import { useDatasetList } from '@/composables/useDataset'
import { getSavedDatasetPreview, getDownloadUrl } from '@/api/dataset'

// 2. 引入子组件
import CategorySidebar from './components/dataset/CategorySidebar.vue'
import DatasetImportDialog from './components/dataset/DatasetImportDialog.vue'
import KnowledgePopover from './components/dataset/KnowledgePopover.vue'

// 3. 逻辑 Hooks
const { 
  tableData, totalItems, loading, categoryStats, 
  filter, fetchData, fetchStats, handleDelete, parseConfigInfo 
} = useDatasetList()

// 4. UI 状态
const importDialogVisible = ref(false)
// 数据预览 (Rows Preview)
const dataPreviewVisible = ref(false)
const dataPreviewContent = ref({ columns: [], rows: [] })
const dataPreviewLoading = ref(false)
// 详情抽屉 (Meta/Config Detail)
const detailDrawerVisible = ref(false)
const currentDataset = ref(null)

// ==========================================
// 交互逻辑
// ==========================================

const handleSearch = () => {
  filter.value.page = 1
  // keyword 变化触发 watch 自动加载
}

const handleRefresh = () => {
  fetchStats()
  fetchData()
}

// 打开详情抽屉
const handleShowDetail = (row) => {
  currentDataset.value = row
  detailDrawerVisible.value = true
}

// 预览数据内容 (Top 5 rows)
const handleViewData = async (row) => {
  dataPreviewVisible.value = true
  dataPreviewLoading.value = true
  dataPreviewContent.value = { columns: [], rows: [] }
  try {
    const data = await getSavedDatasetPreview(row.id)
    dataPreviewContent.value = data
  } catch (error) {
    ElMessage.error('无法读取数据预览')
  } finally {
    dataPreviewLoading.value = false
  }
}

const handleDownload = (row) => {
  window.open(getDownloadUrl(row.id), '_blank')
}
</script>

<template>
  <div class="dataset-view">
    <el-container class="full-height">
      <CategorySidebar 
        :stats="categoryStats" 
        v-model:active="filter.category" 
      />
      
      <el-main class="main-content">
        
        <div class="toolbar">
          <div class="toolbar-left">
            <h2 class="page-title">{{ filter.category === 'All' ? '所有数据集' : filter.category }}</h2>
            <el-tag type="info" round class="count-tag">{{ totalItems }} items</el-tag>
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
              class="search-input"
              @change="handleSearch"
            />
            
            <el-button type="primary" @click="importDialogVisible = true">
              <el-icon class="mr-1"><UploadFilled /></el-icon> 导入数据集
            </el-button>
          </div>
        </div>

        <div class="table-wrapper">
          <el-table :data="tableData" v-loading="loading" border stripe height="100%" style="width: 100%">
             <el-table-column prop="id" label="ID" width="60" align="center" sortable />
  
              <el-table-column label="名称" min-width="180" show-overflow-tooltip>
                <template #default="scope">
                  <span class="dataset-name" @click="handleShowDetail(scope.row)">
                    {{ scope.row.name }}
                  </span>
                </template>
              </el-table-column>
    
              <el-table-column label="来源" width="100" align="center">
                <template #default="scope">
                  <div v-if="scope.row.is_system" class="source-badge official"><el-icon><Medal /></el-icon> 官方</div>
                  <div v-else class="source-badge private"><el-icon><User /></el-icon> 私有</div>
                </template>
              </el-table-column>
    
              <el-table-column label="包含配置 (Configs)" min-width="240">
                <template #default="scope">
                  <div class="config-tags">
                    <el-tag 
                      v-for="cfg in scope.row.configs.slice(0, 2)"
                      :key="cfg.id"
                      :type="cfg.mode === 'gen' ? 'warning' : 'info'"
                      size="small"
                      effect="plain"
                      class="config-tag-item"
                    >
                      <b>{{ cfg.mode.toUpperCase() }}</b>
                      <span class="sep">|</span>
                      <span>{{ cfg.display_metric }}</span>
                    </el-tag>
                    
                    <el-tooltip 
                      v-if="scope.row.configs.length > 2" 
                      :content="`还有 ${scope.row.configs.length - 2} 个配置，点击查看详情`"
                      placement="top"
                    >
                      <el-tag type="info" size="small" effect="light" class="more-tag" @click="handleShowDetail(scope.row)">
                        +{{ scope.row.configs.length - 2 }}
                      </el-tag>
                    </el-tooltip>

                    <span v-if="!scope.row.configs?.length" class="empty-text">暂无配置</span>
                  </div>
                </template>
              </el-table-column>
    
              <el-table-column prop="category" label="能力" width="120" align="center">
                <template #default="scope">
                  <el-tag effect="light" type="success" round>{{ scope.row.category }}</el-tag>
                </template>
              </el-table-column>
              
              <el-table-column label="操作" width="160" align="center" fixed="right">
                <template #default="scope">
                  <el-button-group>
                    <el-button size="small" :icon="Document" @click="handleShowDetail(scope.row)" title="详情" />
                    
                    <template v-if="!scope.row.is_system">
                      <el-button size="small" :icon="View" @click="handleViewData(scope.row)" title="预览数据" />
                      <el-button size="small" :icon="Download" @click="handleDownload(scope.row)" title="下载" />
                      <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(scope.row)" title="删除" />
                    </template>
                  </el-button-group>
                </template>
              </el-table-column>
          </el-table>
        </div>

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

    <el-dialog v-model="dataPreviewVisible" title="源文件数据预览 (Top 5 Rows)" width="700px">
      <div v-if="dataPreviewLoading" class="loading-wrapper">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon> Loading...
      </div>
      <div v-else>
        <el-table :data="dataPreviewContent.rows" border stripe height="300" style="width: 100%">
          <el-table-column v-for="col in dataPreviewContent.columns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>

    <el-drawer
      v-model="detailDrawerVisible"
      title="数据集详情"
      direction="rtl"
      size="500px"
    >
      <div v-if="currentDataset" class="detail-content">
        <div class="detail-header">
           <h3>{{ currentDataset.name }}</h3>
           <el-tag>{{ currentDataset.category }}</el-tag>
        </div>
        <p class="desc">{{ currentDataset.description || '暂无描述' }}</p>

        <el-divider content-position="left">配置列表 (Configs)</el-divider>
        
        <div class="config-list">
          <div v-for="cfg in currentDataset.configs" :key="cfg.id" class="config-card">
             <div class="cfg-header">
                <span class="cfg-name">{{ cfg.config_name }}</span>
                <el-tag size="small" effect="dark" :type="cfg.mode === 'gen' ? 'warning' : 'info'">{{ cfg.mode }}</el-tag>
             </div>
             
             <div class="cfg-body">
                <div class="kv-row">
                  <span class="k">Metric:</span>
                  <span class="v">{{ cfg.display_metric }}</span>
                </div>
                <div class="kv-row">
                  <span class="k">Evaluator:</span>
                  <span class="v code">{{ parseConfigInfo(cfg).evaluator }}</span>
                </div>
                <div class="kv-row" v-if="cfg.reader_cfg">
                  <span class="k">Input Cols:</span>
                  <span class="v code">{{ JSON.parse(cfg.reader_cfg).input_columns?.join(', ') }}</span>
                </div>
                 <div class="kv-row" v-if="cfg.reader_cfg">
                  <span class="k">Output Col:</span>
                  <span class="v code">{{ JSON.parse(cfg.reader_cfg).output_column }}</span>
                </div>
             </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.dataset-view { height: 100%; background: #fff; }
.full-height { height: 100%; }
.main-content { 
  display: flex; flex-direction: column; padding: 20px; height: 100%; overflow: hidden; 
}

/* Toolbar */
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-shrink: 0; }
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.page-title { margin: 0; font-size: 20px; color: #303133; }
.count-tag { font-weight: normal; }

.toolbar-right { display: flex; align-items: center; gap: 15px; }
.filter-box { 
  display: flex; align-items: center; background: #f4f4f5; padding: 4px 12px; 
  border-radius: 20px; border: 1px solid transparent; transition: all 0.3s; 
}
.filter-box:hover { background: #ebeef5; }
.filter-box.active { background: #f2ebfb; border-color: #d6bbf5; }
.filter-label { font-size: 13px; color: #606266; margin-right: 10px; cursor: pointer; display: flex; align-items: center; }
.filter-box.active .filter-label { color: #8e44ad; font-weight: bold; }
.search-input { width: 200px; }

/* Table Area */
.table-wrapper { flex: 1; overflow: hidden; /* 触发 el-table 的 height="100%" */ }
.dataset-name { font-weight: 600; color: #303133; cursor: pointer; transition: color 0.2s; }
.dataset-name:hover { color: #409eff; text-decoration: underline; }

.source-badge { display: flex; align-items: center; justify-content: center; gap: 4px; padding: 2px 8px; border-radius: 4px; font-size: 12px; width: fit-content; margin: 0 auto; }
.source-badge.official { background: #ecf5ff; color: #409eff; }
.source-badge.private { background: #f3e5f5; color: #7b1fa2; }

/* Config Tags */
.config-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.config-tag-item { display: flex; align-items: center; }
.config-tag-item .sep { margin: 0 4px; opacity: 0.5; }
.more-tag { cursor: pointer; }
.empty-text { color: #c0c4cc; font-size: 12px; }

/* Pagination */
.pagination-container { margin-top: 15px; display: flex; justify-content: flex-end; flex-shrink: 0; }

/* Drawer Styles */
.detail-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.detail-header h3 { margin: 0; font-size: 18px; }
.desc { color: #606266; font-size: 14px; margin-bottom: 20px; line-height: 1.5; }

.config-list { display: flex; flex-direction: column; gap: 12px; }
.config-card { border: 1px solid #ebeef5; border-radius: 6px; padding: 12px; background: #fafafa; }
.cfg-header { display: flex; justify-content: space-between; margin-bottom: 8px; font-weight: bold; font-size: 14px; }
.cfg-name { color: #303133; }
.cfg-body { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.kv-row { display: flex; justify-content: space-between; }
.k { color: #909399; }
.v { color: #606266; font-weight: 500; }
.v.code { font-family: monospace; background: #fff; padding: 0 4px; border-radius: 3px; border: 1px solid #eee; color: #d63384; }

.mr-1 { margin-right: 4px; }
.loading-wrapper { text-align: center; padding: 40px; }
</style>