'use client';

import dynamic from 'next/dynamic';
import { useState, useCallback } from 'react';
import { subgraphApi } from '@/lib/api';
import type {
  SubgraphNode,
  SubgraphEdge,
  SubgraphResponse,
  LLMAssessResponse,
} from '@/types';

// Dynamic import to avoid SSR for ECharts
const ReactEcharts = dynamic(() => import('echarts-for-react'), { ssr: false });

// ---------- colour helpers ----------
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
const riskColor = (level: string) => RISK_COLOR[level] ?? '#9ca3af';

// ---------- build ECharts option ----------
function buildOption(
  nodes: SubgraphNode[],
  edges: SubgraphEdge[],
  showOnlyRiskyEdges: boolean,
  selectedNodeId: string | null
) {
  const displayEdges = showOnlyRiskyEdges
    ? edges.filter((e) => e.risk_positive_count > 0)
    : edges;

  const ecNodes = nodes.map((n) => ({
    id: n.node_id,
    name: n.name,
    value: n.risk_score,
    symbolSize: Math.max(8, 8 + n.risk_score * 30),
    itemStyle: {
      color: riskColor(n.risk_level),
      borderColor: n.node_id === selectedNodeId ? '#1e40af' : 'transparent',
      borderWidth: n.node_id === selectedNodeId ? 3 : 0,
    },
    label: {
      show: n.node_id === selectedNodeId,
      color: '#111',
      fontSize: 11,
      formatter: n.name.slice(0, 10),
    },
    // carry full node data for click handler
    _node: n,
  }));

  const ecEdges = displayEdges.map((e) => ({
    source: e.source,
    target: e.target,
    value: e.risk_positive_count,
    lineStyle: {
      width: e.risk_positive_count > 0 ? Math.min(4, 1 + e.risk_positive_count) : 0.5,
      color: e.risk_positive_count > 0 ? '#f97316' : '#d1d5db',
      opacity: 0.55,
    },
  }));

  return {
    backgroundColor: '#f9fafb',
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const n: SubgraphNode = params.data._node;
          return `<b>${n.name}</b><br/>
类型: ${n.node_type}<br/>
风险: ${RISK_LABEL[n.risk_level] ?? n.risk_level} (${(n.risk_score * 100).toFixed(1)}%)<br/>
规模: ${n.enterprise_scale}`;
        }
        if (params.dataType === 'edge') {
          return `${params.data.source} → ${params.data.target}<br/>风险标签数: ${params.data.value}`;
        }
        return '';
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        animation: false,
        roam: true,
        draggable: true,
        force: {
          repulsion: 120,
          edgeLength: [30, 80],
          gravity: 0.08,
          layoutAnimation: false,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
        },
        data: ecNodes,
        links: ecEdges,
      },
    ],
  };
}

// ---------- component ----------
export default function SubgraphPage() {
  // Query params
  const [region, setRegion] = useState('上海');
  const [timeWindow, setTimeWindow] = useState(30);
  const [kHop, setKHop] = useState(2);
  const [seedNode, setSeedNode] = useState('');

  // Data
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Edge filter
  const [showOnlyRiskyEdges, setShowOnlyRiskyEdges] = useState(false);

  // Selected node
  const [selectedNode, setSelectedNode] = useState<SubgraphNode | null>(null);

  // LLM assessment
  const [llmResult, setLlmResult] = useState<LLMAssessResponse | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [showLlmPanel, setShowLlmPanel] = useState(false);

  // ---------- fetch subgraph ----------
  const fetchSubgraph = useCallback(async () => {
    setLoading(true);
    setError(null);
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
    if (res.success && res.data) {
      setSubgraph(res.data);
    } else {
      setError(res.error ?? '请求失败');
    }
  }, [region, timeWindow, kHop, seedNode]);

  // ---------- trigger LLM assess ----------
  const triggerLlmAssess = useCallback(async (useSeedNode?: string) => {
    setLlmLoading(true);
    setLlmError(null);
    setShowLlmPanel(true);

    const res = await subgraphApi.llmAssess({
      region: region || undefined,
      time_window: timeWindow,
      k_hop: kHop,
      seed_node: useSeedNode ?? (seedNode.trim() || undefined),
      use_mock_llm: false,
    });

    setLlmLoading(false);
    if (res.success && res.data) {
      setLlmResult(res.data);
    } else {
      setLlmError(res.error ?? 'LLM 评估失败');
    }
  }, [region, timeWindow, kHop, seedNode]);

  // ---------- chart click handler ----------
  const onChartClick = useCallback(
    (params: any) => {
      if (params.dataType === 'node') {
        const node: SubgraphNode = params.data._node;
        setSelectedNode(node);
      }
    },
    []
  );

  const nodes = subgraph?.nodes ?? [];
  const edges = subgraph?.edges ?? [];
  const highCnt = nodes.filter((n) => n.risk_level === 'high').length;
  const medCnt = nodes.filter((n) => n.risk_level === 'medium').length;
  const lowCnt = nodes.filter((n) => n.risk_level === 'low').length;

  return (
    <div className="bg-white rounded-xl shadow flex flex-col" style={{ minHeight: '85vh' }}>
      {/* ── Header ── */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-gray-800">子图可视化 & LLM 风险评估</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            基于 LLM 异构图 — 节点颜色映射风险等级，边粗细反映风险标签数
          </p>
        </div>
        <button
          onClick={() => triggerLlmAssess()}
          disabled={llmLoading || !subgraph}
          className={`px-4 py-2 rounded-lg text-sm font-semibold text-white transition ${
            llmLoading || !subgraph
              ? 'bg-gray-300 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700'
          }`}
        >
          {llmLoading ? '评估中…' : '▶ LLM 风险评估'}
        </button>
      </div>

      {/* ── Filter Panel ── */}
      <div className="bg-white border-b px-6 py-3 flex flex-wrap gap-4 items-end text-sm">
        {/* region */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">区域</label>
          <input
            type="text"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="如: 上海"
            className="border rounded px-2 py-1 w-24 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        </div>

        {/* time_window */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            时间窗口 <span className="font-medium text-gray-700">{timeWindow} 天</span>
          </label>
          <input
            type="range"
            min={7}
            max={365}
            step={7}
            value={timeWindow}
            onChange={(e) => setTimeWindow(Number(e.target.value))}
            className="w-36 accent-indigo-600"
          />
        </div>

        {/* k_hop */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            k-hop <span className="font-medium text-gray-700">{kHop}</span>
          </label>
          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={kHop}
            onChange={(e) => setKHop(Number(e.target.value))}
            className="w-24 accent-indigo-600"
          />
        </div>

        {/* seed_node */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">种子节点（可选）</label>
          <input
            type="text"
            value={seedNode}
            onChange={(e) => setSeedNode(e.target.value)}
            placeholder="节点名称 / ID"
            className="border rounded px-2 py-1 w-44 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        </div>

        {/* query button */}
        <button
          onClick={fetchSubgraph}
          disabled={loading}
          className={`px-5 py-2 rounded-lg text-sm font-semibold text-white transition self-end ${
            loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {loading ? '查询中…' : '🔍 查询子图'}
        </button>

        {/* edge filter toggle */}
        {subgraph && (
          <label className="flex items-center gap-1.5 self-end text-xs cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showOnlyRiskyEdges}
              onChange={(e) => setShowOnlyRiskyEdges(e.target.checked)}
              className="accent-orange-500"
            />
            <span className="text-gray-600">仅显示风险边</span>
          </label>
        )}
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="mx-6 mt-3 px-4 py-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* ── Main Area ── */}
      <div className="flex overflow-hidden" style={{ height: '55vh', minHeight: '440px' }}>
        {/* graph */}
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
              <div className="text-gray-500 text-sm">正在提取子图…</div>
            </div>
          )}

          {!subgraph && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-gray-400">
              <div className="text-5xl mb-3">🕸️</div>
              <p className="text-sm">设置参数后点击「查询子图」</p>
            </div>
          )}

          {subgraph && nodes.length === 0 && (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
              无节点匹配当前过滤条件
            </div>
          )}

          {subgraph && nodes.length > 0 && (
            <ReactEcharts
              option={buildOption(nodes, edges, showOnlyRiskyEdges, selectedNode?.node_id ?? null)}
              style={{ width: '100%', height: '55vh', minHeight: '440px' }}
              onEvents={{ click: onChartClick }}
              opts={{ renderer: 'canvas' }}
            />
          )}

          {/* legend */}
          {subgraph && (
            <div className="absolute bottom-4 left-4 bg-white/90 rounded-lg shadow px-3 py-2 text-xs">
              <div className="font-semibold mb-1 text-gray-700">节点风险等级</div>
              {(['high', 'medium', 'low'] as const).map((lvl) => (
                <div key={lvl} className="flex items-center gap-1.5 mb-0.5">
                  <span
                    className="inline-block w-3 h-3 rounded-full"
                    style={{ background: RISK_COLOR[lvl] }}
                  />
                  <span className="text-gray-600">{RISK_LABEL[lvl]}</span>
                </div>
              ))}
              <div className="mt-1 text-gray-400 border-t pt-1">
                节点: {nodes.length} | 边: {showOnlyRiskyEdges ? edges.filter((e) => e.risk_positive_count > 0).length : edges.length}
              </div>
            </div>
          )}
        </div>

        {/* right panel: stats + node detail */}
        <div className="w-72 bg-white border-l flex flex-col overflow-y-auto">
          {/* stats */}
          {subgraph && (
            <div className="px-4 py-3 border-b">
              <div className="font-semibold text-gray-800 text-sm mb-2">子图统计</div>
              <div className="grid grid-cols-3 gap-1 text-center">
                {[
                  { label: '高', count: highCnt, color: RISK_COLOR.high },
                  { label: '中', count: medCnt, color: RISK_COLOR.medium },
                  { label: '低', count: lowCnt, color: RISK_COLOR.low },
                ].map(({ label, count, color }) => (
                  <div key={label} className="rounded border py-1">
                    <div className="text-lg font-bold" style={{ color }}>
                      {count}
                    </div>
                    <div className="text-xs text-gray-500">{label}风险</div>
                  </div>
                ))}
              </div>
              {subgraph.meta.capped && (
                <p className="text-xs text-orange-500 mt-2">
                  ⚠ 结果已截断至 {nodes.length} 节点 / {edges.length} 边
                </p>
              )}
              {subgraph.meta.start_time && (
                <p className="text-xs text-gray-400 mt-1">
                  时间范围: {subgraph.meta.start_time.slice(0, 10)} ~{' '}
                  {subgraph.meta.end_time?.slice(0, 10)}
                </p>
              )}
            </div>
          )}

          {/* node detail */}
          {selectedNode ? (
            <div className="px-4 py-3 flex-1">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-800 text-sm">节点详情</span>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-gray-400 hover:text-gray-600 text-xs"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-1.5 text-sm">
                <div>
                  <span className="text-gray-500 text-xs">名称</span>
                  <p className="font-medium text-gray-800 leading-snug">{selectedNode.name}</p>
                </div>
                <div className="flex gap-3">
                  <div>
                    <span className="text-gray-500 text-xs">类型</span>
                    <p className="text-gray-700">{selectedNode.node_type}</p>
                  </div>
                  <div>
                    <span className="text-gray-500 text-xs">规模</span>
                    <p className="text-gray-700">{selectedNode.enterprise_scale}</p>
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">风险等级</span>
                  <p
                    className="font-semibold"
                    style={{ color: riskColor(selectedNode.risk_level) }}
                  >
                    {RISK_LABEL[selectedNode.risk_level] ?? selectedNode.risk_level} (
                    {(selectedNode.risk_score * 100).toFixed(1)}%)
                  </p>
                </div>

                {/* risk vector */}
                <div>
                  <span className="text-gray-500 text-xs block mb-1">风险向量</span>
                  <div className="space-y-0.5">
                    {Object.entries(selectedNode.risk_vector).map(([key, val]) => {
                      const pct = Math.min(100, (val as number) * 100);
                      return (
                        <div key={key} className="flex items-center gap-1">
                          <span className="text-xs text-gray-500 w-28 truncate" title={key}>
                            {key.replace(/_/g, ' ')}
                          </span>
                          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${pct}%`,
                                background: pct > 50 ? '#ef4444' : pct > 20 ? '#f97316' : '#22c55e',
                              }}
                            />
                          </div>
                          <span className="text-xs text-gray-400 w-8 text-right">
                            {pct.toFixed(0)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="text-xs text-gray-400">
                  ID: {selectedNode.node_id} | 边数: {selectedNode.observed_edge_count}
                </div>

                {/* trigger LLM for this node */}
                <button
                  onClick={() => triggerLlmAssess(selectedNode.node_id)}
                  disabled={llmLoading}
                  className={`w-full mt-2 py-1.5 rounded text-xs font-semibold text-white transition ${
                    llmLoading
                      ? 'bg-gray-300 cursor-not-allowed'
                      : 'bg-indigo-600 hover:bg-indigo-700'
                  }`}
                >
                  {llmLoading ? '评估中…' : '以此节点为种子触发 LLM 评估'}
                </button>
              </div>
            </div>
          ) : (
            <div className="px-4 py-6 text-center text-gray-400 text-xs flex-1 flex flex-col items-center justify-center">
              <div className="text-3xl mb-2">👆</div>
              点击图中节点查看详情
            </div>
          )}
        </div>
      </div>

      {/* ── LLM Assessment Panel ── */}
      {showLlmPanel && (
        <div className="border-t bg-white">
          <div
            className="flex items-center justify-between px-6 py-2 cursor-pointer hover:bg-gray-50"
            onClick={() => setShowLlmPanel((v) => !v)}
          >
            <span className="font-semibold text-gray-800 text-sm">
              🤖 LLM 风险评估结果
              {llmResult && (
                <span
                  className="ml-2 px-2 py-0.5 rounded-full text-xs font-bold text-white"
                  style={{ background: riskColor(llmResult.rule_summary.risk_level) }}
                >
                  {RISK_LABEL[llmResult.rule_summary.risk_level]} —{' '}
                  {llmResult.rule_summary.risk_score.toFixed(1)} 分
                </span>
              )}
            </span>
            <span className="text-gray-400 text-xs">{showLlmPanel ? '▲ 收起' : '▼ 展开'}</span>
          </div>

          {llmLoading && (
            <div className="px-6 py-4 text-sm text-gray-500 animate-pulse">正在调用 LLM 评估…</div>
          )}

          {llmError && (
            <div className="px-6 py-2 text-sm text-red-600">{llmError}</div>
          )}

          {llmResult && !llmLoading && (
            <div className="px-6 pb-4 space-y-3">
              {/* stats row */}
              <div className="flex gap-6 text-sm mt-1">
                <span>
                  节点: <b>{llmResult.subgraph_meta.node_count}</b>
                </span>
                <span>
                  边: <b>{llmResult.subgraph_meta.edge_count}</b>
                </span>
                <span>
                  高风险节点: <b className="text-red-500">{llmResult.rule_summary.high_count}</b>
                </span>
                <span>
                  中风险节点: <b className="text-orange-500">{llmResult.rule_summary.medium_count}</b>
                </span>
                {llmResult.llm.mock && (
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
                    Mock 模式
                  </span>
                )}
                {llmResult.llm.latency_ms && (
                  <span className="text-xs text-gray-400">耗时 {llmResult.llm.latency_ms} ms</span>
                )}
              </div>

              {/* top risky nodes */}
              {llmResult.rule_summary.top_nodes.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-gray-600 mb-1">Top 风险节点</div>
                  <div className="flex flex-wrap gap-2">
                    {llmResult.rule_summary.top_nodes.map((n) => (
                      <span
                        key={n.node_id}
                        className="px-2 py-0.5 rounded text-xs text-white"
                        style={{ background: riskColor(n.risk_level) }}
                        title={n.node_id}
                      >
                        {n.name.slice(0, 12)} ({(n.risk_score * 100).toFixed(1)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* LLM content */}
              {llmResult.llm.success && llmResult.llm.content && (
                <LLMContentBlock content={llmResult.llm.content} />
              )}
              {!llmResult.llm.success && llmResult.llm.error && (
                <p className="text-sm text-red-500">{llmResult.llm.error}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------- LLM content renderer ----------
function LLMContentBlock({ content }: { content: any }) {
  if (typeof content === 'string') {
    return <pre className="text-xs bg-gray-50 p-3 rounded whitespace-pre-wrap">{content}</pre>;
  }

  if (typeof content !== 'object') {
    return <pre className="text-xs">{JSON.stringify(content, null, 2)}</pre>;
  }

  const sections: { title: string; key: string; isList?: boolean }[] = [
    { title: '执行摘要', key: 'executive_summary' },
    { title: '深度分析', key: 'deep_analysis' },
    { title: '根本原因', key: 'root_cause' },
    { title: '关键风险因子', key: 'key_risk_factors', isList: true },
    { title: '立即行动', key: 'immediate_actions', isList: true },
    { title: '短期措施', key: 'short_term_actions', isList: true },
    { title: '长期建议', key: 'long_term_recommendations', isList: true },
    { title: '监管依据', key: 'regulatory_basis', isList: true },
    { title: '置信度评估', key: 'confidence_assessment' },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 text-xs">
      {sections.map(({ title, key, isList }) => {
        const val = content[key];
        if (!val || (Array.isArray(val) && val.length === 0)) return null;
        return (
          <div key={key} className="bg-gray-50 rounded p-2">
            <div className="font-semibold text-gray-700 mb-1">{title}</div>
            {isList && Array.isArray(val) ? (
              <ul className="list-disc list-inside space-y-0.5 text-gray-600">
                {(val as string[]).map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-600 leading-relaxed">{String(val)}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
