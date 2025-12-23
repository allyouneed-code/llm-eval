<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDatasets } from '@/api/dataset'
import { createScheme } from '@/api/scheme'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'success'])

const submitting = ref(false)
const form = reactive({
  name: '',
  description: '',
  config_ids: []
})

// 穿梭框数据源
const allConfigs = ref([])
// 穿梭框已选 ID
const selectedConfigIds = ref([])

// 加载所有可用配置
const fetchConfigs = async () => {
  try {
    // 获取所有数据集
    const res = await getDatasets({ page: 1, page_size: 100 }) // 简单起见，取前100个，实际应分页或搜索
    const configs = []
    
    // 扁平化处理：把 Meta 下的 Configs 拆出来
    res.items.forEach(meta => {
      if (meta.configs) {
        meta.configs.forEach(cfg => {
          configs.push({
            key: cfg.id,
            label: `[${meta.category}] ${meta.name} - ${cfg.config_name} (${cfg.display_metric})`,
            disabled: false
          })
        })
      }
    })
    allConfigs.value = configs
  } catch (e) {
    console.error(e)
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    form.name = ''
    form.description = ''
    selectedConfigIds.value = []
    fetchConfigs()
  }
})

const handleSubmit = async () => {
  if (!form.name) return ElMessage.warning('请输入方案名称')
  if (selectedConfigIds.value.length === 0) return ElMessage.warning('请至少选择一个数据集配置')

  submitting.value = true
  try {
    await createScheme({
      name: form.name,
      description: form.description,
      dataset_config_ids: selectedConfigIds.value
    })
    ElMessage.success('方案创建成功')
    emit('update:visible', false)
    emit('success')
  } catch (e) {
    // console.error(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog 
    title="创建评测方案" 
    :model-value="visible"
    @update:model-value="val => emit('update:visible', val)"
    width="800px"
  >
    <el-form :model="form" label-position="top">
      <el-form-item label="方案名称" required>
        <el-input v-model="form.name" placeholder="例如：Standard Benchmark v1" />
      </el-form-item>
      
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" placeholder="备注信息" />
      </el-form-item>

      <el-form-item label="选择数据集配置" required>
        <el-transfer
          v-model="selectedConfigIds"
          :data="allConfigs"
          :titles="['可选配置', '已选配置']"
          filterable
          filter-placeholder="搜索数据集..."
          style="width: 100%;"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
:deep(.el-transfer-panel) {
  width: 300px;
}
</style>