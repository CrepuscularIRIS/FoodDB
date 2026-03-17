/**
 * 供应链风险可视化主题配置
 * 深色主题 + 科技蓝配色
 */

export const theme = {
  // 基础颜色
  colors: {
    // 背景
    bgPrimary: '#0a0f1a',
    bgSecondary: '#111827',
    bgTertiary: '#1f2937',
    bgCard: 'rgba(17, 24, 39, 0.85)',
    bgCardHover: 'rgba(31, 41, 55, 0.9)',
    
    // 边框
    border: 'rgba(75, 85, 99, 0.3)',
    borderHighlight: 'rgba(59, 130, 246, 0.5)',
    
    // 文字
    textPrimary: '#f9fafb',
    textSecondary: '#9ca3af',
    textMuted: '#6b7280',
    
    // 科技蓝主色
    primary: '#3b82f6',
    primaryLight: '#60a5fa',
    primaryDark: '#2563eb',
    primaryGlow: 'rgba(59, 130, 246, 0.3)',
    
    // 功能色
    success: '#10b981',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#06b6d4',
    
    // 节点类型颜色（6种节点）
    nodeColors: {
      rawMilk: '#10b981',      // 绿色 - 原奶供应商
      processor: '#ef4444',    // 红色 - 乳制品加工厂
      logistics: '#3b82f6',    // 蓝色 - 物流公司
      warehouse: '#06b6d4',    // 青色 - 仓储中心
      distributor: '#8b5cf6',  // 紫色 - 经销商
      retailer: '#f59e0b',     // 黄色 - 零售终端
    },
    
    // 风险等级颜色
    risk: {
      high: '#ef4444',
      medium: '#f59e0b',
      low: '#10b981',
      unknown: '#6b7280',
    },
    
    // 边类型颜色（10种边）
    edgeColors: {
      supply: '#3b82f6',       // 供应关系
      transport: '#06b6d4',    // 运输关系
      store: '#8b5cf6',        // 存储关系
      sell: '#f59e0b',         // 销售关系
      process: '#ef4444',      // 加工关系
      partnership: '#10b981',  // 合作关系
      contract: '#ec4899',     // 合同关系
      logistics: '#6366f1',    // 物流关系
      quality: '#14b8a6',      // 质检关系
      other: '#9ca3af',        // 其他关系
    },
  },
  
  // 字体
  fonts: {
    primary: 'Inter, system-ui, -apple-system, sans-serif',
    mono: 'JetBrains Mono, Fira Code, monospace',
  },
  
  // 间距
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },
  
  // 圆角
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
  
  // 阴影
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.3)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.4)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.5)',
    glow: '0 0 20px rgba(59, 130, 246, 0.3)',
    glowRed: '0 0 20px rgba(239, 68, 68, 0.3)',
    glowGreen: '0 0 20px rgba(16, 185, 129, 0.3)',
  },
  
  // 动画
  animation: {
    duration: {
      fast: '150ms',
      normal: '300ms',
      slow: '500ms',
    },
    easing: {
      default: 'cubic-bezier(0.4, 0, 0.2, 1)',
      bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    },
  },
  
  // 断点
  breakpoints: {
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    xxl: '1536px',
  },
};

// 节点类型配置
export const nodeTypeConfig = {
  RAW_MILK: { 
    label: '原奶供应商', 
    color: '#10b981', 
    icon: '🥛',
    shape: 'circle' 
  },
  PROCESSOR: { 
    label: '乳制品加工厂', 
    color: '#ef4444', 
    icon: '🏭',
    shape: 'rect' 
  },
  LOGISTICS: { 
    label: '物流公司', 
    color: '#3b82f6', 
    icon: '🚚',
    shape: 'diamond' 
  },
  WAREHOUSE: { 
    label: '仓储中心', 
    color: '#06b6d4', 
    icon: '🏪',
    shape: 'hexagon' 
  },
  DISTRIBUTOR: { 
    label: '经销商', 
    color: '#8b5cf6', 
    icon: '📦',
    shape: 'triangle' 
  },
  RETAILER: { 
    label: '零售终端', 
    color: '#f59e0b', 
    icon: '🏪',
    shape: 'star' 
  },
};

// 边类型配置
export const edgeTypeConfig = {
  SUPPLY: { label: '供应', color: '#3b82f6', style: 'solid' },
  TRANSPORT: { label: '运输', color: '#06b6d4', style: 'dashed' },
  STORE: { label: '存储', color: '#8b5cf6', style: 'dotted' },
  SELL: { label: '销售', color: '#f59e0b', style: 'solid' },
  PROCESS: { label: '加工', color: '#ef4444', style: 'solid' },
  PARTNERSHIP: { label: '合作', color: '#10b981', style: 'dashed' },
  CONTRACT: { label: '合同', color: '#ec4899', style: 'dotted' },
  LOGISTICS: { label: '物流', color: '#6366f1', style: 'solid' },
  QUALITY: { label: '质检', color: '#14b8a6', style: 'dashed' },
  OTHER: { label: '其他', color: '#9ca3af', style: 'dotted' },
};

// 风险等级配置
export const riskLevelConfig = {
  HIGH: { 
    label: '高风险', 
    color: '#ef4444', 
    bgColor: 'rgba(239, 68, 68, 0.2)',
    icon: '🔴',
    threshold: 0.7 
  },
  MEDIUM: { 
    label: '中风险', 
    color: '#f59e0b', 
    bgColor: 'rgba(245, 158, 11, 0.2)',
    icon: '🟡',
    threshold: 0.4 
  },
  LOW: { 
    label: '低风险', 
    color: '#10b981', 
    bgColor: 'rgba(16, 185, 129, 0.2)',
    icon: '🟢',
    threshold: 0 
  },
};

export default theme;
