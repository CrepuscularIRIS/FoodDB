'use client';

import React, { useState, useEffect, useCallback, Suspense, useRef } from 'react';
import { AlertItem, RiskStats, GraphNode, GraphEdge } from '@/data/types';
import { graphApi } from '@/lib/api';

// 动态导入地图和网络图组件（避免SSR问题）
const ChinaMap = React.lazy(() => import('@/components/ChinaMap'));
const SupplyChainGraph = React.lazy(() => import('@/components/SupplyChainGraph'));

// 地图错误边界组件
function MapErrorFallback({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
      <div className="text-center p-8 bg-gray-800 rounded-xl border border-gray-700 max-w-md">
        <div className="text-4xl mb-4">🗺️</div>
        <h3 className="text-lg font-semibold text-white mb-2">地图加载失败</h3>
        <p className="text-gray-400 text-sm mb-4">{error.message || '无法加载中国地图数据'}</p>
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-white text-sm transition-colors"
        >
          重试加载
        </button>
        <p className="text-gray-500 text-xs mt-4">
          提示：地图数据来自外部CDN，请检查网络连接
        </p>
      </div>
    </div>
  );
}

// 地图加载占位符
function MapLoadingPlaceholder() {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-cyan-400 text-sm">加载中国地图数据...</p>
      </div>
    </div>
  );
}

// API错误提示组件
function ApiErrorFallback({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="h-screen flex items-center justify-center bg-gray-900 text-white">
      <div className="text-center p-8 bg-gray-800 rounded-xl border border-gray-700 max-w-md">
        <div className="text-4xl mb-4">⚠️</div>
        <h3 className="text-lg font-semibold mb-2">数据加载失败</h3>
        <p className="text-gray-400 text-sm mb-4">{error}</p>
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-white text-sm transition-colors"
        >
          重试
        </button>
        <p className="text-gray-500 text-xs mt-4">
          请确保后端服务已启动 (python start_backend.py)
        </p>
      </div>
    </div>
  );
}

// 基础统计卡片组件
interface StatCardProps {
  title: string;
  value: string | number;
  color?: string;
  suffix?: string;
}

function StatCard({ title, value, color = 'cyan', suffix }: StatCardProps) {
  const colorClasses: Record<string, string> = {
    cyan: 'text-cyan-400',
    red: 'text-red-500',
    green: 'text-green-500',
    amber: 'text-amber-400',
    blue: 'text-blue-400',
  };

  return (
    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
      <h3 className="text-gray-400 text-sm mb-1">{title}</h3>
      <div className="flex items-baseline gap-2">
        <p className={`text-3xl font-bold ${colorClasses[color] || colorClasses.cyan}`}>
          {value}
        </p>
        {suffix && <span className="text-xs text-gray-500">{suffix}</span>}
      </div>
    </div>
  );
}

// 预警项组件
interface AlertItemProps {
  alert: AlertItem;
}

function AlertItemCard({ alert }: AlertItemProps) {
  const getTimeAgo = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    return `${Math.floor(diff / 86400000)}天前`;
  };

  const isHigh = alert.level === 'high';
  
  return (
    <div className="p-3 bg-gray-800/30 rounded-lg border border-gray-700/50 hover:bg-gray-800/50 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isHigh ? 'bg-red-500 animate-pulse' : 'bg-amber-400'}`}></span>
          <span className="text-white text-sm font-medium">{alert.title}</span>
        </div>
        <span className="text-xs text-gray-500">{getTimeAgo(alert.timestamp)}</span>
      </div>
      <p className="text-gray-400 text-xs mt-1 ml-4">{alert.message}</p>
      <div className="mt-2 ml-4">
        <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${isHigh ? 'bg-red-500' : 'bg-amber-400'}`}
            style={{ width: `${alert.intensity * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// 风险统计面板组件
function RiskStatsPanel({ stats }: { stats: RiskStats }) {
  const highRiskPercent = ((stats.highRiskNodes / stats.totalNodes) * 100).toFixed(1);
  
  return (
    <div className="bg-gray-900/90 rounded-xl border border-gray-700 p-4">
      <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
        <span className="w-5 h-5 text-blue-400">📊</span>
        风险统计概览
      </h3>
      
      <div className="grid grid-cols-2 gap-3 mb-4">
        <StatCard title="总节点数" value={stats.totalNodes} color="blue" />
        <StatCard title="连接数" value={stats.totalEdges} color="cyan" />
        <StatCard 
          title="高风险企业" 
          value={stats.highRiskNodes} 
          color="red" 
          suffix={`(${highRiskPercent}%)`}
        />
        <StatCard title="活跃预警" value={stats.activeAlerts} color="amber" />
      </div>

      {/* 节点类型分布 */}
      <div className="mb-4">
        <p className="text-xs text-gray-500 mb-2">节点类型分布</p>
        <div className="space-y-2">
          {Object.entries(stats.nodeTypeDistribution).map(([type, count]) => {
            const config: Record<string, { label: string; color: string; icon: string }> = {
              RAW_MILK: { label: '原奶供应商', color: '#10b981', icon: '🥛' },
              PROCESSOR: { label: '乳制品加工厂', color: '#ef4444', icon: '🏭' },
              LOGISTICS: { label: '物流公司', color: '#3b82f6', icon: '🚚' },
              WAREHOUSE: { label: '仓储中心', color: '#06b6d4', icon: '🏪' },
              DISTRIBUTOR: { label: '经销商', color: '#8b5cf6', icon: '📦' },
              RETAILER: { label: '零售终端', color: '#f59e0b', icon: '🏪' },
            };
            const cfg = config[type];
            return (
              <div key={type} className="flex items-center gap-2">
                <span className="text-sm">{cfg?.icon}</span>
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-400">{cfg?.label}</span>
                    <span className="text-white">{count}</span>
                  </div>
                  <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${(count / stats.totalNodes) * 100}%`,
                        backgroundColor: cfg?.color,
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// 预警面板组件
function AlertPanel({ alerts }: { alerts: AlertItem[] }) {
  const highRiskCount = alerts.filter(a => a.level === 'high').length;
  const mediumRiskCount = alerts.filter(a => a.level === 'medium').length;
  const displayAlerts = alerts.slice(0, 5);

  return (
    <div className="bg-gray-900/90 rounded-xl border border-gray-700 overflow-hidden">
      {/* 头部 */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5">🔔</span>
            <h3 className="text-white font-semibold">实时预警</h3>
            {alerts.length > 0 && (
              <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full">
              {highRiskCount} 高
            </span>
            <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded-full">
              {mediumRiskCount} 中
            </span>
          </div>
        </div>

        {/* 统计条 */}
        <div className="flex h-1.5 rounded-full overflow-hidden bg-gray-800">
          <div
            className="bg-red-500 transition-all duration-500"
            style={{ width: `${(highRiskCount / Math.max(alerts.length, 1)) * 100}%` }}
          />
          <div
            className="bg-amber-500 transition-all duration-500"
            style={{ width: `${(mediumRiskCount / Math.max(alerts.length, 1)) * 100}%` }}
          />
        </div>
      </div>

      {/* 预警列表 */}
      <div className="max-h-64 overflow-y-auto p-4 space-y-3">
        {displayAlerts.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-gray-500 text-sm">暂无预警信息</p>
          </div>
        ) : (
          displayAlerts.map((alert) => (
            <AlertItemCard key={alert.id} alert={alert} />
          ))
        )}
      </div>

      {/* 底部 */}
      {alerts.length > 5 && (
        <div className="p-3 border-t border-gray-700 text-center">
          <span className="text-sm text-blue-400">
            共 {alerts.length} 条预警
          </span>
        </div>
      )}
    </div>
  );
}

export default function SimpleDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<Error | null>(null);
  const [graphError, setGraphError] = useState<Error | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [stats, setStats] = useState<RiskStats | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'map' | 'graph'>('map');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);
  const [dataSource, setDataSource] = useState<'api' | 'cache'>('api');
  
  // WebSocket引用
  const wsRef = useRef<WebSocket | null>(null);
  
  // 筛选器状态
  const [filters, setFilters] = useState({
    nodeTypes: [] as string[],
    riskLevels: [] as string[],
  });
  const [showFilters, setShowFilters] = useState(false);

  // 路径追踪函数
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

  // 清除高亮路径当选择节点变化时
  useEffect(() => {
    if (!selectedNode) {
      setHighlightedPath([]);
    }
  }, [selectedNode]);

  // 加载图数据
  const loadGraphData = useCallback(async (retryCount = 0) => {
    setLoading(true);
    setError(null);
    
    try {
      // 并行获取图数据和统计数据
      const [graphResult, statsResult] = await Promise.all([
        graphApi.getGraphData(),
        graphApi.getStats(),
      ]);
      
      if (graphResult.success && graphResult.data && statsResult.success && statsResult.data) {
        setNodes(graphResult.data.nodes);
        setEdges(graphResult.data.edges);
        setStats(statsResult.data);
        setAlerts(statsResult.data.topRiskyNodes?.map((node: any, index: number) => ({
          id: `alert_${index}`,
          level: node.riskScore > 0.8 ? 'high' : 'medium',
          title: `${node.district || '未知地区'}：${node.name}`,
          message: `风险评分: ${(node.riskScore * 100).toFixed(1)}% | 类型: ${node.type}`,
          timestamp: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000).toISOString(),
          intensity: node.riskScore,
          nodeId: node.id,
        })).slice(0, 20) || []);
        setDataSource('api');
        console.log(`[Dashboard] 从API加载数据: ${graphResult.data.nodes.length}节点, ${graphResult.data.edges.length}边`);
      } else {
        const errorMsg = graphResult.error || statsResult.error || '加载数据失败';
        throw new Error(errorMsg);
      }
    } catch (err: any) {
      console.error('[Dashboard] 加载数据失败:', err);
      setError(err.message || '无法连接到后端服务');
      
      // 重试机制
      if (retryCount < 3) {
        console.log(`[Dashboard] ${retryCount + 1}秒后重试...`);
        setTimeout(() => loadGraphData(retryCount + 1), (retryCount + 1) * 1000);
        return;
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // 初始加载
  useEffect(() => {
    loadGraphData();
  }, [loadGraphData]);

  // WebSocket连接（用于实时更新）
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    
    const connectWebSocket = () => {
      try {
        ws = graphApi.connectWebSocket(
          (data) => {
            // 处理WebSocket消息
            if (data.type === 'initial_data') {
              console.log('[WebSocket] 已连接，收到初始数据');
            } else if (data.type === 'nodes') {
              setNodes(data.nodes);
            } else if (data.type === 'edges') {
              setEdges(data.edges);
            }
          },
          (error) => {
            console.error('[WebSocket] 连接错误:', error);
          }
        );
        
        wsRef.current = ws;
        reconnectAttempts = 0;
      } catch (err) {
        console.error('[WebSocket] 连接失败:', err);
      }
    };
    
    // 延迟连接WebSocket，确保HTTP数据先加载
    const timer = setTimeout(() => {
      connectWebSocket();
    }, 2000);
    
    return () => {
      clearTimeout(timer);
      if (ws) {
        ws.close();
      }
    };
  }, []);

  // 模拟实时预警更新
  useEffect(() => {
    const interval = setInterval(() => {
      setAlerts(prev => {
        if (Math.random() > 0.7 && prev.length > 0) {
          const provinces = ['内蒙古', '黑龙江', '河北', '山东', '江苏', '广东', '四川', '陕西'];
          const province = provinces[Math.floor(Math.random() * provinces.length)];
          const newAlert: AlertItem = {
            id: `alert_${Date.now()}`,
            level: Math.random() > 0.5 ? 'high' : 'medium',
            title: `新预警 · ${province}`,
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

  if (error) {
    return <ApiErrorFallback error={error} onRetry={() => loadGraphData()} />;
  }

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">正在从后端加载数据...</p>
          <p className="text-gray-500 text-sm mt-2">768节点 · 1078边</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-gray-900 text-white flex overflow-hidden">
      {/* 左侧边栏 */}
      <div className="w-80 flex-shrink-0 border-r border-gray-800 overflow-hidden">
        <div className="h-full overflow-y-auto p-4 space-y-4">
          {stats && <RiskStatsPanel stats={stats} />}
          <AlertPanel alerts={alerts} />
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* 顶部导航栏 */}
        <div className="h-14 bg-gray-900/95 border-b border-gray-800 flex items-center justify-between px-4 z-20">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold">乳制品供应链风险监控</h1>
            
            {/* 标签切换 */}
            <div className="flex bg-gray-800/50 rounded-lg p-1 ml-4">
              <button
                onClick={() => setActiveTab('map')}
                className={`px-3 py-1.5 rounded-md text-sm transition-all ${
                  activeTab === 'map'
                    ? 'bg-cyan-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                地图视图
              </button>
              <button
                onClick={() => setActiveTab('graph')}
                className={`px-3 py-1.5 rounded-md text-sm transition-all ${
                  activeTab === 'graph'
                    ? 'bg-cyan-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                网络图
              </button>
              <button
                onClick={() => setActiveTab('overview')}
                className={`px-3 py-1.5 rounded-md text-sm transition-all ${
                  activeTab === 'overview'
                    ? 'bg-cyan-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                概览
              </button>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2 py-0.5 rounded ${dataSource === 'api' ? 'bg-green-600/20 text-green-400' : 'bg-amber-600/20 text-amber-400'}`}>
              {dataSource === 'api' ? '● 后端数据' : '● 缓存数据'}
            </span>
            <span className="text-sm text-gray-400">
              {nodes.length}节点 · {edges.length}连接 · 全国覆盖
            </span>
            <span className="px-2 py-0.5 bg-cyan-600/20 text-cyan-400 text-xs rounded-full">
              简化版 v2.0
            </span>
          </div>
        </div>

        {/* 主内容 */}
        <div className="flex-1 relative overflow-hidden">
          {activeTab === 'map' && (
            <div className="absolute inset-0">
              <Suspense fallback={<MapLoadingPlaceholder />}>
                {mapError ? (
                  <MapErrorFallback 
                    error={mapError} 
                    onRetry={() => setMapError(null)} 
                  />
                ) : (
                  <ChinaMap />
                )}
              </Suspense>
              
              {/* 地图上的浮动信息 */}
              <div className="absolute bottom-4 left-4 z-10 bg-gray-900/80 backdrop-blur-sm p-4 rounded-xl border border-gray-700">
                <h4 className="text-white font-medium mb-2">地图数据</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">节点数:</span>
                    <span className="text-cyan-400">{nodes.length}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">连接数:</span>
                    <span className="text-cyan-400">{edges.length}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-gray-400">覆盖省份:</span>
                    <span className="text-cyan-400">34</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'graph' && (
            <div className="absolute inset-0">
              {/* 筛选器面板 */}
              <div className="absolute top-4 left-4 z-10 bg-gray-900/90 backdrop-blur-sm p-4 rounded-xl border border-gray-700 w-56">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-white font-medium text-sm">筛选器</h4>
                  <button 
                    onClick={() => setShowFilters(!showFilters)}
                    className="text-gray-400 hover:text-white text-xs"
                  >
                    {showFilters ? '收起' : '展开'}
                  </button>
                </div>
                
                {showFilters && (
                  <div className="space-y-3">
                    {/* 节点类型筛选 */}
                    <div>
                      <p className="text-xs text-gray-500 mb-2">节点类型</p>
                      <div className="space-y-1">
                        {['RAW_MILK', 'PROCESSOR', 'LOGISTICS', 'WAREHOUSE', 'DISTRIBUTOR', 'RETAILER'].map((type) => {
                          const config: Record<string, { label: string; color: string }> = {
                            RAW_MILK: { label: '原奶供应商', color: '#10b981' },
                            PROCESSOR: { label: '加工厂', color: '#ef4444' },
                            LOGISTICS: { label: '物流', color: '#3b82f6' },
                            WAREHOUSE: { label: '仓储', color: '#06b6d4' },
                            DISTRIBUTOR: { label: '经销商', color: '#8b5cf6' },
                            RETAILER: { label: '零售', color: '#f59e0b' },
                          };
                          const cfg = config[type];
                          const isSelected = filters.nodeTypes.includes(type);
                          return (
                            <label key={type} className="flex items-center gap-2 cursor-pointer hover:bg-gray-800/50 p-1 rounded">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setFilters(prev => ({ ...prev, nodeTypes: [...prev.nodeTypes, type] }));
                                  } else {
                                    setFilters(prev => ({ ...prev, nodeTypes: prev.nodeTypes.filter(t => t !== type) }));
                                  }
                                }}
                                className="w-3 h-3 rounded border-gray-600"
                              />
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cfg.color }}></span>
                              <span className="text-xs text-gray-300">{cfg.label}</span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                    
                    {/* 风险等级筛选 */}
                    <div>
                      <p className="text-xs text-gray-500 mb-2">风险等级</p>
                      <div className="space-y-1">
                        {[
                          { key: 'high', label: '高风险', color: '#ef4444' },
                          { key: 'medium', label: '中风险', color: '#f59e0b' },
                          { key: 'low', label: '低风险', color: '#10b981' },
                        ].map(({ key, label, color }) => {
                          const isSelected = filters.riskLevels.includes(key);
                          return (
                            <label key={key} className="flex items-center gap-2 cursor-pointer hover:bg-gray-800/50 p-1 rounded">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setFilters(prev => ({ ...prev, riskLevels: [...prev.riskLevels, key] }));
                                  } else {
                                    setFilters(prev => ({ ...prev, riskLevels: prev.riskLevels.filter(r => r !== key) }));
                                  }
                                }}
                                className="w-3 h-3 rounded border-gray-600"
                              />
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }}></span>
                              <span className="text-xs text-gray-300">{label}</span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                    
                    {/* 清除筛选 */}
                    {(filters.nodeTypes.length > 0 || filters.riskLevels.length > 0) && (
                      <button
                        onClick={() => setFilters({ nodeTypes: [], riskLevels: [] })}
                        className="w-full py-1.5 text-xs text-gray-400 hover:text-white bg-gray-800/50 hover:bg-gray-700/50 rounded transition-colors"
                      >
                        清除筛选
                      </button>
                    )}
                  </div>
                )}
                
                {/* 筛选统计 */}
                <div className="mt-3 pt-3 border-t border-gray-700 text-xs text-gray-500">
                  已筛选: {nodes.filter(n => {
                    if (filters.nodeTypes.length > 0 && !filters.nodeTypes.includes(n.type)) return false;
                    if (filters.riskLevels.length > 0 && !filters.riskLevels.includes(n.riskLevel)) return false;
                    return true;
                  }).length} / {nodes.length} 节点
                </div>
              </div>

              <Suspense fallback={<MapLoadingPlaceholder />}>
                {graphError ? (
                  <MapErrorFallback 
                    error={graphError} 
                    onRetry={() => setGraphError(null)} 
                  />
                ) : nodes.length > 0 ? (
                  <SupplyChainGraph
                    nodes={nodes.filter(n => {
                      if (filters.nodeTypes.length > 0 && !filters.nodeTypes.includes(n.type)) return false;
                      if (filters.riskLevels.length > 0 && !filters.riskLevels.includes(n.riskLevel)) return false;
                      return true;
                    })}
                    edges={edges}
                    filters={{
                      nodeTypes: [],
                      riskLevels: [],
                      minScale: 0,
                      maxScale: 10000,
                      districts: [],
                    }}
                    selectedNode={selectedNode}
                    onNodeSelect={setSelectedNode}
                    onNodeHover={setHoveredNode}
                    highlightedPath={highlightedPath}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
                    <div className="text-center">
                      <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4"></div>
                      <p className="text-cyan-400 text-sm">加载网络图数据...</p>
                    </div>
                  </div>
                )}
              </Suspense>
              
              {/* 选中节点信息 */}
              {selectedNode && (
                <div className="absolute top-4 right-4 z-10 bg-gray-900/90 backdrop-blur-sm p-4 rounded-xl border border-gray-700 w-72">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-white font-medium">节点详情</h4>
                    <button 
                      onClick={() => setSelectedNode(null)}
                      className="text-gray-400 hover:text-white"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="space-y-2 text-sm mb-4">
                    <div className="flex justify-between">
                      <span className="text-gray-400">名称:</span>
                      <span className="text-white truncate max-w-[140px]" title={selectedNode.name}>{selectedNode.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">类型:</span>
                      <span className="text-white">{selectedNode.type}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">风险等级:</span>
                      <span className={selectedNode.riskLevel === 'high' ? 'text-red-400' : selectedNode.riskLevel === 'medium' ? 'text-amber-400' : 'text-green-400'}>
                        {selectedNode.riskLevel === 'high' ? '高风险' : selectedNode.riskLevel === 'medium' ? '中风险' : '低风险'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">风险评分:</span>
                      <span className="text-white">{(selectedNode.riskScore * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">省份:</span>
                      <span className="text-white">{selectedNode.district}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">规模:</span>
                      <span className="text-white">{selectedNode.scale.toFixed(0)}</span>
                    </div>
                  </div>
                  
                  {/* 路径追踪按钮 */}
                  <div className="border-t border-gray-700 pt-3">
                    <p className="text-xs text-gray-500 mb-2">路径追踪</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleTracePath('upstream')}
                        className="flex-1 px-3 py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 rounded-lg text-xs transition-colors border border-blue-600/30"
                      >
                        ← 上游
                      </button>
                      <button
                        onClick={() => handleTracePath('downstream')}
                        className="flex-1 px-3 py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 rounded-lg text-xs transition-colors border border-blue-600/30"
                      >
                        下游 →
                      </button>
                    </div>
                    {highlightedPath.length > 0 && (
                      <div className="mt-2 text-xs text-cyan-400">
                        追踪到 {highlightedPath.length} 个节点
                        <button 
                          onClick={() => setHighlightedPath([])}
                          className="ml-2 text-gray-400 hover:text-white"
                        >
                          清除
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          {activeTab === 'overview' && (
            <div className="p-8 overflow-auto h-full">
              <div className="bg-gray-800 p-6 rounded-lg mb-6">
                <h2 className="text-xl font-semibold mb-4">系统状态</h2>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <p className="text-green-400 font-medium">✓ 前端运行正常</p>
                  </div>
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <p className={`font-medium ${dataSource === 'api' ? 'text-green-400' : 'text-amber-400'}`}>
                      {dataSource === 'api' ? '✓ 后端数据连接正常' : '⚠ 使用缓存数据'}
                    </p>
                  </div>
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <p className="text-green-400 font-medium">✓ 图数据已加载</p>
                    <p className="text-xs text-gray-400 mt-1">{nodes.length}节点 · {edges.length}边</p>
                  </div>
                </div>
              </div>

              <div className="bg-gray-800 p-6 rounded-lg">
                <h2 className="text-xl font-semibold mb-4">功能模块</h2>
                <p className="text-gray-400 mb-4">当前已加载的功能：</p>
                <ul className="space-y-2 text-gray-300">
                  <li className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    风险统计概览 - 显示节点、连接、风险企业等关键指标
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    实时预警面板 - 显示高风险和中风险预警信息
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    中国地图 - 显示全国供应链地理分布
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    供应链网络图 - 显示节点连接关系
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    路径追踪 - 支持上下游供应链追溯
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    节点详情面板 - 点击查看企业详细信息
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    筛选器 - 按节点类型和风险等级筛选
                  </li>
                </ul>
              </div>

              <div className="bg-gray-800 p-6 rounded-lg mt-6">
                <h2 className="text-xl font-semibold mb-4">数据源信息</h2>
                <div className="space-y-2 text-gray-300">
                  <p><span className="text-gray-400">数据来源:</span> {dataSource === 'api' ? '后端API (实时)' : '本地缓存'}</p>
                  <p><span className="text-gray-400">节点总数:</span> {nodes.length}</p>
                  <p><span className="text-gray-400">边总数:</span> {edges.length}</p>
                  <p><span className="text-gray-400">API地址:</span> {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
