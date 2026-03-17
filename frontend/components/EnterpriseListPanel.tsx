'use client';

import React, { useState, useMemo } from 'react';
import { GraphNode } from '@/data/types';
import { nodeTypeConfig, riskLevelConfig } from '@/styles/theme';
import { MagnifyingGlassIcon, ChevronUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline';

interface EnterpriseListPanelProps {
  nodes: GraphNode[];
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode) => void;
}

type SortField = 'name' | 'riskScore' | 'scale' | 'district';
type SortOrder = 'asc' | 'desc';

export default function EnterpriseListPanel({ nodes, selectedNode, onSelectNode }: EnterpriseListPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('riskScore');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const filteredAndSortedNodes = useMemo(() => {
    let result = nodes.filter(node => {
      const query = searchQuery.toLowerCase();
      return (
        node.name.toLowerCase().includes(query) ||
        node.district.toLowerCase().includes(query) ||
        nodeTypeConfig[node.type]?.label.includes(query)
      );
    });

    result.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'riskScore':
          comparison = a.riskScore - b.riskScore;
          break;
        case 'scale':
          comparison = a.scale - b.scale;
          break;
        case 'district':
          comparison = a.district.localeCompare(b.district);
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return result;
  }, [nodes, searchQuery, sortField, sortOrder]);

  const SortHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
    >
      {children}
      {sortField === field && (
        sortOrder === 'asc' ? <ChevronUpIcon className="w-3 h-3" /> : <ChevronDownIcon className="w-3 h-3" />
      )}
    </button>
  );

  return (
    <div className="bg-gray-900/90 backdrop-blur-md rounded-xl border border-gray-700 overflow-hidden flex flex-col h-full">
      {/* 头部搜索 */}
      <div className="p-4 border-b border-gray-700">
        <h3 className="text-white font-semibold mb-3">企业列表</h3>
        
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="搜索企业名称、区域或类型..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-gray-800/50 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <div className="flex items-center gap-4 mt-3">
          <SortHeader field="name">名称</SortHeader>
          <SortHeader field="riskScore">风险分</SortHeader>
          <SortHeader field="scale">规模</SortHeader>
          <SortHeader field="district">区域</SortHeader>
        </div>
      </div>

      {/* 列表内容 */}
      <div className="flex-1 overflow-y-auto">
        {filteredAndSortedNodes.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            未找到匹配的企业
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {filteredAndSortedNodes.map(node => {
              const nodeConfig = nodeTypeConfig[node.type];
              const riskConfig = riskLevelConfig[node.riskLevel.toUpperCase() as keyof typeof riskLevelConfig];
              const isSelected = selectedNode?.id === node.id;

              return (
                <button
                  key={node.id}
                  onClick={() => onSelectNode(node)}
                  className={`w-full p-3 text-left transition-all ${
                    isSelected
                      ? 'bg-blue-900/30 border-l-2 border-blue-500'
                      : 'hover:bg-gray-800/50 border-l-2 border-transparent'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: `${nodeConfig?.color}20` }}
                    >
                      <span className="text-sm">{nodeConfig?.icon}</span>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-white text-sm font-medium truncate">{node.name}</p>
                        <span
                          className="text-xs px-1.5 py-0.5 rounded"
                          style={{
                            backgroundColor: riskConfig?.bgColor,
                            color: riskConfig?.color,
                          }}
                        >
                          {(node.riskScore * 100).toFixed(0)}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-gray-500">{nodeConfig?.label}</span>
                        <span className="text-gray-600">·</span>
                        <span className="text-gray-500">{node.district}</span>
                        <span className="text-gray-600">·</span>
                        <span className="text-gray-500">{node.scale}人</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 底部计数 */}
      <div className="p-3 border-t border-gray-700 text-xs text-gray-500">
        共 {filteredAndSortedNodes.length} 家企业
        {searchQuery && ` (搜索 "${searchQuery}")`}
      </div>
    </div>
  );
}
