'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as echarts from 'echarts';
import { subgraphApi } from '@/lib/api';
import type { SubgraphNode, SubgraphResponse, LLMAssessResponse } from '@/types';

// ------- constants -------
const CHINA_GEOJSON_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';

const RISK_COLOR: Record<string, string> = {
  high: '#ef4444',
  medium: '#f97316',
  low: '#22c55e',
};
const RISK_LABEL: Record<string, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
};
const riskColor = (lvl: string) => RISK_COLOR[lvl] ?? '#9ca3af';

// ------- helpers -------
interface GeoNode {
  node: SubgraphNode;
  coord: [number, number]; // [lng, lat]
}

function nodesWithCoords(nodes: SubgraphNode[]): GeoNode[] {
  return nodes
    .filter((n) => n.longitude !== null && n.latitude !== null)
    .map((n) => ({ node: n, coord: [n.longitude!, n.latitude!] }));
}

// Build scatter series data
function buildScatterData(geoNodes: GeoNode[], selectedId: string | null) {
  return geoNodes.map(({ node, coord }) => ({
    name: node.name,
    value: [...coord, node.risk_score],
    symbolSize: Math.max(6, 6 + node.risk_score * 28),
    itemStyle: {
      color: riskColor(node.risk_level),
      borderColor: node.node_id === selectedId ? '#fff' : 'transparent',
      borderWidth: node.node_id === selectedId ? 2 : 0,
      opacity: 0.85,
    },
    _node: node,
  }));
}

// Build lines series data (edges that connect two geo-located nodes)
function buildLinesData(
  subgraph: SubgraphResponse,
  coordMap: Map<string, [number, number]>,
  showOnlyRisky: boolean
) {
  const edges = showOnlyRisky
    ? subgraph.edges.filter((e) => e.risk_positive_count > 0)
    : subgraph.edges;

  return edges
    .filter((e) => coordMap.has(e.source) && coordMap.has(e.target))
    .map((e) => ({
      coords: [coordMap.get(e.source)!, coordMap.get(e.target)!],
      lineStyle: {
        width: e.risk_positive_count > 0 ? Math.min(3, 1 + e.risk_positive_count) : 0.5,
        color: e.risk_positive_count > 0 ? '#f97316' : 'rgba(148,163,184,0.3)',
        opacity: 0.5,
      },
    }));
}

// ------- component -------
export default function LLMSubgraphMapView() {
  const mapRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const geoLoadedRef = useRef(false);

  // query params
  const [region, setRegion] = useState('上海');
  const [timeWindow, setTimeWindow] = useState(30);
  const [kHop, setKHop] = useState(2);
  const [seedNode, setSeedNode] = useState('');
  const [showOnlyRisky, setShowOnlyRisky] = useState(false);

  // data
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  // selected node
  const [selectedNode, setSelectedNode] = useState<SubgraphNode | null>(null);

  // LLM assess
  const [llmResult, setLlmResult] = useState<LLMAssessResponse | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [showLlm, setShowLlm] = useState(false);

  // --- init chart ---
  useEffect(() => {
    if (!mapRef.current) return;
    const chart = echarts.init(mapRef.current, 'dark', { renderer: 'canvas' });
    chartRef.current = chart;

    // load GeoJSON
    fetch(CHINA_GEOJSON_URL)
      .then((r) => r.json())
      .then((geo) => {
        echarts.registerMap('china_llm', geo);
        geoLoadedRef.current = true;
        renderChart(chart, null, false);
      })
      .catch(console.error);

    const resize = () => chart.resize();
    window.addEventListener('resize', resize);

    chart.on('click', (params: any) => {
      if (params.seriesType === 'scatter' && params.data?._node) {
        setSelectedNode(params.data._node as SubgraphNode);
      }
    });

    return () => {
      window.removeEventListener('resize', resize);
      chart.dispose();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- re-render when data changes ---
  useEffect(() => {
    if (!chartRef.current || !geoLoadedRef.current) return;
    renderChart(chartRef.current, subgraph, showOnlyRisky);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subgraph, showOnlyRisky, selectedNode]);

  function renderChart(
    chart: echarts.ECharts,
    sg: SubgraphResponse | null,
    onlyRisky: boolean
  ) {
    const geoNodes = sg ? nodesWithCoords(sg.nodes) : [];
    const coordMap = new Map<string, [number, number]>(
      geoNodes.map(({ node, coord }) => [node.node_id, coord])
    );
    const scatterData = buildScatterData(geoNodes, selectedNode?.node_id ?? null);
    const linesData = sg ? buildLinesData(sg, coordMap, onlyRisky) : [];

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      geo: {
        map: 'china_llm',
        roam: true,
        zoom: 8,
        center: [121.47, 31.23], // Shanghai
        label: { show: false },
        itemStyle: {
          areaColor: 'rgba(15,35,70,0.7)',
          borderColor: '#1e3a5f',
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: {
            areaColor: 'rgba(30,80,150,0.8)',
            borderColor: '#00f2ff',
          },
        },
      },
      series: [
        {
          type: 'lines',
          coordinateSystem: 'geo',
          data: linesData,
          polyline: false,
          large: true,
          effect: { show: false },
          zlevel: 1,
        },
        {
          type: 'scatter',
          coordinateSystem: 'geo',
          data: scatterData,
          zlevel: 2,
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              formatter: (p: any) => p.name?.slice(0, 12) ?? '',
              color: '#fff',
              fontSize: 11,
            },
          },
          tooltip: {
            trigger: 'item',
            formatter: (p: any) => {
              const n: SubgraphNode = p.data._node;
              if (!n) return '';
              return `<b>${n.name}</b><br/>
类型: ${n.node_type}<br/>
风险: <span style="color:${riskColor(n.risk_level)}">${RISK_LABEL[n.risk_level] ?? n.risk_level}</span> (${(n.risk_score * 100).toFixed(1)}%)<br/>
规模: ${n.enterprise_scale}`;
            },
          },
        },
      ],
      tooltip: { trigger: 'item' },
    };

    chart.setOption(option, true);
  }

  // --- fetch subgraph ---
  const fetchSubgraph = useCallback(async () => {
    setLoading(true);
    setQueryError(null);
    setSelectedNode(null);
    setLlmResult(null);

    const res = await subgraphApi.getSubgraph({
      region: region || undefined,
      time_window: timeWindow,
      k_hop: kHop,
      seed_node: seedNode.trim() || undefined,
      max_nodes: 300,
      max_edges: 600,
    });
    setLoading(false);
    if (res.success && res.data) setSubgraph(res.data);
    else setQueryError(res.error ?? '请求失败');
  }, [region, timeWindow, kHop, seedNode]);

  // --- LLM assess ---
  const triggerLlm = useCallback(
    async (seedId?: string) => {
      setLlmLoading(true);
      setLlmError(null);
      setShowLlm(true);
      const res = await subgraphApi.llmAssess({
        region: region || undefined,
        time_window: timeWindow,
        k_hop: kHop,
        seed_node: seedId ?? (seedNode.trim() || undefined),
        use_mock_llm: false,
      });
      setLlmLoading(false);
      if (res.success && res.data) setLlmResult(res.data);
      else setLlmError(res.error ?? 'LLM 评估失败');
    },
    [region, timeWindow, kHop, seedNode]
  );

  const nodes = subgraph?.nodes ?? [];
  const highCnt = nodes.filter((n) => n.risk_level === 'high').length;
  const medCnt = nodes.filter((n) => n.risk_level === 'medium').length;
  const geoNodeCount = nodes.filter((n) => n.longitude !== null).length;

  return (
    <div className="absolute inset-0 flex flex-col overflow-hidden">
      {/* grid background */}
      <div
        className="absolute inset-0 pointer-events-none z-0"
        style={{
          background: 'radial-gradient(ellipse at center, #0a1628 0%, #050a10 100%)',
          backgroundImage:
            'linear-gradient(rgba(0,242,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,242,255,0.03) 1px,transparent 1px)',
          backgroundSize: '50px 50px',
        }}
      />

      {/* map */}
      <div ref={mapRef} className="absolute inset-0 z-[1]" />

      {/* ── Filter controls (floating top-left) ── */}
      <div className="absolute top-3 left-3 z-20 bg-gray-900/90 border border-gray-700 rounded-xl p-3 w-64 backdrop-blur-sm">
        <div className="text-xs font-bold text-cyan-400 mb-2 tracking-wider uppercase">
          🕸️ LLM 子图过滤
        </div>

        <div className="space-y-2 text-xs text-gray-300">
          {/* region */}
          <div className="flex items-center gap-2">
            <span className="w-14 flex-shrink-0">区域</span>
            <input
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-0.5 text-xs text-white focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* time_window */}
          <div>
            <div className="flex justify-between mb-0.5">
              <span>时间窗口</span>
              <span className="text-cyan-400">{timeWindow} 天</span>
            </div>
            <input
              type="range" min={7} max={365} step={7} value={timeWindow}
              onChange={(e) => setTimeWindow(Number(e.target.value))}
              className="w-full accent-cyan-500"
            />
          </div>

          {/* k_hop */}
          <div>
            <div className="flex justify-between mb-0.5">
              <span>k-hop 深度</span>
              <span className="text-cyan-400">{kHop}</span>
            </div>
            <input
              type="range" min={1} max={5} step={1} value={kHop}
              onChange={(e) => setKHop(Number(e.target.value))}
              className="w-full accent-cyan-500"
            />
          </div>

          {/* seed_node */}
          <div className="flex items-center gap-2">
            <span className="w-14 flex-shrink-0">种子节点</span>
            <input
              type="text"
              value={seedNode}
              onChange={(e) => setSeedNode(e.target.value)}
              placeholder="名称 / ID"
              className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-0.5 text-xs text-white focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* risky edge toggle */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox" checked={showOnlyRisky}
              onChange={(e) => setShowOnlyRisky(e.target.checked)}
              className="accent-orange-500"
            />
            <span>仅显示风险连线</span>
          </label>
        </div>

        <button
          onClick={fetchSubgraph}
          disabled={loading}
          className={`mt-2 w-full py-1.5 rounded-lg text-xs font-semibold transition ${
            loading
              ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
              : 'bg-cyan-600 hover:bg-cyan-500 text-white'
          }`}
        >
          {loading ? '查询中…' : '🔍 查询子图'}
        </button>

        {queryError && (
          <p className="mt-1.5 text-red-400 text-xs leading-snug">{queryError}</p>
        )}
      </div>

      {/* ── Stats + LLM button (floating top-right) ── */}
      <div className="absolute top-3 right-3 z-20 flex flex-col gap-2 items-end">
        {subgraph && (
          <div className="bg-gray-900/90 border border-gray-700 rounded-xl px-3 py-2 text-xs text-gray-300 backdrop-blur-sm">
            <div className="flex gap-3 items-center">
              <span className="text-cyan-400 font-semibold">{nodes.length}</span> 节点
              <span className="text-red-400 font-semibold">{highCnt}</span> 高
              <span className="text-orange-400 font-semibold">{medCnt}</span> 中
              <span className="text-gray-400">({geoNodeCount} 有坐标)</span>
            </div>
            {subgraph.meta.capped && (
              <p className="text-orange-400 mt-0.5">⚠ 结果已截断</p>
            )}
          </div>
        )}
        <button
          onClick={() => triggerLlm()}
          disabled={llmLoading || !subgraph}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
            llmLoading || !subgraph
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-500 text-white'
          }`}
        >
          {llmLoading ? '评估中…' : '🤖 LLM 风险评估'}
        </button>
      </div>

      {/* ── Legend (bottom-left) ── */}
      <div className="absolute bottom-4 left-3 z-20 bg-gray-900/80 border border-gray-700 rounded-lg px-3 py-2 text-xs backdrop-blur-sm">
        <div className="font-semibold text-gray-400 mb-1.5">节点风险等级</div>
        {(['high', 'medium', 'low'] as const).map((lvl) => (
          <div key={lvl} className="flex items-center gap-1.5 mb-0.5">
            <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: RISK_COLOR[lvl] }} />
            <span className="text-gray-300">{RISK_LABEL[lvl]}</span>
          </div>
        ))}
        <div className="mt-1 pt-1 border-t border-gray-700 text-gray-500">
          节点大小 ∝ 风险分数
        </div>
      </div>

      {/* ── Selected node detail (floating right panel) ── */}
      {selectedNode && (
        <div className="absolute top-20 right-3 z-20 w-64 bg-gray-900/95 border border-gray-700 rounded-xl p-3 text-xs text-gray-300 backdrop-blur-sm">
          <div className="flex justify-between items-start mb-2">
            <span className="font-semibold text-white text-sm leading-snug pr-1">
              {selectedNode.name}
            </span>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-500 hover:text-white flex-shrink-0"
            >✕</button>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">节点类型</span>
              <span>{selectedNode.node_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">企业规模</span>
              <span>{selectedNode.enterprise_scale}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">风险等级</span>
              <span style={{ color: riskColor(selectedNode.risk_level) }} className="font-semibold">
                {RISK_LABEL[selectedNode.risk_level]} ({(selectedNode.risk_score * 100).toFixed(1)}%)
              </span>
            </div>
          </div>

          {/* risk vector mini bars */}
          <div className="mt-2 space-y-0.5">
            {Object.entries(selectedNode.risk_vector).map(([key, val]) => {
              const pct = Math.min(100, (val as number) * 100);
              return (
                <div key={key} className="flex items-center gap-1">
                  <span className="w-24 truncate text-gray-500" title={key}>
                    {key.replace(/_/g, ' ')}
                  </span>
                  <div className="flex-1 h-1 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${pct}%`,
                        background: pct > 50 ? '#ef4444' : pct > 20 ? '#f97316' : '#22c55e',
                      }}
                    />
                  </div>
                  <span className="w-6 text-right text-gray-500">{pct.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>

          <button
            onClick={() => triggerLlm(selectedNode.node_id)}
            disabled={llmLoading}
            className={`mt-2 w-full py-1 rounded text-xs font-semibold transition ${
              llmLoading
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white'
            }`}
          >
            以此节点为种子触发 LLM 评估
          </button>
        </div>
      )}

      {/* ── LLM result panel (bottom slide-up) ── */}
      {showLlm && (
        <div className="absolute bottom-0 left-0 right-0 z-30 bg-gray-900/97 border-t border-gray-700 backdrop-blur-md">
          <div
            className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-gray-800/50"
            onClick={() => setShowLlm(false)}
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white">🤖 LLM 风险评估结果</span>
              {llmResult && (
                <span
                  className="px-2 py-0.5 rounded-full text-xs font-bold text-white"
                  style={{ background: riskColor(llmResult.rule_summary.risk_level) }}
                >
                  {RISK_LABEL[llmResult.rule_summary.risk_level]} — {llmResult.rule_summary.risk_score.toFixed(1)} 分
                </span>
              )}
            </div>
            <span className="text-gray-400 text-xs">▼ 点击收起</span>
          </div>

          {llmLoading && (
            <p className="px-4 pb-3 text-cyan-400 text-sm animate-pulse">正在调用 LLM 评估…</p>
          )}
          {llmError && (
            <p className="px-4 pb-3 text-red-400 text-sm">{llmError}</p>
          )}

          {llmResult && !llmLoading && (
            <div className="px-4 pb-4 max-h-52 overflow-y-auto">
              {/* stats */}
              <div className="flex gap-4 text-xs text-gray-400 mb-2">
                <span>节点 <b className="text-white">{llmResult.subgraph_meta.node_count}</b></span>
                <span>边 <b className="text-white">{llmResult.subgraph_meta.edge_count}</b></span>
                <span>高风险 <b className="text-red-400">{llmResult.rule_summary.high_count}</b></span>
                <span>中风险 <b className="text-orange-400">{llmResult.rule_summary.medium_count}</b></span>
                {llmResult.llm.mock && (
                  <span className="text-gray-500 bg-gray-800 px-1.5 rounded">Mock</span>
                )}
              </div>

              {/* top risky nodes */}
              {llmResult.rule_summary.top_nodes.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {llmResult.rule_summary.top_nodes.map((n) => (
                    <span
                      key={n.node_id}
                      className="px-2 py-0.5 rounded text-xs text-white cursor-default"
                      style={{ background: riskColor(n.risk_level) }}
                      title={n.node_id}
                    >
                      {n.name.slice(0, 10)} ({(n.risk_score * 100).toFixed(1)}%)
                    </span>
                  ))}
                </div>
              )}

              {/* LLM text */}
              {llmResult.llm.success && llmResult.llm.content && (
                <LLMSummary content={llmResult.llm.content} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- compact LLM text display ----
function LLMSummary({ content }: { content: any }) {
  if (typeof content === 'string') {
    return (
      <pre className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed">{content}</pre>
    );
  }
  if (typeof content !== 'object') return null;

  const fields: { label: string; key: string; isList?: boolean }[] = [
    { label: '执行摘要', key: 'executive_summary' },
    { label: '根本原因', key: 'root_cause' },
    { label: '立即行动', key: 'immediate_actions', isList: true },
    { label: '关键因子', key: 'key_risk_factors', isList: true },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 text-xs">
      {fields.map(({ label, key, isList }) => {
        const val = content[key];
        if (!val || (Array.isArray(val) && val.length === 0)) return null;
        return (
          <div key={key} className="bg-gray-800/60 rounded p-2">
            <div className="text-cyan-400 font-semibold mb-0.5">{label}</div>
            {isList && Array.isArray(val) ? (
              <ul className="list-disc list-inside space-y-0.5 text-gray-300">
                {(val as string[]).map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-300 leading-relaxed">{String(val)}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
