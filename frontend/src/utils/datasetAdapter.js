/**
 * src/utils/datasetAdapter.js
 * 修复版：增加了对多模态数据集的自动映射支持
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

// ⬇️ 兼容性导出
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

function getAutoPostProcessCfg(metric, taskType) {
  if (taskType === TASK_TYPES.CHOICE.value) {
    if (metric === 'Accuracy' || metric === 'F1') {
      return { 
        type: 'opencompass.utils.text_postprocessors.first_option_postprocess',
        options: 'ABCD'
      }
    }
  }
  return null
}

function generatePromptTemplate(taskType, mapping) {
  if (taskType === TASK_TYPES.CHOICE.value) {
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
  // 🌟 1. 解构 importState，注意这里增加了 modality
  const { meta, taskType, columnMapping, metrics, modality } = importState
  
  // 🌟 2. 构造 finalMapping (核心修复点)
  // 如果是多模态模式(非Text)且映射为空(因为跳过了Mapping步骤)，则自动填充默认值
  let finalMapping = { ...columnMapping }
  
  if (modality && modality !== 'Text' && Object.keys(finalMapping).length === 0) {
      if (taskType === TASK_TYPES.QA.value) {
          // 多模态 QA 默认映射
          finalMapping = {
              prompt: 'question', // 标准字段 question -> 映射到 Input 插槽
              target: 'answer'    // 标准字段 answer   -> 映射到 Target 插槽
          }
          // 根据模态追加资源字段，确保它们被加入 input_columns
          if (modality === 'Image') finalMapping.image = 'image'
          if (modality === 'Video') finalMapping.video = 'video'
          if (modality === 'Audio') finalMapping.audio = 'audio'
      }
      // 如果将来支持 Choice，可在此处扩展
  }

  // 🌟 3. Reader Config (使用 finalMapping)
  const inputColumns = Object.values(finalMapping).filter(v => v)
  const outputColumnKey = taskType === TASK_TYPES.CHOICE.value ? 'answer' : 'target'
  const outputColumn = finalMapping[outputColumnKey]

  const readerCfg = {
    input_columns: inputColumns,
    output_column: outputColumn,
    mapping: finalMapping 
  }

  // 🌟 4. Infer Config (使用 finalMapping 生成 Prompt)
  const promptTemplateStr = generatePromptTemplate(taskType, finalMapping)
  const inferCfg = {
    prompt_template: {
      type: 'PromptTemplate',
      template: promptTemplateStr
    },
    retriever: { type: 'ZeroRetriever' },
    inferencer: { type: 'GenInferencer' }
  }

  // 5. Generate Configs List
  const configs = metrics.map((metricName) => {
    const evaluatorType = METRIC_EVALUATOR_MAP[metricName] || 'AccEvaluator'
    const evaluatorConfig = { type: evaluatorType }
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