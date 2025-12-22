<script setup>
import { computed } from 'vue'
import { DataLine } from '@element-plus/icons-vue'

const props = defineProps({
  stats: { type: Array, default: () => [] },
  active: { type: String, default: 'All' }
})

const emit = defineEmits(['update:active'])

// 过滤无效分类
const visibleStats = computed(() => {
  return props.stats.filter(item => item.category && item.category.trim() !== '')
})

const totalCount = computed(() => {
  return props.stats.reduce((sum, item) => sum + item.count, 0)
})

const handleSelect = (index) => {
  emit('update:active', index)
}
</script>

<template>
  <el-aside width="240px" style="background: #fff; border-right: 1px solid #eee;">
    <div class="cap-header">能力维度 (Category)</div>
    <el-menu 
      :default-active="active" 
      @select="handleSelect"
      style="border-right: none;"
    >
      <el-menu-item index="All">
        <el-icon><DataLine /></el-icon>
        <span>All</span>
        <span class="menu-badge">{{ totalCount }}</span>
      </el-menu-item>
      
      <el-menu-item v-for="item in visibleStats" :key="item.category" :index="item.category">
        <el-icon><DataLine /></el-icon>
        <span>{{ item.category }}</span>
        <span class="menu-badge">{{ item.count }}</span>
      </el-menu-item>
    </el-menu>
  </el-aside>
</template>

<style scoped>
.cap-header { padding: 15px 20px; font-weight: bold; color: #303133; border-bottom: 1px solid #eee; background: #f5f7fa; }
.menu-badge { float: right; background: #f0f2f5; padding: 0 8px; border-radius: 10px; color: #909399; font-size: 12px; height: 20px; line-height: 20px; margin-top: 18px; }
</style>