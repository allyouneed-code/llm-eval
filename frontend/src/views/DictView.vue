<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import { 
  Plus, 
  Delete, 
  Search, 
  Refresh, 
  CollectionTag, 
  PriceTag, 
  EditPen,
  Document
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDicts, createDict, deleteDict } from '@/api/dict'

// ===========================
// 状态定义
// ===========================
const loading = ref(false)
const rawList = ref([]) // 原始数据
const showDialog = ref(false)
const searchQuery = ref('') // 搜索关键词

const form = reactive({
  category: '',
  code: '',
  label: '',
  sort_order: 0,
  description: ''
})

// ===========================
// 核心逻辑
// ===========================

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getDicts()
    rawList.value = res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 🌟 客户端即时搜索/过滤
const filteredList = computed(() => {
  if (!searchQuery.value) return rawList.value
  const q = searchQuery.value.toLowerCase()
  return rawList.value.filter(item => 
    item.category.toLowerCase().includes(q) || 
    item.label.toLowerCase().includes(q) || 
    item.code.toLowerCase().includes(q)
  )
})

// 🌟 辅助函数：根据分类字符串生成固定的 Tag 颜色类型
const getTagType = (str) => {
  const types = ['', 'success', 'warning', 'danger', 'info']
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return types[Math.abs(hash) % types.length]
}

// ===========================
// 交互操作
// ===========================

const handleCreate = async () => {
  if(!form.category || !form.code || !form.label) {
    return ElMessage.warning('请填写必填项')
  }
  try {
    await createDict(form)
    ElMessage.success('创建成功')
    showDialog.value = false
    fetchData()
    // 重置表单
    Object.assign(form, { category: '', code: '', label: '', sort_order: 0, description: '' })
  } catch (e) {
    console.error(e)
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('删除后可能会影响关联业务显示，是否继续？', '警告', { 
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning' 
    })
    await deleteDict(id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    // cancel
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="app-container">
    
    <div class="content-card header-card">
      <div class="page-header">
        <div class="title-group">
          <el-icon class="icon-logo"><CollectionTag /></el-icon>
          <div>
            <h2 class="page-title">数据字典</h2>
            <p class="sub-title">系统枚举值配置中心</p>
          </div>
        </div>
        
        <div class="actions-group">
          <el-input 
            v-model="searchQuery" 
            placeholder="搜索分类 / 键值 / 名称..." 
            class="search-input"
            clearable
            :prefix-icon="Search"
          />
          <el-button :icon="Refresh" circle @click="fetchData" title="刷新列表" />
          <el-button type="primary" :icon="Plus" @click="showDialog = true" class="create-btn">
            新建字典项
          </el-button>
        </div>
      </div>
    </div>

    <div class="content-card main-card" v-loading="loading">
      <el-table :data="filteredList" style="width: 100%" :header-cell-style="{ background: '#f8fafc', color: '#606266' }">
        
        <el-table-column prop="category" label="分类标识 (Category)" min-width="180" sortable>
          <template #default="{ row }">
            <el-tag :type="getTagType(row.category)" effect="plain" round>
              {{ row.category }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="code" label="键值 (Code)" width="140">
          <template #default="{ row }">
            <span class="code-text">{{ row.code }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="label" label="显示名 (Label)" min-width="160">
          <template #default="{ row }">
            <span style="font-weight: 600; color: #303133;">{{ row.label }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="sort_order" label="排序" width="80" align="center">
          <template #default="{ row }">
            <span style="color: #909399; font-family: monospace;">{{ row.sort_order }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="描述说明" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
             <span v-if="row.description">{{ row.description }}</span>
             <span v-else style="color: #ccc;">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="scope">
            <el-button type="danger" link :icon="Delete" @click="handleDelete(scope.row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty v-if="!loading && filteredList.length === 0" description="暂无相关数据" :image-size="100" />
    </div>

    <el-dialog 
      v-model="showDialog" 
      title="新增字典项" 
      width="580px"
      class="custom-dialog"
      destroy-on-close
    >
      <div class="dialog-tip">
        <el-icon><Document /></el-icon>
        <span>请确保 "分类标识" 与代码中调用的 Key 保持一致 (如 model_param_size)</span>
      </div>

      <el-form :model="form" label-position="top" size="large" class="create-form">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="分类标识 (Category)" required>
              <el-input v-model="form.category" placeholder="">
                <template #prefix><el-icon><CollectionTag /></el-icon></template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="键值 (Code)" required>
              <el-input v-model="form.code" placeholder="">
                <template #prefix><el-icon><PriceTag /></el-icon></template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="16">
            <el-form-item label="显示名称 (Label)" required>
              <el-input v-model="form.label" placeholder="">
                 <template #prefix><el-icon><EditPen /></el-icon></template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述说明 (可选)">
          <el-input 
            v-model="form.description" 
            type="textarea" 
            :rows="3" 
            placeholder="该选项的备注信息，仅后台可见..."
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showDialog = false">取消</el-button>
          <el-button type="primary" @click="handleCreate">确认创建</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 容器与背景 */
.app-container {
  padding: 24px;
  background-color: #f0f2f5;
  min-height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 通用卡片样式 */
.content-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  border: 1px solid #ebeef5;
}

/* 顶部 Header 样式 */
.header-card {
  padding: 20px 24px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title-group {
  display: flex;
  align-items: center;
  gap: 16px;
}
.icon-logo {
  font-size: 24px;
  color: #409EFF;
  background: #ecf5ff;
  padding: 10px;
  border-radius: 12px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.sub-title {
  margin: 4px 0 0 0;
  font-size: 13px;
  color: #909399;
}

/* 操作栏 */
.actions-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-input {
  width: 260px;
}
.create-btn {
  padding: 10px 20px;
  font-weight: 500;
  border-radius: 6px;
}

/* 表格区域 */
.main-card {
  padding: 0; /* 表格自带 padding */
  overflow: hidden;
  flex: 1; /* 撑满剩余高度 */
}
.code-text {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #d63384; /* 类似代码的高亮色 */
  background: #fff0f6;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

/* 弹窗样式 */
.dialog-tip {
  background: #e6f7ff;
  border: 1px solid #91caff;
  color: #1890ff;
  padding: 10px 15px;
  border-radius: 4px;
  font-size: 13px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1.4;
}
.create-form .el-form-item__label {
  font-weight: 500;
}
</style>