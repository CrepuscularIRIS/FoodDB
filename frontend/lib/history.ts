// 查询历史管理
import { RiskAssessmentReport } from '@/types';

export interface HistoryRecord {
  id: string;
  query: string;
  targetType: string;
  targetName: string;
  riskLevel: string;
  riskScore: number;
  timestamp: number;
  report: RiskAssessmentReport;
}

const HISTORY_KEY = 'dairy_risk_assessment_history';
const MAX_HISTORY = 50;

// 获取历史记录
export function getHistory(): HistoryRecord[] {
  if (typeof window === 'undefined') return [];

  try {
    const data = localStorage.getItem(HISTORY_KEY);
    if (!data) return [];
    const parsed = JSON.parse(data);
    // 验证解析结果为数组
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.error('Failed to load history:', e);
    return [];
  }
}

// 添加历史记录
export function addHistory(record: Omit<HistoryRecord, 'id' | 'timestamp'>): HistoryRecord {
  const history = getHistory();

  const newRecord: HistoryRecord = {
    ...record,
    id: `hist_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    timestamp: Date.now(),
  };

  // 去重：如果查询相同，删除旧的
  const filtered = history.filter(h => h.query !== record.query);

  // 添加到开头
  const newHistory = [newRecord, ...filtered].slice(0, MAX_HISTORY);

  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));
  } catch (e) {
    console.error('Failed to save history:', e);
  }

  return newRecord;
}

// 删除历史记录
export function removeHistory(id: string): void {
  const history = getHistory();
  const filtered = history.filter(h => h.id !== id);

  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(filtered));
  } catch (e) {
    console.error('Failed to remove history:', e);
  }
}

// 清空历史记录
export function clearHistory(): void {
  try {
    localStorage.removeItem(HISTORY_KEY);
  } catch (e) {
    console.error('Failed to clear history:', e);
  }
}

// 格式化时间
export function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();

  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const dayDiff = Math.floor((startOfDay(now) - startOfDay(date)) / (24 * 60 * 60 * 1000));

  // 今天
  if (dayDiff === 0) {
    return `今天 ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`;
  }

  // 昨天
  if (dayDiff === 1) {
    return `昨天 ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`;
  }

  // 其他
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// 按日期分组
export function groupHistoryByDate(history: HistoryRecord[]): Record<string, HistoryRecord[]> {
  const groups: Record<string, HistoryRecord[]> = {};

  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const now = new Date();
  const nowStart = startOfDay(now);

  history.forEach(record => {
    const date = new Date(record.timestamp);
    const dateStart = startOfDay(date);
    const dayDiff = Math.floor((nowStart - dateStart) / (24 * 60 * 60 * 1000));

    let key: string;
    if (dayDiff === 0) {
      key = '今天';
    } else if (dayDiff === 1) {
      key = '昨天';
    } else {
      key = date.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
    }

    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(record);
  });

  return groups;
}
