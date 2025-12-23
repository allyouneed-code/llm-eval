<script setup>
import { ref, onMounted } from 'vue'
import { Plus, Delete, Collection } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSchemes, deleteScheme } from '@/api/scheme'
import SchemeCreateDialog from './components/scheme/SchemeCreateDialog.vue'

const schemes = ref([])
const loading = ref(false)
const showCreateDialog = ref(false)

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getSchemes()
    schemes.value = res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该方案吗？这将影响基于该方案创建的新任务。', '警告', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await deleteScheme(id)
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
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-bold">评测方案管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon class="mr-1"><Plus /></el-icon> 新建方案
      </el-button>
    </div>

    <el-row :gutter="20" v-loading="loading">
      <el-col :span="8" v-for="item in schemes" :key="item.id">
        <el-card shadow="hover" class="mb-4 scheme-card">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-bold truncate" :title="item.name">{{ item.name }}</span>
              <el-button type="danger" link @click="handleDelete(item.id)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </template>
          
          <div class="text-gray-500 text-sm mb-4 h-10 overflow-hidden">
            {{ item.description || '暂无描述' }}
          </div>
          
          <div class="flex items-center text-blue-600 bg-blue-50 p-2 rounded">
            <el-icon class="mr-2"><Collection /></el-icon>
            <span class="font-bold text-lg mr-1">{{ item.dataset_config_ids.length }}</span>
            <span class="text-xs">个数据集配置</span>
          </div>
          
          <div class="mt-4 text-xs text-gray-400">
            创建于: {{ new Date(item.created_at).toLocaleDateString() }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <SchemeCreateDialog 
      v-model:visible="showCreateDialog" 
      @success="fetchData" 
    />
  </div>
</template>

<style scoped>
.scheme-card {
  transition: all 0.3s;
}
.scheme-card:hover {
  transform: translateY(-2px);
}
</style>