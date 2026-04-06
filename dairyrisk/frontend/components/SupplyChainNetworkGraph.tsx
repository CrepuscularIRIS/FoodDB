'use client';

import { useMemo, useState } from 'react';
import { GraphCanvas, GraphEdge, GraphNode } from 'reagraph';
import { ArrowDownTrayIcon, FunnelIcon, XMarkIcon } from '@heroicons/react/24/outline';

interface NodeData {
  id: string;
  name: string;
  type: string;
  scale?: string;
  region?: string;
  risk_probability: number;
  risk_level: 'high' | 'medium' | 'low';
  confidence: number;
  violations: number;
}

interface EdgeData {
  source: string;
  target: string;
  relation?: string;
  risk_level?: 'high' | 'medium' | 'low';
  risk_probability?: number;
  priority_score?: number;
  product_type?: string;
}

interface SupplyChainNetworkGraphProps {
  nodes: NodeData[];
  edges: EdgeData[];
  onClose?: () => void;
}

export default function SupplyChainNetworkGraph({
  nodes: initialNodes,
  edges: initialEdges,
  onClose,
}: SupplyChainNetworkGraphProps) {
  const [showLegend, setShowLegend] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [selectedRiskLevels, setSelectedRiskLevels] = useState<Set<string>>(new Set(['high', 'medium', 'low']));
  const [selectedEdgeRiskLevels, setSelectedEdgeRiskLevels] = useState<Set<string>>(new Set(['high', 'medium', 'low']));
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());

  const nodeTypes = useMemo(() => {
    const types = new Set(initialNodes.map((n) => n.type));
    return Array.from(types);
  }, [initialNodes]);

  const filteredNodeIds = useMemo(() => {
    return new Set(
      initialNodes
        .filter((n) => selectedRiskLevels.has(n.risk_level) && (selectedTypes.size === 0 || selectedTypes.has(n.type)))
        .map((n) => n.id)
    );
  }, [initialNodes, selectedRiskLevels, selectedTypes]);

  const filteredEdges = useMemo(() => {
    return initialEdges.filter(
      (e) =>
        filteredNodeIds.has(e.source) &&
        filteredNodeIds.has(e.target) &&
        selectedEdgeRiskLevels.has(e.risk_level || 'low')
    );
  }, [initialEdges, filteredNodeIds, selectedEdgeRiskLevels]);

  const graphNodes: GraphNode[] = useMemo(() => {
    return initialNodes
      .filter((n) => filteredNodeIds.has(n.id))
      .map((node) => {
        const fill =
          node.risk_level === 'high' ? '#ef4444' : node.risk_level === 'medium' ? '#eab308' : '#22c55e';
        return {
          id: node.id,
          label: node.name,
          data: node,
          fill,
          size: node.risk_level === 'high' ? 18 : node.risk_level === 'medium' ? 14 : 10,
        };
      });
  }, [initialNodes, filteredNodeIds]);

  const graphEdges: GraphEdge[] = useMemo(() => {
    return filteredEdges.map((edge, idx) => ({
      id: `edge-${idx}`,
      source: edge.source,
      target: edge.target,
      label: edge.relation || '',
      data: edge,
      fill: edge.risk_level === 'high' ? '#ef4444' : edge.risk_level === 'medium' ? '#f59e0b' : '#94a3b8',
      size: edge.risk_level === 'high' ? 2.2 : edge.risk_level === 'medium' ? 1.6 : 1.0,
      interpolation: 'curved',
      arrowPlacement: 'end',
    }));
  }, [filteredEdges]);

  const toggleEdgeRiskLevel = (level: string) => {
    const next = new Set(selectedEdgeRiskLevels);
    if (next.has(level)) {
      next.delete(level);
    } else {
      next.add(level);
    }
    setSelectedEdgeRiskLevels(next);
  };

  const toggleRiskLevel = (level: string) => {
    const next = new Set(selectedRiskLevels);
    if (next.has(level)) {
      next.delete(level);
    } else {
      next.add(level);
    }
    setSelectedRiskLevels(next);
  };

  const toggleNodeType = (type: string) => {
    const next = new Set(selectedTypes);
    if (next.has(type)) {
      next.delete(type);
    } else {
      next.add(type);
    }
    setSelectedTypes(next);
  };

  const exportGraph = () => {
    const data = {
      nodes: initialNodes.filter((n) => filteredNodeIds.has(n.id)),
      edges: filteredEdges,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'supply-chain-filtered.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 bg-white z-50 overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-14 bg-gray-900 text-white flex items-center justify-between px-4 z-10">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">供应链全图可视化</h2>
          <span className="text-sm text-gray-400">
            {filteredNodeIds.size} 节点 / {filteredEdges.length} 边
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={`p-2 rounded-lg transition-colors ${showFilters ? 'bg-blue-600' : 'hover:bg-gray-800'}`}
            title="筛选"
          >
            <FunnelIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={exportGraph}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
            title="导出数据"
          >
            <ArrowDownTrayIcon className="h-5 w-5" />
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
              title="关闭"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>

      {showFilters && (
        <div
          className="absolute top-14 left-0 w-64 bg-white border-r border-gray-200 z-10 p-4 shadow-lg overflow-y-auto"
          style={{ height: 'calc(100vh - 56px)' }}
        >
          <h3 className="font-semibold text-gray-900 mb-3">风险等级筛选</h3>
          <div className="space-y-2 mb-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedRiskLevels.has('high')}
                onChange={() => toggleRiskLevel('high')}
                className="rounded text-red-600"
              />
              <span className="w-3 h-3 rounded-full bg-red-500" />
              <span>高风险 ({initialNodes.filter((n) => n.risk_level === 'high').length})</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedRiskLevels.has('medium')}
                onChange={() => toggleRiskLevel('medium')}
                className="rounded text-yellow-500"
              />
              <span className="w-3 h-3 rounded-full bg-yellow-500" />
              <span>中风险 ({initialNodes.filter((n) => n.risk_level === 'medium').length})</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedRiskLevels.has('low')}
                onChange={() => toggleRiskLevel('low')}
                className="rounded text-green-600"
              />
              <span className="w-3 h-3 rounded-full bg-green-500" />
              <span>低风险 ({initialNodes.filter((n) => n.risk_level === 'low').length})</span>
            </label>
          </div>

          <h3 className="font-semibold text-gray-900 mb-3">节点类型筛选</h3>
          <div className="space-y-2 mb-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedTypes.size === 0}
                onChange={() => setSelectedTypes(new Set())}
                className="rounded"
              />
              <span>全部类型</span>
            </label>
            {nodeTypes.map((type) => (
              <label key={type} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedTypes.has(type)}
                  onChange={() => toggleNodeType(type)}
                  className="rounded"
                />
                <span>{type} ({initialNodes.filter((n) => n.type === type).length})</span>
              </label>
            ))}
          </div>

          <h3 className="font-semibold text-gray-900 mb-3">边风险等级筛选</h3>
          <div className="space-y-2 mb-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedEdgeRiskLevels.has('high')}
                onChange={() => toggleEdgeRiskLevel('high')}
                className="rounded text-red-600"
              />
              <span className="w-6 h-0.5 bg-red-500" />
              <span>高风险边 ({initialEdges.filter((e) => (e.risk_level || 'low') === 'high').length})</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedEdgeRiskLevels.has('medium')}
                onChange={() => toggleEdgeRiskLevel('medium')}
                className="rounded text-yellow-500"
              />
              <span className="w-6 h-0.5 bg-amber-500" />
              <span>中风险边 ({initialEdges.filter((e) => (e.risk_level || 'low') === 'medium').length})</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedEdgeRiskLevels.has('low')}
                onChange={() => toggleEdgeRiskLevel('low')}
                className="rounded text-gray-500"
              />
              <span className="w-6 h-0.5 bg-slate-400" />
              <span>低风险边 ({initialEdges.filter((e) => (e.risk_level || 'low') === 'low').length})</span>
            </label>
          </div>
        </div>
      )}

      <div className="pt-14 h-full">
        <GraphCanvas
          nodes={graphNodes}
          edges={graphEdges}
          layoutType="forceDirected2d"
          edgeInterpolation="curved"
          edgeArrowPosition="end"
          draggable
          animated
          labelType="nodes"
          maxDistance={25000}
          minDistance={500}
        />
      </div>

      {showLegend && !showFilters && (
        <div className="absolute bottom-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg shadow-lg p-3 text-xs z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500" />
              <span>高风险 ({initialNodes.filter((n) => n.risk_level === 'high').length})</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-yellow-500" />
              <span>中风险 ({initialNodes.filter((n) => n.risk_level === 'medium').length})</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-green-500" />
              <span>低风险 ({initialNodes.filter((n) => n.risk_level === 'low').length})</span>
            </div>
            <div className="mt-2 border-t border-gray-200 pt-2" />
            <div className="flex items-center gap-2">
              <span className="w-5 h-0.5 bg-red-500" />
              <span>高风险边</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-0.5 bg-amber-500" />
              <span>中风险边</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-0.5 bg-slate-400" />
              <span>低风险边</span>
            </div>
          </div>
          <p className="text-gray-400 mt-2">滚轮缩放 / 拖拽移动 / 点击节点查看详情</p>
        </div>
      )}
    </div>
  );
}
