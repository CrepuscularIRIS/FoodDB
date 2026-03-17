'use client';

import React from 'react';
import { nodeTypeConfig, edgeTypeConfig, riskLevelConfig } from '@/styles/theme';

export default function GraphLegend() {
  const [activeTab, setActiveTab] = React.useState<'nodes' | 'edges' | 'risk'>('nodes');

  return (
    <div className="bg-gray-900/90 backdrop-blur-md rounded-xl border border-gray-700 p-4">
      <div className="flex gap-2 mb-3">
        {[
          { key: 'nodes', label: '节点类型' },
          { key: 'edges', label: '边类型' },
          { key: 'risk', label: '风险等级' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`px-3 py-1 rounded-lg text-xs transition-all ${
              activeTab === tab.key
                ? 'bg-blue-600/30 text-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {activeTab === 'nodes' && (
          <>
            {Object.entries(nodeTypeConfig).map(([type, config]) => (
              <div key={type} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: config.color }}
                />
                <span className="text-xs text-gray-300">{config.icon} {config.label}</span>
              </div>
            ))}
          </>
        )}

        {activeTab === 'edges' && (
          <>
            {Object.entries(edgeTypeConfig).slice(0, 6).map(([type, config]) => (
              <div key={type} className="flex items-center gap-2">
                <div
                  className="w-6 h-0.5"
                  style={{
                    backgroundColor: config.color,
                    borderStyle: config.style === 'dashed' ? 'dashed' : config.style === 'dotted' ? 'dotted' : 'solid',
                    borderWidth: config.style !== 'solid' ? '1px 0' : '0',
                    borderColor: config.color,
                  }}
                />
                <span className="text-xs text-gray-300">{config.label}</span>
              </div>
            ))}
          </>
        )}

        {activeTab === 'risk' && (
          <>
            {Object.entries(riskLevelConfig).map(([level, config]) => (
              <div key={level} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: config.color }}
                />
                <span className="text-xs text-gray-300">{config.icon} {config.label}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
