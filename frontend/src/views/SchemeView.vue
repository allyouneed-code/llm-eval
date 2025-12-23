<script setup>
import { ref, computed, onMounted } from 'vue'
import { Plus, Delete, CollectionTag, Document, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSchemes, deleteScheme } from '@/api/scheme'
import { getDatasets } from '@/api/dataset'
import { getCapColor } from '@/utils/style' // 引入颜色工具(如果有的话，没有则使用默认色)
import SchemeCreateDialog from './components/scheme/SchemeCreateDialog.vue'

// ==========================
// 状态定义
// ==========================
const loading = ref(false)
const rawSchemes = ref([])
const configMap = ref({})
const showCreateDialog = ref(false)

// 详情抽屉状态
const drawerVisible = ref(false)
const currentScheme = ref(null)

// ==========================
// 核心逻辑
// ==========================

const fetchData = async () => {
  loading.value = true
  try {
    const [schemesRes, datasetsRes] = await Promise.all([
      getSchemes(),
      getDatasets({ page: 1, page_size: 500 })
    ])

    rawSchemes.value = schemesRes

    // 构建映射字典
    const map = {}
    datasetsRes.items.forEach(meta => {
      if (meta.configs) {
        meta.configs.forEach(cfg => {
          map[cfg.id] = {
            configId: cfg.id,
            datasetName: meta.name,
            category: meta.category,
            configName: cfg.config_name,
            mode: cfg.mode,
            metric: cfg.display_metric
          }
        })
      }
    })
    configMap.value = map

  } catch (e) {
    console.error("数据加载失败", e)
    ElMessage.error("列表加载失败")
  } finally {
    loading.value = false
  }
}

// 方案列表数据增强
const richSchemes = computed(() => {
  return rawSchemes.value.map(scheme => {
    const ids = scheme.dataset_config_ids || []
    const details = ids.map(id => configMap.value[id]).filter(Boolean)
    const categories = Array.from(new Set(details.map(d => d.category)))
    return {
      ...scheme,
      realCount: ids.length,
      details: details,
      categories: categories
    }
  })
})

// 🌟 新增：当前方案详情的分组数据 (用于抽屉展示)
const currentSchemeGrouped = computed(() => {
  if (!currentScheme.value || !currentScheme.value.details) return {}
  
  const groups = {}
  currentScheme.value.details.forEach(item => {
    if (!groups[item.category]) {
      groups[item.category] = []
    }
    groups[item.category].push(item)
  })
  return groups
})

// ==========================
// 交互操作
// ==========================

const openDetailDrawer = (scheme) => {
  currentScheme.value = scheme
  drawerVisible.value = true
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm(
      '删除方案不会删除原数据集，但会影响基于此方案创建任务的快捷引用。是否继续？', 
      '确认删除', 
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteScheme(id)
    ElMessage.success('删除成功')
    rawSchemes.value = rawSchemes.value.filter(s => s.id !== id)
  } catch (e) {
    // cancel
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="scheme-container">
    
    <div class="header-bar">
      <div class="title-group">
        <el-icon class="icon-logo"><CollectionTag /></el-icon>
        <div class="text-info">
          <h2 class="page-title">评测方案库</h2>
          <p class="sub-title">预设数据集组合，用于标准化模型能力评测</p>
        </div>
      </div>
      <el-button type="primary" size="large" @click="showCreateDialog = true" class="create-btn">
        <el-icon class="mr-2"><Plus /></el-icon> 新建评测方案
      </el-button>
    </div>

    <div class="card-grid" v-loading="loading">
      <div v-for="item in richSchemes" :key="item.id" class="custom-card" @click="openDetailDrawer(item)">
        <div class="card-header">
          <span class="scheme-name" :title="item.name">{{ item.name }}</span>
          <div class="actions" @click.stop>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(item.id)" />
          </div>
        </div>
        
        <div class="card-desc">
          {{ item.description || '暂无描述信息...' }}
        </div>
        
        <div class="card-stats">
          <div class="stat-item">
            <span class="num">{{ item.realCount }}</span>
            <span class="label">配置项</span>
          </div>
          <div class="divider"></div>
          <div class="stat-item">
            <span class="num">{{ item.categories.length }}</span>
            <span class="label">能力维度</span>
          </div>
        </div>

        <div class="card-tags">
          <el-tag 
            v-for="cat in item.categories.slice(0, 3)" 
            :key="cat" 
            size="small" 
            effect="plain"
            type="info"
            class="mr-1 mb-1"
          >
            {{ cat }}
          </el-tag>
          <span v-if="item.categories.length > 3" class="more-tag">...</span>
        </div>
      </div>

      <el-empty v-if="!loading && richSchemes.length === 0" description="暂无评测方案，点击右上角创建" />
    </div>

    <el-drawer
      v-model="drawerVisible"
      :title="currentScheme?.name"
      direction="rtl"
      size="500px"
      class="scheme-drawer"
    >
      <template #header>
         <div class="drawer-header-content">
           <span class="d-title">{{ currentScheme?.name }}</span>
           <el-tag size="small" type="success" effect="dark">ID: {{ currentScheme?.id }}</el-tag>
         </div>
      </template>

      <div v-if="currentScheme" class="drawer-content">
        <div class="desc-box">
          <el-icon><Document /></el-icon>
          <span class="text">{{ currentScheme.description || '此方案未设置描述信息' }}</span>
        </div>

        <el-divider content-position="left">
          配置详情 (共 {{ currentScheme.realCount }} 项)
        </el-divider>

        <div class="grouped-list">
          <div 
            v-for="(items, category) in currentSchemeGrouped" 
            :key="category" 
            class="category-group"
          >
            <div class="group-header">
              <span class="cat-point"></span>
              <span class="cat-name">{{ category }}</span>
              <span class="cat-count">({{ items.length }})</span>
            </div>

            <div class="group-items">
              <div v-for="cfg in items" :key="cfg.configId" class="item-row">
                <div class="row-main">
                  <div class="ds-name">{{ cfg.datasetName }}</div>
                  <div class="cfg-name">{{ cfg.configName }}</div>
                </div>
                <div class="row-meta">
                  <el-tag v-if="cfg.mode === 'gen'" type="warning" size="small" effect="plain">GEN</el-tag>
                  <el-tag v-else type="info" size="small" effect="plain">PPL</el-tag>
                  <span class="metric-val">{{ cfg.metric }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </el-drawer>

    <SchemeCreateDialog 
      v-model:visible="showCreateDialog" 
      @success="fetchData" 
    />
  </div>
</template>

<style scoped>
/* 保持之前的页面样式不变... */
.scheme-container { padding: 20px; background-color: #f8fafc; min-height: 100vh; }
.header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; background: #fff; padding: 15px 25px; border-radius: 8px; box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05); }
.title-group { display: flex; align-items: center; }
.icon-logo { font-size: 28px; color: #409EFF; margin-right: 15px; background: #ecf5ff; padding: 8px; border-radius: 8px; box-sizing: content-box; }
.page-title { margin: 0; font-size: 18px; color: #303133; font-weight: 600; }
.sub-title { margin: 4px 0 0 0; font-size: 12px; color: #909399; }
.create-btn { padding: 10px 20px; font-weight: 500; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
.custom-card { background: #fff; border-radius: 8px; padding: 20px; position: relative; cursor: pointer; border: 1px solid #e4e7ed; transition: all 0.3s ease; overflow: hidden; display: flex; flex-direction: column; min-height: 180px; }
.custom-card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); border-color: #c6e2ff; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.scheme-name { font-size: 16px; font-weight: bold; color: #303133; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1; overflow: hidden; }
.card-desc { font-size: 13px; color: #606266; margin-bottom: 20px; line-height: 1.5; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; flex-grow: 1; height: 38px;}
.card-stats { display: flex; align-items: center; margin-bottom: 15px; background: #f9fafc; padding: 10px; border-radius: 6px; }
.stat-item { flex: 1; text-align: center; }
.stat-item .num { display: block; font-size: 18px; font-weight: bold; color: #409EFF; }
.stat-item .label { font-size: 11px; color: #909399; }
.divider { width: 1px; height: 20px; background: #e4e7ed; }
.card-tags { display: flex; flex-wrap: wrap; align-items: center; height: 26px; overflow: hidden; }
.more-tag { color: #909399; font-size: 12px; margin-left: 2px; }

/* 🌟 抽屉样式优化 */
.drawer-header-content { display: flex; align-items: center; gap: 10px; }
.d-title { font-size: 18px; font-weight: bold; color: #303133; }
.desc-box { background: #fff7e6; padding: 12px; border-radius: 6px; color: #d48806; font-size: 13px; display: flex; gap: 8px; line-height: 1.5; border: 1px solid #ffe7ba; margin-bottom: 10px; }

/* 分组列表样式 */
.grouped-list { display: flex; flex-direction: column; gap: 20px; }
.category-group { background: #fff; }
.group-header { 
  display: flex; align-items: center; gap: 6px; margin-bottom: 8px; 
  padding-bottom: 4px; border-bottom: 2px solid #f0f2f5;
}
.cat-point { width: 4px; height: 14px; background: #409EFF; border-radius: 2px; }
.cat-name { font-size: 14px; font-weight: 700; color: #303133; }
.cat-count { font-size: 12px; color: #909399; }

.group-items { display: flex; flex-direction: column; gap: 8px; }
.item-row { 
  display: flex; justify-content: space-between; align-items: center; 
  padding: 10px 12px; background: #f8fafc; border-radius: 6px; border: 1px solid #ebeef5;
}
.row-main .ds-name { font-weight: 600; font-size: 14px; color: #333; }
.row-main .cfg-name { font-size: 12px; color: #909399; margin-top: 2px; }
.row-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.metric-val { font-size: 12px; font-family: monospace; color: #67c23a; font-weight: 600; }
</style>