import { 
  MagicStick, Collection, Monitor, Lock, DataLine, 
  ChatLineRound, Cpu, Operation, Connection 
} from '@element-plus/icons-vue'

// 1. 定义预设的“舒适色盘” (参考了 Element Plus 和 Ant Design 的配色)
const PRESET_COLORS = {
  'Reasoning': '#8e44ad',     // 优雅紫 (Wisteria)
  'Knowledge': '#409EFF',     // 品牌蓝
  'Coding':    '#e67e22',     // 活力橙 (Carrot) - 比纯黄更易读
  'Safety':    '#e74c3c',     // 柔和红 (Alizarin)
  'Understanding': '#16a085', // 青绿色 (Green Sea)
  'Language':  '#2980b9',     // 深蓝
  'Math':      '#d35400',     // 赭石色
  'General':   '#7f8c8d',     // 也就是灰色
}

export function getCapColor(cap) {
  if (!cap) return '#909399' // 默认灰
  
  // 1. 优先匹配预设色 (支持模糊匹配，如 "Math-Hard" 也能匹配到 "Math")
  for (const key in PRESET_COLORS) {
    if (cap.includes(key)) return PRESET_COLORS[key]
  }

  // 2. 降级策略：生成低饱和度的随机色 (优化算法)
  let hash = 0
  for (let i = 0; i < cap.length; i++) {
    hash = cap.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  // H (色相): 0-360
  const h = Math.abs(hash) % 360
  
  // S (饱和度): 降低到 40%-60% (之前是 65-85%，太艳了)
  // 这样颜色会带有“灰度”，看起来更高级、不刺眼
  const s = 40 + (Math.abs(hash) % 20) 
  
  // L (亮度): 控制在 45%-55% (保证在白底上的文字可读性)
  const l = 45 + (Math.abs(hash) % 10)
  
  return `hsl(${h}, ${s}%, ${l}%)`
}

export function getCapIcon(cap) {
  // 扩展图标映射，覆盖更多场景
  const map = { 
    'Reasoning': MagicStick,      // 推理 -> 魔法棒
    'Knowledge': Collection,      // 知识 -> 书籍集合
    'Coding': Monitor,            // 代码 -> 显示器
    'Safety': Lock,               // 安全 -> 锁
    'Understanding': ChatLineRound, // 理解 -> 对话气泡
    'Math': Operation,            // 数学 -> 运算符号
    'Language': Connection,       // 语言 -> 连接
    'Agent': Cpu                  // 智能体 -> CPU
  }
  
  for (const key in map) { 
    if (cap && cap.includes(key)) return map[key] 
  }
  
  // 默认图标
  return DataLine
}

// 状态颜色保持 Element Plus 标准色即可，这符合用户习惯
export function getStatusType(status) {
  const map = { 
    pending: 'info', 
    running: 'primary', 
    success: 'success', 
    failed: 'danger' 
  }
  return map[status] || 'info'
}