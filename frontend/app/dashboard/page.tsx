'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { GraphNode, GraphEdge, FilterCriteria, AlertItem, RiskStats } from '@/data/types';
import { mockGraphData, mockAlerts, mockRiskStats } from '@/data/mockData';
import { normalizeRegion } from '@/lib/region';

// 动态导入组件（避免SSR问题）
const SupplyChainGraph = dynamic(() => import('@/components/SupplyChainGraph'), { ssr: false });
const ChinaMap = dynamic(() => import('@/components/ChinaMap'), { ssr: false });
const RiskHeatmap = dynamic(() => import('@/components/RiskHeatmap'), { ssr: false });
const NodeDetailPanel = dynamic(() => import('@/components/NodeDetailPanel'), { ssr: false });
const AlertPanel = dynamic(() => import('@/components/AlertPanel'), { ssr: false });
const FilterPanel = dynamic(() => import('@/components/FilterPanel'), { ssr: false });
const RiskStatsPanel = dynamic(() => import('@/components/RiskStatsPanel'), { ssr: false });
const EnterpriseListPanel = dynamic(() => import('@/components/EnterpriseListPanel'), { ssr: false });
const GraphLegend = dynamic(() => import('@/components/GraphLegend'), { ssr: false });

import { MapPinIcon, PresentationChartLineIcon, ListBulletIcon, FunnelIcon } from '@heroicons/react/24/outline';

type ViewMode = 'graph' | 'heatmap' | 'list';

export default function Dashboard() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [stats, setStats] = useState<RiskStats | null>(null);
  const [loading, setLoading] = useState(true);
  
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('graph');
  const [showSidebar] = useState(true);
  const [showFilters, setShowFilters] = useState(true);
  const [incomingKeywords, setIncomingKeywords] = useState('');
  
  const [filters, setFilters] = useState<FilterCriteria>({
    nodeTypes: [],
    riskLevels: [],
    minScale: 0,
    maxScale: 10000,
    districts: ['上海市'],
  });

  // 读取 URL 参数（关键词 + 区域）
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q') || '';
    const district = normalizeRegion(params.get('district'));
    if (q) setIncomingKeywords(q);
    if (district) {
      setFilters(prev => ({ ...prev, districts: [district] }));
    }
  }, []);

  // 读取首页研判后的自动联动筛选（本地缓存，30分钟有效）
  useEffect(() => {
    try {
      const raw = localStorage.getItem('dashboard_auto_districts');
      const tsRaw = localStorage.getItem('dashboard_auto_districts_ts');
      if (!raw || !tsRaw) return;

      const ts = Number(tsRaw);
      if (!Number.isFinite(ts) || Date.now() - ts > 30 * 60 * 1000) return;

      const cachedKeywords = localStorage.getItem('dashboard_auto_keywords') || '';
      if (!incomingKeywords && cachedKeywords) {
        setIncomingKeywords(cachedKeywords);
      }

      const districts = JSON.parse(raw)
        .map((d: string) => normalizeRegion(d))
        .filter(Boolean);

      if (Array.isArray(districts) && districts.length > 0) {
        setFilters(prev => ({ ...prev, districts: districts as string[] }));
      }
    } catch (e) {
      console.warn('读取大屏联动筛选失败:', e);
    }
  }, [incomingKeywords]);

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setTimeout(() => {
        setNodes(mockGraphData.nodes);
        setEdges(mockGraphData.edges);
        setAlerts(mockAlerts);
        setStats(mockRiskStats);
        setLoading(false);
      }, 800);
    };
    
    loadData();
    
    // 模拟实时预警更新
    const interval = setInterval(() => {
      setAlerts(prev => {
        if (Math.random() > 0.7) {
          const provinces = ['内蒙古', '黑龙江', '河北', '山东', '江苏', '广东', '四川', '陕西'];
          const districts = provinces.map(p => p + (p.includes('市') ? '' : '省'));
          const newAlert: AlertItem = {
            id: `alert_${Date.now()}`,
            level: Math.random() > 0.5 ? 'high' : 'medium',
            title: `新预警 · ${randomChoice(districts)}`,
            message: `检测到异常风险信号 | 强度 ${(Math.random() * 0.3 + 0.7).toFixed(3)}`,
            timestamp: new Date().toISOString(),
            intensity: Math.random() * 0.3 + 0.7,
            nodeId: `node_${Math.floor(Math.random() * 768)}`,
          };
          return [newAlert, ...prev].slice(0, 50);
        }
        return prev;
      });
    }, 15000);
    
    return () => clearInterval(interval);
  }, []);

  // 获取所有省份作为筛选选项
  const districts = useMemo(() => {
    const districtSet = new Set(nodes.map(n => n.district));
    return Array.from(districtSet).sort();
  }, [nodes]);

  useEffect(() => {
    setFilters(prev => {
      if (prev.districts.length === 0 || districts.length === 0) return prev;
      const normalized = prev.districts
        .map(d => normalizeRegion(d) || d)
        .filter(d => districts.includes(d));
      if (normalized.length === prev.districts.length && normalized.every((d, i) => d === prev.districts[i])) {
        return prev;
      }
      return { ...prev, districts: normalized };
    });
  }, [districts]);

  const handleTracePath = useCallback((direction: 'upstream' | 'downstream') => {
    if (!selectedNode) return;
    
    const visited = new Set<string>([selectedNode.id]);
    const queue = [selectedNode.id];
    const path = [selectedNode.id];
    
    let hops = 0;
    const maxHops = 3;
    
    while (queue.length > 0 && hops < maxHops) {
      const size = queue.length;
      for (let i = 0; i < size; i++) {
        const current = queue.shift()!;
        
        const neighbors = edges
          .filter(e => direction === 'upstream' ? e.target === current : e.source === current)
          .map(e => direction === 'upstream' ? e.source : e.target);
        
        neighbors.forEach(neighbor => {
          if (!visited.has(neighbor)) {
            visited.add(neighbor);
            queue.push(neighbor);
            path.push(neighbor);
          }
        });
      }
      hops++;
    }
    
    setHighlightedPath(path);
  }, [selectedNode, edges]);

  useEffect(() => {
    if (!selectedNode) {
      setHighlightedPath([]);
    }
  }, [selectedNode]);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">加载全国供应链数据...</p>
          <p className="text-gray-500 text-sm mt-2">768个节点 · 1078条连接 · 全国覆盖</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative left-1/2 right-1/2 w-screen -translate-x-1/2 h-[calc(100vh-180px)] bg-gray-900 flex overflow-hidden border-y border-gray-800">
      {/* 左侧边栏 */}
      <div className={`${showSidebar ? 'w-80' : 'w-0'} transition-all duration-300 flex-shrink-0 border-r border-gray-800 overflow-hidden`}>
        <div className="h-full overflow-y-auto p-4 space-y-4">
          <RiskStatsPanel stats={stats!} />
          <AlertPanel alerts={alerts} maxDisplay={5} />
          <GraphLegend />
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部导航栏 */}
        <div className="h-14 bg-gray-900/95 backdrop-blur-md border-b border-gray-800 flex items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-lg transition-colors ${showFilters ? 'bg-cyan-600/20 text-cyan-400' : 'text-gray-400 hover:text-white hover:bg-gray-800'}`}
              title="筛选器"
            >
              <FunnelIcon className="w-5 h-5" />
            </button>
            
            <div className="h-6 w-px bg-gray-700"></div>
            
            <div className="flex bg-gray-800/50 rounded-lg p-1">
              {[
                { key: 'graph', icon: PresentationChartLineIcon, label: '网络图' },
                { key: 'heatmap', icon: MapPinIcon, label: '热力图' },
                { key: 'list', icon: ListBulletIcon, label: '列表' },
              ].map(({ key, icon: Icon, label }) => (
                <button
                  key={key}
                  onClick={() => setViewMode(key as ViewMode)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all ${
                    viewMode === key
                      ? 'bg-cyan-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {incomingKeywords && (
              <span className="px-2 py-0.5 bg-violet-600/20 text-violet-300 text-xs rounded-full max-w-[28vw] truncate">
                关键词: {incomingKeywords}
              </span>
            )}
            <span className="text-sm text-gray-400">
              乳制品供应链风险监控系统
            </span>
            <span className="px-2 py-0.5 bg-cyan-600/20 text-cyan-400 text-xs rounded-full">
              全国版 v3.0
            </span>
          </div>
        </div>

        {/* 地图/图表区域 */}
        <div className="flex-1 relative overflow-hidden">
          {viewMode === 'graph' && (
            <>
              <div className="absolute inset-0 z-10">
                <SupplyChainGraph
                  nodes={nodes}
                  edges={edges}
                  filters={filters}
                  selectedNode={selectedNode}
                  onNodeSelect={setSelectedNode}
                  onNodeHover={setHoveredNode}
                  highlightedPath={highlightedPath}
                />
              </div>
            </>
          )}

          {viewMode === 'heatmap' && (
            <>
              <ChinaMap />
              <div className="absolute inset-0 z-10">
                <RiskHeatmap nodes={nodes} />
              </div>
            </>
          )}

          {viewMode === 'list' && (
            <div className="h-full p-4 overflow-auto">
              <EnterpriseListPanel
                nodes={nodes}
                selectedNode={selectedNode}
                onSelectNode={setSelectedNode}
              />
            </div>
          )}

          {/* 右侧筛选面板 */}
          <div
            className={`absolute top-4 right-4 z-20 w-80 max-w-[35vw] transition-all duration-300 ${
              showFilters ? 'translate-x-0 opacity-100' : 'translate-x-[120%] opacity-0 pointer-events-none'
            }`}
          >
            <div className="max-h-[calc(100vh-260px)] overflow-y-auto pr-1 pb-6">
              <FilterPanel filters={filters} onFilterChange={setFilters} districts={districts} />
            </div>
          </div>
        </div>
      </div>

      {/* 节点详情面板 */}
      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          onTracePath={handleTracePath}
        />
      )}
    </div>
  );
}

// 辅助函数
function randomChoice<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}
