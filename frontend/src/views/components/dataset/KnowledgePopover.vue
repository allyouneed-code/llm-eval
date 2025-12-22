<script setup>
import { QuestionFilled } from '@element-plus/icons-vue'
</script>

<template>
  <el-popover
    placement="bottom-start"
    :width="500"
    trigger="hover"
    popper-class="knowledge-popover-container"
  >
    <template #reference>
      <el-icon class="help-icon"><QuestionFilled /></el-icon>
    </template>
    
    <div class="knowledge-content">
      <div class="k-section">
        <h4 class="k-title">🛠️ 评测模式 (Mode)</h4>
        <div class="k-item">
          <span class="k-label">Gen (生成式)</span>
          <span class="k-desc">模型生成完整文本。适用于问答、翻译、代码生成。通常较慢。</span>
        </div>
        <div class="k-item">
          <span class="k-label">PPL (判别式)</span>
          <span class="k-desc">Perplexity(困惑度)。模型不生成文本，而是计算选项(ABCD)的概率。适用于选择题，速度快。</span>
        </div>
      </div>

      <div class="k-divider"></div>

      <div class="k-section">
        <h4 class="k-title">⚖️ 裁判类型 (Evaluator)</h4>
        <div class="k-item">
          <span class="k-label">Rule (规则)</span>
          <span class="k-desc">使用字符串匹配或正则提取答案。客观、标准，但对长文本无力。</span>
        </div>
        <div class="k-item">
          <span class="k-label">LLM (模型)</span>
          <span class="k-desc">使用 GPT-4 等强模型作为裁判进行打分。主观、灵活，适合开放性问题。</span>
        </div>
      </div>

      <div class="k-divider"></div>

      <div class="k-section">
        <h4 class="k-title">📊 常见指标 (Metrics)</h4>
        <div class="k-item">
          <span class="k-label">Accuracy</span>
          <span class="k-desc">准确率。预测正确数 / 总数。用于选择题。</span>
        </div>
        <div class="k-item">
          <span class="k-label">Pass@k</span>
          <span class="k-desc">代码通过率。生成 k 个代码样本，至少有一个通过测试即视为成功。</span>
        </div>
        <div class="k-item">
          <span class="k-label">BLEU/ROUGE</span>
          <span class="k-desc">文本重合度。分别用于翻译和摘要，计算 n-gram 词汇重叠。</span>
        </div>
        <div class="k-item">
          <span class="k-label">Score</span>
          <span class="k-desc">智能打分。通常是 1-10 分，评价回答的质量、安全性或相关性。</span>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<style scoped>
/* 触发图标的样式保留在组件内 */
.help-icon { margin-left: 10px; color: #909399; cursor: pointer; transition: color 0.3s; font-size: 18px; }
.help-icon:hover { color: #409eff; }
</style>

<style>
.knowledge-content { padding: 5px; }
.k-section { margin-bottom: 12px; }
.k-title { margin: 0 0 10px 0; font-size: 14px; color: #303133; font-weight: 700; border-left: 3px solid #409eff; padding-left: 8px; }
.k-item { margin-bottom: 8px; display: flex; flex-direction: column; }
.k-label { font-weight: bold; color: #555; font-size: 13px; margin-bottom: 2px; }
.k-desc { color: #888; font-size: 12px; line-height: 1.4; }
.k-divider { height: 1px; background: #f0f2f5; margin: 12px 0; }
</style>