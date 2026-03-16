'use client';

import { useEffect, useState } from 'react';
import { riskApi } from '@/lib/api';

interface RiskStats {
  total_nodes: number;
  risk_level_distribution: {
    高风险: number;
    中风险: number;
    低风险: number;
  };
  average_risk_probability: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
}

interface RiskStatsCardProps {
  onClose?: () => void;
}

export default function RiskStatsCard({ onClose }: RiskStatsCardProps) {
  const [stats, setStats] = useState<RiskStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const result = await riskApi.getStats();
        if (result.success && result.data) {
          setStats(result.data);
        } else {
          setError(result.error || '获取统计数据失败');
        }
      } catch (err: any) {
        setError(err.message || '请求失败');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="grid grid-cols-4 gap-4">
            <div className="h-20 bg-gray-200 rounded-lg"></div>
            <div className="h-20 bg-gray-200 rounded-lg"></div>
            <div className="h-20 bg-gray-200 rounded-lg"></div>
            <div className="h-20 bg-gray-200 rounded-lg"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
        <div className="text-center text-red-500 py-4">
          <p>加载失败: {error}</p>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-gray-200">
      {/* 头部 */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            风险统计仪表盘
          </h2>
          {onClose && (
            <button
              onClick={onClose}
              className="text-white/80 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* 核心指标卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 总节点数 */}
          <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-xl p-5 border border-slate-200 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500 font-medium">总节点数</p>
                <p className="text-3xl font-bold text-slate-800 mt-1">{stats.total_nodes}</p>
              </div>
              <div className="w-12 h-12 bg-slate-200 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
            </div>
          </div>

          {/* 高风险 */}
          <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-xl p-5 border border-red-200 hover:shadow-md transition-shadow animate-pulse-once">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-red-600 font-medium">高风险</p>
                <p className="text-3xl font-bold text-red-700 mt-1">{stats.high_risk_count}</p>
              </div>
              <div className="w-12 h-12 bg-red-200 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
            </div>
            <div className="mt-2 h-2 bg-red-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-red-500 to-red-600 rounded-full transition-all duration-1000"
                style={{ width: `${stats.total_nodes > 0 ? (stats.high_risk_count / stats.total_nodes) * 100 : 0}%` }}
              />
            </div>
          </div>

          {/* 中风险 */}
          <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-xl p-5 border border-amber-200 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-amber-600 font-medium">中风险</p>
                <p className="text-3xl font-bold text-amber-700 mt-1">{stats.medium_risk_count}</p>
              </div>
              <div className="w-12 h-12 bg-amber-200 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <div className="mt-2 h-2 bg-amber-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-amber-400 to-amber-500 rounded-full transition-all duration-1000"
                style={{ width: `${stats.total_nodes > 0 ? (stats.medium_risk_count / stats.total_nodes) * 100 : 0}%` }}
              />
            </div>
          </div>

          {/* 低风险 */}
          <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-xl p-5 border border-emerald-200 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-emerald-600 font-medium">低风险</p>
                <p className="text-3xl font-bold text-emerald-700 mt-1">{stats.low_risk_count}</p>
              </div>
              <div className="w-12 h-12 bg-emerald-200 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <div className="mt-2 h-2 bg-emerald-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full transition-all duration-1000"
                style={{ width: `${stats.total_nodes > 0 ? (stats.low_risk_count / stats.total_nodes) * 100 : 0}%` }}
              />
            </div>
          </div>
        </div>

        {/* 平均风险概率 */}
        <div className="bg-gradient-to-r from-violet-50 to-purple-50 rounded-xl p-5 border border-violet-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-violet-600 font-medium">平均风险概率</p>
              <p className="text-4xl font-bold text-violet-700 mt-1">
                {(stats.average_risk_probability * 100).toFixed(2)}%
              </p>
            </div>
            <div className="w-16 h-16 bg-violet-200 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
          </div>
          <div className="mt-4 h-3 bg-violet-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full transition-all duration-1000"
              style={{ width: `${stats.average_risk_probability * 100}%` }}
            />
          </div>
        </div>

        {/* 风险分布可视化 */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 bg-red-50 rounded-lg border border-red-100">
            <div className="text-2xl font-bold text-red-600">{stats.high_risk_count}</div>
            <div className="text-sm text-red-500 mt-1">高风险节点</div>
          </div>
          <div className="text-center p-4 bg-amber-50 rounded-lg border border-amber-100">
            <div className="text-2xl font-bold text-amber-600">{stats.medium_risk_count}</div>
            <div className="text-sm text-amber-500 mt-1">中风险节点</div>
          </div>
          <div className="text-center p-4 bg-emerald-50 rounded-lg border border-emerald-100">
            <div className="text-2xl font-bold text-emerald-600">{stats.low_risk_count}</div>
            <div className="text-sm text-emerald-500 mt-1">低风险节点</div>
          </div>
        </div>
      </div>
    </div>
  );
}
