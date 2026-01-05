<template>
  <div class="compare-view-container">
    <div v-if="loading" class="loading-state">
       <el-icon class="is-loading loading-icon"><Loading /></el-icon>
       <p>正在处理数据，请稍候...</p>
    </div>

    <transition name="fade-slide" mode="out-in">
      <div v-if="!loading" :key="report ? 'report' : 'selector'" class="content-wrapper">
        <CompareReport 
          v-if="report" 
          :report="report" 
          @back="handleReset" 
        />

        <CompareSelector 
          v-else 
          @submit="handleStartCompare" 
        />
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { compareTasks } from '@/api/task'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'

import CompareSelector from './components/compare/CompareSelector.vue'
import CompareReport from './components/compare/CompareReport.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const report = ref(null)

onMounted(() => {
  const ids = route.query.ids
  if (ids) loadReport(ids)
})

const loadReport = async (idsStr) => {
  loading.value = true
  try {
    const taskIds = idsStr.split(',').map(Number)
    const res = await compareTasks({ task_ids: taskIds })
    if (!res || !res.models) throw new Error("数据异常")
    report.value = res
  } catch (e) {
    ElMessage.error("生成报告失败，请重试")
    report.value = null
    router.replace({ query: {} })
  } finally {
    // 延迟一点点关闭 loading，让动画更自然
    setTimeout(() => { loading.value = false }, 300)
  }
}

const handleStartCompare = (ids) => {
  const idsStr = ids.join(',')
  router.push({ query: { ids: idsStr } })
  loadReport(idsStr)
}

const handleReset = () => {
  report.value = null
  router.push({ query: {} })
}
</script>

<style scoped>
.compare-view-container {
  min-height: 100vh;
  background-color: #f0f2f5; /* 浅灰背景 */
  padding: 24px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60vh;
  color: #909399;
}

.loading-icon {
  font-size: 40px;
  color: #409EFF;
  margin-bottom: 16px;
}

/* 动画效果 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>