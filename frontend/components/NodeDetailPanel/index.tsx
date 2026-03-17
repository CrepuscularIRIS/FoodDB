'use client';

import React from 'react';
import { GraphNode } from '@/data/types';
import { nodeTypeConfig, riskLevelConfig } from '@/styles/theme';
import { XMarkIcon, BuildingOfficeIcon, MapPinIcon, ScaleIcon, ExclamationTriangleIcon, CheckCircleIcon, ShieldExclamationIcon } from '@heroicons/react/24/outline';

interface NodeDetailPanelProps {
  node: GraphNode | null;
  onClose: () => void;
  onTracePath: (direction: 'upstream' | 'downstream') => void;
}

export default function NodeDetailPanel({ node, onClose, onTracePath }: NodeDetailPanelProps) {
  if (!node) return null;

  const nodeConfig = nodeTypeConfig[node.type];
  const riskConfig = riskLevelConfig[node.riskLevel.toUpperCase() as keyof typeof riskLevelConfig];

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-gray-900/95 backdrop-blur-md border-l border-gray-700 shadow-2xl z-50 overflow-y-auto">
      {/* 头部 */}
      <div className="sticky top-0 bg-gray-900/95 backdrop-blur-md border-b border-gray-700 p-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">企业详情</h2>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
        >
          <XMarkIcon className="w-5 h-5 text-gray-400" />
        </button>
      </div>

      <div className="p-4 space-y-6">
        {/* 基本信息 */}
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
              style={{ backgroundColor: `${nodeConfig?.color}20` }}
            >
              {nodeConfig?.icon}
            </div>
            <div>
              <h3 className="text-white font-medium">{node.name}</h3>
              <p className="text-sm text-gray-400">{nodeConfig?.label}</p>
            </div>
          </div>

          {/* 风险等级标签 */}
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium"
            style={{
              backgroundColor: riskConfig?.bgColor,
              color: riskConfig?.color,
            }}
          >
            {riskConfig?.icon}
            <span>{riskConfig?.label} (风险分: {(node.riskScore * 100).toFixed(1)})</span>
          </div>
        </div>

        {/* 关键指标 */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 mb-1">
              <ScaleIcon className="w-4 h-4" />
              <span className="text-xs">企业规模</span>
            </div>
            <p className="text-white font-semibold">{node.scale.toLocaleString()} 人</p>
          </div>

          <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 mb-1">
              <ShieldExclamationIcon className="w-4 h-4" />
              <span className="text-xs">信用等级</span>
            </div>
            <p className="text-white font-semibold">{node.creditRating}</p>
          </div>

          <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 mb-1">
              <ExclamationTriangleIcon className="w-4 h-4" />
              <span className="text-xs">历史违规</span>
            </div>
            <p className={`font-semibold ${node.violationCount > 0 ? 'text-red-400' : 'text-green-400'}`}>
              {node.violationCount} 次
            </p>
          </div>

          <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
            <div className="flex items-center gap-2 text-gray-400 mb-1">
              <CheckCircleIcon className="w-4 h-4" />
              <span className="text-xs">最后检查</span>
            </div>
            <p className="text-white font-semibold text-sm">
              {new Date(node.lastInspection).toLocaleDateString('zh-CN')}
            </p>
          </div>
        </div>

        {/* 地址信息 */}
        <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-3">
            <BuildingOfficeIcon className="w-4 h-4" />
            <span className="text-sm">地址信息</span>
          </div>
          
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">所属区域</span>
              <span className="text-white">{node.district}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">详细地址</span>
              <span className="text-white text-right max-w-[200px]">{node.address}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">坐标</span>
              <span className="text-gray-400 font-mono text-xs">{node.x.toFixed(4)}, {node.y.toFixed(4)}</span>
            </div>
          </div>
        </div>

        {/* 路径追踪 */}
        <div className="space-y-3">
          <p className="text-sm text-gray-400">供应链路径追踪</p>
          
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => onTracePath('upstream')}
              className="px-4 py-3 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-600/50 rounded-xl text-blue-400 transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4 rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
              </svg>
              追溯上游
            </button>
            
            <button
              onClick={() => onTracePath('downstream')}
              className="px-4 py-3 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-600/50 rounded-xl text-blue-400 transition-colors flex items-center justify-center gap-2"
            >
              追踪下游
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
              </svg>
            </button>
          </div>
        </div>

        {/* 风险分析 */}
        <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
          <p className="text-sm text-gray-400 mb-3">风险分析</p>
          
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-500">综合风险分</span>
                <span className={node.riskScore > 0.7 ? 'text-red-400' : node.riskScore > 0.4 ? 'text-amber-400' : 'text-green-400'}>
                  {(node.riskScore * 100).toFixed(0)}%
                </span>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    node.riskScore > 0.7 ? 'bg-red-500' : node.riskScore > 0.4 ? 'bg-amber-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${node.riskScore * 100}%` }}
                />
              </div>
            </div>
            
            {node.violationCount > 0 && (
              <div className="flex items-start gap-2 p-3 bg-red-900/20 border border-red-700/50 rounded-lg">
                <ExclamationTriangleIcon className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-red-300">
                  该企业有 {node.violationCount} 条历史违规记录，建议加强监管。
                </p>
              </div>
            )}
            
            {node.creditRating === 'BB' && (
              <div className="flex items-start gap-2 p-3 bg-amber-900/20 border border-amber-700/50 rounded-lg">
                <ShieldExclamationIcon className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-300">
                  该企业信用等级较低，存在潜在合作风险。
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
