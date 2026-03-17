'use client';

import React from 'react';
import { FilterCriteria, NodeType, RiskLevel } from '@/data/types';
import { nodeTypeConfig, riskLevelConfig } from '@/styles/theme';
import { FunnelIcon, XMarkIcon } from '@heroicons/react/24/outline';

interface FilterPanelProps {
  filters: FilterCriteria;
  onFilterChange: (filters: FilterCriteria) => void;
  districts: string[];
}

const nodeTypes: NodeType[] = ['RAW_MILK', 'PROCESSOR', 'LOGISTICS', 'WAREHOUSE', 'DISTRIBUTOR', 'RETAILER'];
const riskLevels: RiskLevel[] = ['high', 'medium', 'low'];

export default function FilterPanel({ filters, onFilterChange, districts }: FilterPanelProps) {
  const toggleNodeType = (type: NodeType) => {
    const newTypes = filters.nodeTypes.includes(type)
      ? filters.nodeTypes.filter(t => t !== type)
      : [...filters.nodeTypes, type];
    onFilterChange({ ...filters, nodeTypes: newTypes });
  };

  const toggleRiskLevel = (level: RiskLevel) => {
    const newLevels = filters.riskLevels.includes(level)
      ? filters.riskLevels.filter(l => l !== level)
      : [...filters.riskLevels, level];
    onFilterChange({ ...filters, riskLevels: newLevels });
  };

  const toggleDistrict = (district: string) => {
    const newDistricts = filters.districts.includes(district)
      ? filters.districts.filter(d => d !== district)
      : [...filters.districts, district];
    onFilterChange({ ...filters, districts: newDistricts });
  };

  const clearFilters = () => {
    onFilterChange({
      nodeTypes: [],
      riskLevels: [],
      minScale: 0,
      maxScale: 10000,
      districts: [],
    });
  };

  const hasActiveFilters = 
    filters.nodeTypes.length > 0 ||
    filters.riskLevels.length > 0 ||
    filters.districts.length > 0 ||
    filters.minScale > 0 ||
    filters.maxScale < 10000;

  return (
    <div className="bg-gray-900/90 backdrop-blur-md rounded-xl border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FunnelIcon className="w-4 h-4 text-blue-400" />
          <h3 className="text-white font-medium text-sm">筛选器</h3>
        </div>
        
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            <XMarkIcon className="w-3 h-3" />
            清除
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* 节点类型筛选 */}
        <div>
          <p className="text-xs text-gray-500 mb-2">节点类型</p>
          <div className="grid grid-cols-2 gap-2">
            {nodeTypes.map(type => {
              const config = nodeTypeConfig[type];
              const isActive = filters.nodeTypes.includes(type);
              
              return (
                <button
                  key={type}
                  onClick={() => toggleNodeType(type)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all ${
                    isActive
                      ? 'bg-gray-700 text-white'
                      : 'bg-gray-800/50 text-gray-400 hover:bg-gray-800'
                  }`}
                >
                  <span>{config.icon}</span>
                  <span className="truncate">{config.label}</span>
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: config.color }}
                  />
                </button>
              );
            })}
          </div>
        </div>

        {/* 风险等级筛选 */}
        <div>
          <p className="text-xs text-gray-500 mb-2">风险等级</p>
          <div className="flex gap-2">
            {riskLevels.map(level => {
              const config = riskLevelConfig[level.toUpperCase() as keyof typeof riskLevelConfig];
              const isActive = filters.riskLevels.includes(level);
              
              return (
                <button
                  key={level}
                  onClick={() => toggleRiskLevel(level)}
                  className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs transition-all ${
                    isActive
                      ? 'text-white'
                      : 'bg-gray-800/50 text-gray-400 hover:bg-gray-800'
                  }`}
                  style={{
                    backgroundColor: isActive ? config?.bgColor : undefined,
                  }}
                >
                  <span>{config.icon}</span>
                  <span>{config.label}</span>
                </button>
              );
            })}</div>
        </div>

        {/* 企业规模滑块 */}
        <div>
          <div className="flex justify-between text-xs mb-2">
            <span className="text-gray-500">企业规模</span>
            <span className="text-gray-400">{filters.minScale} - {filters.maxScale}</span>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="0"
              max="1000"
              value={filters.minScale}
              onChange={(e) => onFilterChange({ ...filters, minScale: parseInt(e.target.value) })}
              className="flex-1 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <input
              type="range"
              min="0"
              max="10000"
              value={filters.maxScale}
              onChange={(e) => onFilterChange({ ...filters, maxScale: parseInt(e.target.value) })}
              className="flex-1 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>
        </div>

        {/* 区域筛选 */}
        <div>
          <p className="text-xs text-gray-500 mb-2">所属区域</p>
          <div className="flex flex-wrap gap-1.5">
            {districts.map(district => {
              const isActive = filters.districts.includes(district);
              
              return (
                <button
                  key={district}
                  onClick={() => toggleDistrict(district)}
                  className={`px-2.5 py-1 rounded-md text-xs transition-all ${
                    isActive
                      ? 'bg-blue-600/30 text-blue-400 border border-blue-600/50'
                      : 'bg-gray-800/50 text-gray-400 border border-transparent hover:bg-gray-800'
                  }`}
                >
                  {district}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
