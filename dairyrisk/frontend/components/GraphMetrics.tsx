'use client';

import { GraphMetrics as GraphMetricsType } from '@/types';
import {
  ShareIcon,
  BuildingOfficeIcon,
  TruckIcon,
  HomeIcon,
  ShoppingCartIcon,
  CubeIcon,
} from '@heroicons/react/24/outline';

interface GraphMetricsProps {
  metrics: GraphMetricsType;
}

const nodeTypeConfig: Record<string, { label: string; icon: React.ElementType; color: string; bgColor: string }> = {
  '牧场': {
    label: '牧场',
    icon: HomeIcon,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  'FARM': {
    label: '牧场',
    icon: HomeIcon,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  '乳企': {
    label: '乳企',
    icon: BuildingOfficeIcon,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  'PROCESSOR': {
    label: '乳企',
    icon: BuildingOfficeIcon,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  '物流': {
    label: '物流',
    icon: TruckIcon,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
  'LOGISTICS': {
    label: '物流',
    icon: TruckIcon,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
  '仓储': {
    label: '仓储',
    icon: CubeIcon,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  'WAREHOUSE': {
    label: '仓储',
    icon: CubeIcon,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  '零售': {
    label: '零售',
    icon: ShoppingCartIcon,
    color: 'text-pink-600',
    bgColor: 'bg-pink-50',
  },
  'RETAIL': {
    label: '零售',
    icon: ShoppingCartIcon,
    color: 'text-pink-600',
    bgColor: 'bg-pink-50',
  },
};

export default function GraphMetrics({ metrics }: GraphMetricsProps) {
  const typeDistribution = metrics.node_type_distribution || {};
  const totalNodes = metrics.total_nodes || Object.values(typeDistribution).reduce((a, b) => a + b, 0);
  const totalEdges = metrics.total_edges || 0;
  const density = metrics.network_density || 0;

  // Calculate percentages for visualization
  const typeEntries = Object.entries(typeDistribution).sort((a, b) => b[1] - a[1]);
  const maxCount = typeEntries[0]?.[1] || 1;

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-blue-600 font-medium">网络节点</p>
              <p className="text-2xl font-bold text-blue-900">{totalNodes.toLocaleString()}</p>
            </div>
            <div className="w-12 h-12 bg-blue-200 rounded-full flex items-center justify-center">
              <ShareIcon className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-green-600 font-medium">连接关系</p>
              <p className="text-2xl font-bold text-green-900">{totalEdges.toLocaleString()}</p>
            </div>
            <div className="w-12 h-12 bg-green-200 rounded-full flex items-center justify-center">
              <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-purple-600 font-medium">网络密度</p>
              <p className="text-2xl font-bold text-purple-900">{density.toFixed(4)}</p>
            </div>
            <div className="w-12 h-12 bg-purple-200 rounded-full flex items-center justify-center">
              <svg className="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Node Type Distribution */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h4 className="text-sm font-semibold text-gray-900 mb-4">节点类型分布</h4>

        <div className="space-y-3">
          {typeEntries.map(([type, count]) => {
            const config = nodeTypeConfig[type] || {
              label: type,
              icon: CubeIcon,
              color: 'text-gray-600',
              bgColor: 'bg-gray-50',
            };
            const Icon = config.icon;
            const percentage = (count / totalNodes) * 100;
            const barWidth = (count / maxCount) * 100;

            return (
              <div key={type} className="flex items-center space-x-3">
                <div className={`w-10 h-10 rounded-lg ${config.bgColor} flex items-center justify-center flex-shrink-0`}>
                  <Icon className={`h-5 w-5 ${config.color}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-900">{config.label}</span>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-semibold text-gray-900">{count.toLocaleString()}</span>
                      <span className="text-xs text-gray-500">({percentage.toFixed(1)}%)</span>
                    </div>
                  </div>

                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${
                        type.includes('牧场') || type === 'FARM'
                          ? 'bg-green-500'
                          : type.includes('乳企') || type === 'PROCESSOR'
                          ? 'bg-blue-500'
                          : type.includes('物流') || type === 'LOGISTICS'
                          ? 'bg-orange-500'
                          : type.includes('仓储') || type === 'WAREHOUSE'
                          ? 'bg-purple-500'
                          : 'bg-pink-500'
                      }`}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Network Visualization Hint */}
      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <div className="flex items-start">
          <ShareIcon className="h-5 w-5 text-gray-400 mt-0.5 mr-2" />
          <div>
            <h4 className="text-sm font-medium text-gray-900">异构图网络说明</h4>
            <p className="text-sm text-gray-600 mt-1">
              当前网络包含 {totalNodes.toLocaleString()} 个节点和 {totalEdges.toLocaleString()} 条边，
              涵盖牧场→乳企→物流→仓储→零售的完整供应链路径。
              网络密度 {density.toFixed(4)} 表明这是一个稀疏连接的异构图网络。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
