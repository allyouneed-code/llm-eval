/**
 * src/utils/datasetAdapter.js
 * 修复版：保留了旧的常量导出以防止 Import Error，同时内置了自动后处理逻辑
 */

// ==========================================
// 1. 核心定义
// ==========================================

export const TASK_TYPES = {
  CHOICE: { 
    label: '客观选择题 (Multiple Choice)', 
    value: 'choice',
    desc: '适用于 MMLU, CMMLU, ARC 等有标准选项(A/B/C/D)的题目'
  },
  QA: { 
    label: '开放式问答 (Open QA)', 
    value: 'qa',
    desc: '适用于翻译、摘要、简答等生成式任务'
  }
}

export const TASK_SLOTS = {
  [TASK_TYPES.CHOICE.value]: [
    { key: 'question', label: '题目 (Question)', required: true },
    { key: 'optA', label: '选项 A', required: true },
    { key: 'optB', label: '选项 B', required: true },
    { key: 'optC', label: '选项 C', required: false },
    { key: 'optD', label: '选项 D', required: false },
    { key: 'answer', label: '标准答案 (Key)', required: true }
  ],
  [TASK_TYPES.QA.value]: [
    { key: 'prompt', label: '输入/提示词 (Input)', required: true },
    { key: 'target', label: '参考答案 (Target)', required: true }
  ]
}

export const TASK_METRICS = {
  [TASK_TYPES.CHOICE.value]: [
    { label: 'Accuracy (准确率)', value: 'Accuracy', default: true },
    { label: 'F1 Score (加权得分)', value: 'F1', default: false }
  ],
  [TASK_TYPES.QA.value]: [
    { label: 'ROUGE-L (文本相似度)', value: 'ROUGE', default: true },
    { label: 'BLEU-4 (机器翻译标准)', value: 'BLEU', default: false },
    { label: 'Exact Match (完全匹配)', value: 'EM', default: false }
  ]
}

// ⬇️ 兼容性修复：保留这些导出，防止 Vue 组件报错
export const CHOICE_POST_PROCESSORS = [
  { label: '提取首选项 (A/B/C/D)', value: 'first_option' }
]
export const QA_POST_PROCESSORS = []

// ==========================================
// 2. 自动映射逻辑 (Auto-Mapping)
// ==========================================

const METRIC_EVALUATOR_MAP = {
  'Accuracy': 'AccEvaluator',
  'F1': 'F1Evaluator',
  'ROUGE': 'RougeEvaluator',
  'BLEU': 'BleuEvaluator',
  'EM': 'EMEvaluator'
}

/**
 * 根据指标和任务类型，获取最佳后处理配置
 */
function getAutoPostProcessCfg(metric, taskType) {
  // 场景 A: 选择题 (Choice) -> 自动应用 first_option_postprocess
  if (taskType === TASK_TYPES.CHOICE.value) {
    if (metric === 'Accuracy' || metric === 'F1') {
      return { 
        type: 'opencompass.utils.text_postprocessors.first_option_postprocess',
        options: 'ABCD'
      }
    }
  }

  // 场景 B: 问答题 (QA) -> 默认 null (Raw Match)
  // ROUGE/BLEU 在通用场景下不需要特定后处理
  return null
}

function generatePromptTemplate(taskType, mapping) {
  if (taskType === TASK_TYPES.CHOICE.value) {
    // 确保这里的 mapping key 对应的是实际的 CSV 列名
    // 注意：模板里用 {MappingKey}，而不是 {SlotKey}
    let template = `Question: {${mapping.question}}\n`
    if (mapping.optA) template += `A. {${mapping.optA}}\n`
    if (mapping.optB) template += `B. {${mapping.optB}}\n`
    if (mapping.optC) template += `C. {${mapping.optC}}\n`
    if (mapping.optD) template += `D. {${mapping.optD}}\n`
    template += `Answer:`
    return template
  }
  if (taskType === TASK_TYPES.QA.value) {
    return `Question: {${mapping.prompt}}\nAnswer:`
  }
  return ''
}

// ==========================================
// 3. 工厂方法
// ==========================================

export function generateConfigPayload(importState) {
  const { meta, taskType, columnMapping, metrics } = importState
  
  // 1. Reader Config
  const inputColumns = Object.values(columnMapping).filter(v => v)
  const outputColumnKey = taskType === TASK_TYPES.CHOICE.value ? 'answer' : 'target'
  const outputColumn = columnMapping[outputColumnKey]

  const readerCfg = {
    input_columns: inputColumns,
    output_column: outputColumn,
    // 🌟 核心修复：必须包含 mapping 字段，否则后端 Schema 校验会失败 (400 Bad Request)
    mapping: columnMapping 
  }

  // 2. Infer Config
  const promptTemplateStr = generatePromptTemplate(taskType, columnMapping)
  const inferCfg = {
    prompt_template: {
      type: 'PromptTemplate',
      template: promptTemplateStr
    },
    retriever: { type: 'ZeroRetriever' },
    inferencer: { type: 'GenInferencer' }
  }

  // 3. Generate Configs List
  const configs = metrics.map((metricName) => {
    // A. 确定 Evaluator
    const evaluatorType = METRIC_EVALUATOR_MAP[metricName] || 'AccEvaluator'
    const evaluatorConfig = { type: evaluatorType }

    // B. 自动确定 PostProcess (忽略前端传来的 postProcess 字段)
    const postProcessCfg = getAutoPostProcessCfg(metricName, taskType) || {}
    
    return {
      config_name: `${meta.name}_${metricName}`,
      mode: 'gen', 
      display_metric: metricName,
      
      reader_cfg: JSON.stringify(readerCfg),
      infer_cfg: JSON.stringify(inferCfg),
      metric_config: JSON.stringify({ evaluator: evaluatorConfig }),
      post_process_cfg: JSON.stringify(postProcessCfg),
      few_shot_cfg: JSON.stringify({})
    }
  })

  return configs
}