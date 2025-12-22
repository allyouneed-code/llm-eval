<script setup>
import { getStatusType } from '@/utils/style'

defineProps({
  status: { type: String, required: true }
})
</script>

<template>
  <el-tag :type="getStatusType(status)" effect="light" size="small" round>
    {{ status.toUpperCase() }}
  </el-tag>
</template>