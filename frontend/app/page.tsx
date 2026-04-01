'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import type { SubgraphNode, SubgraphResponse, LLMAssessResponse } from '@/types';
import { subgraphApi } from '@/lib/api';
import Link from 'next/link';
import { PresentationChartLineIcon } from '@heroicons/react/24/outline';
import { detectRegionFromText, saveDashboardAutoFilter } from '@/lib/region';

const ReactEcharts = dynamic(() => import('echarts-for-react'), { ssr: false });

// 产品品类配置
type ProductTagConfig = { label: string; color: string; emoji: string };
const PRODUCT_TAG_CONFIG: Record<string, ProductTagConfig> = {
  pasteurized: { label: '巴氏奶', color: '#3b82f6', emoji: '🥛' },
  UHT: { label: 'UHT奶', color: '#8b5cf6', emoji: '📦' },
  yogurt: { label: '酸奶', color: '#ec4899', emoji: '🍶' },
  cheese: { label: '干酪', color: '#f59e0b', emoji: '🧀' },
  dairy_general: { label: '通用', color: '#6b7280', emoji: '🥄' },
  unknown: { label: '未知', color: '#9ca3af', emoji: '❓' },
};

// 产品品类视觉编码
type ProductTagVisual = { shape: string; color: string; sizeMult: number };
const PRODUCT_TAG_VISUAL: Record<string, ProductTagVisual> = {
  pasteurized: { shape: 'circle', color: '#3b82f6', sizeMult: 1.0 },      // 巴氏奶 - 蓝色圆
  UHT: { shape: 'rect', color: '#8b5cf6', sizeMult: 1.1 },       // UHT - 紫色方
  yogurt: { shape: 'triangle', color: '#ec4899', sizeMult: 0.9 },    // 酸奶 - 粉色三角
  cheese: { shape: 'diamond', color: '#f59e0b', sizeMult: 1.0 },     // 干酪 - 橙色菱形
  dairy_general: { shape: 'circle', color: '#6b7280', sizeMult: 0.8 },    // 通用 - 灰圆
};

export default function Home() {
  useEffect(() => {
    const district = detectRegionFromText('上海');
    if (district) saveDashboardAutoFilter(district, 'modea_unified_entry');
  }, []);

  return (
    <div className="space-y-8">
      {/* 可视化大屏入口 */}
      <Link
        href="/dashboard"
        className="block bg-gradient-to-r from-blue-900/50 to-cyan-900/50 border border-blue-700/50 rounded-xl p-6 hover:from-blue-800/50 hover:to-cyan-800/50 transition-all group"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-blue-600/20 flex items-center justify-center group-hover:scale-110 transition-transform">
              <PresentationChartLineIcon className="w-7 h-7 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white mb-1">供应链风险可视化大屏</h2>
              <p className="text-gray-400 text-sm">
                实时展示 768 家企业节点的风险分布与传播态势 · 异构网络可视化 · 热力图分析
              </p>
            </div>
          </div>
          <div className="text-blue-400 group-hover:translate-x-1 transition-transform">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </Link>
      <Link
        href="/modeb-opinion"
        className="block bg-gradient-to-r from-emerald-900/50 to-teal-900/50 border border-emerald-700/50 rounded-xl p-6 hover:from-emerald-800/50 hover:to-teal-800/50 transition-all group"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-emerald-600/20 flex items-center justify-center group-hover:scale-110 transition-transform text-2xl">
              📣
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white mb-1">MediaCrawler 舆情中心 (Mode B)</h2>
              <p className="text-gray-300 text-sm">
                导入微博/抖音/小红书等舆情语料 · 生成企业舆情风险特征 · 联动症状评估
              </p>
            </div>
          </div>
          <div className="text-emerald-300 group-hover:translate-x-1 transition-transform">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </Link>
      <ModeAPanel />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  Mode A — 子图供应链研判面板
// ═══════════════════════════════════════════════════════════

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

function buildChartOption(
  nodes: SubgraphNode[],
  edges: { source: string; target: string; risk_positive_count: number }[],
  showOnlyRiskyEdges: boolean,
  selectedNodeId: string | null
) {
  const displayEdges = showOnlyRiskyEdges
    ? edges.filter((e) => e.risk_positive_count > 0)
    : edges;

  const ecNodes = nodes.map((n) => {
    const visual = PRODUCT_TAG_VISUAL[n.product_tag] || PRODUCT_TAG_VISUAL.dairy_general;
    // 形状: 品类决定 | 颜色: 风险等级决定 | 大小: 风险分数决定
    return {
      id: n.node_id,
      name: n.name,
      value: n.risk_score,
      symbol: visual.shape,
      symbolSize: Math.max(8, 8 + n.risk_score * 30 * visual.sizeMult),
      itemStyle: {
        color: riskColor(n.risk_level),  // 风险等级决定填充色
        borderColor: n.node_id === selectedNodeId ? '#1e40af' : visual.color,
        borderWidth: n.node_id === selectedNodeId ? 4 : 2,
        shadowBlur: 3,
        shadowColor: visual.color + '40',  // 品类决定阴影色(带透明度)
      },
      label: {
        show: n.node_id === selectedNodeId || n.risk_level === 'high',
        color: '#111',
        fontSize: 10,
        formatter: n.name.slice(0, 8),
        backgroundColor: 'rgba(255,255,255,0.8)',
        borderRadius: 3,
        padding: [2, 4],
      },
      _node: n,
    };
  });

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
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      textStyle: { color: '#374151' },
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const n: SubgraphNode = params.data._node;
          const tagConfig = PRODUCT_TAG_CONFIG[n.product_tag] || PRODUCT_TAG_CONFIG.unknown;
          return `
            <div style="padding:4px 8px;">
              <div style="font-weight:bold;font-size:13px;margin-bottom:4px;">${n.name}</div>
              <div style="display:grid;grid-template-columns:auto auto;gap:4px 12px;font-size:11px;line-height:1.4;">
                <span style="color:#6b7280;">品类:</span>
                <span>${tagConfig.emoji} ${tagConfig.label}</span>
                <span style="color:#6b7280;">类型:</span>
                <span>${n.node_type}</span>
                <span style="color:#6b7280;">风险:</span>
                <span style="color:${riskColor(n.risk_level)};font-weight:500;">
                  ${RISK_LABEL[n.risk_level] ?? n.risk_level} (${(n.risk_score * 100).toFixed(1)}%)
                </span>
                <span style="color:#6b7280;">规模:</span>
                <span>${n.enterprise_scale}</span>
                <span style="color:#6b7280;">度数:</span>
                <span>${n.observed_edge_count}条边</span>
              </div>
            </div>
          `;
        }
        if (params.dataType === 'edge') {
          return `
            <div style="padding:4px 8px;font-size:11px;">
              <div style="color:#6b7280;margin-bottom:2px;">供应链连接</div>
              <div style="font-weight:500;">${params.data.source}</div>
              <div style="color:#9ca3af;margin:2px 0;">↓</div>
              <div style="font-weight:500;">${params.data.target}</div>
              <div style="margin-top:4px;color:${params.data.value > 0 ? '#f97316' : '#22c55e'};">
                风险标签数: ${params.data.value}
              </div>
            </div>
          `;
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
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
        data: ecNodes,
        links: ecEdges,
      },
    ],
  };
}

function ModeAPanel() {
  const [useUnifiedModeA] = useState(true);
  const [region, setRegion] = useState('上海');
  const [timeWindow, setTimeWindow] = useState(365);
  const [kHop, setKHop] = useState(2);
  const [seedNode, setSeedNode] = useState('');

  // Node search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<{ node_id: string; name: string; node_type: string; risk_score: number; product_tag: string }>>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [seedNodeDisplay, setSeedNodeDisplay] = useState('');
  const searchRef = useRef<HTMLDivElement>(null);

  // Debounced search
  useEffect(() => {
    if (searchQuery.length < 2) { setSearchResults([]); setShowDropdown(false); return; }
    const timer = setTimeout(async () => {
      const res = await subgraphApi.searchNodes(searchQuery, 8);
      if (res.success && res.data) { setSearchResults(res.data); setShowDropdown(true); }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => { if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowDropdown(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showOnlyRiskyEdges, setShowOnlyRiskyEdges] = useState(false);
  const [selectedNode, setSelectedNode] = useState<SubgraphNode | null>(null);

  const [llmResult, setLlmResult] = useState<LLMAssessResponse | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [showLlmPanel, setShowLlmPanel] = useState(false);

  const fetchSubgraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setLlmResult(null);
    setShowLlmPanel(false);

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

  const triggerLlmAssess = useCallback(
    async (useSeedNode?: string) => {
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
    },
    [region, timeWindow, kHop, seedNode]
  );

  const onChartClick = useCallback((params: any) => {
    if (params.dataType === 'node') {
      setSelectedNode(params.data._node as SubgraphNode);
    }
  }, []);

  const nodes = subgraph?.nodes ?? [];
  const edges = subgraph?.edges ?? [];
  const highCnt = nodes.filter((n) => n.risk_level === 'high').length;
  const medCnt = nodes.filter((n) => n.risk_level === 'medium').length;
  const lowCnt = nodes.filter((n) => n.risk_level === 'low').length;

  // 产品品类统计
  const productTagStats = nodes.reduce((acc, n) => {
    const tag = n.product_tag || 'unknown';
    acc[tag] = (acc[tag] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  if (useUnifiedModeA) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b bg-gradient-to-r from-slate-900 to-cyan-900">
          <h2 className="text-lg font-bold text-white">供应链研判 (Mode A) - 统一LLM决策链路</h2>
          <p className="text-xs text-cyan-100 mt-1">
            已切换到 ModelA v2：全图/子图 + Top5%热点 + 目标1-3（筛选/排序/预算）+ ModeA报告
          </p>
          <div className="mt-3 flex items-center gap-3">
            <Link
              href="/modela-v2"
              className="inline-flex items-center px-3 py-1.5 rounded-lg bg-cyan-500 text-slate-950 text-xs font-semibold hover:bg-cyan-400 transition-colors"
            >
              打开全屏版 ModelA v2
            </Link>
            <span className="text-[11px] text-cyan-100">
              接口链路：`/api/modela/v2/view` + `/api/modela/v2/modea_report`
            </span>
          </div>
        </div>
        <div className="p-4 bg-slate-50">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
              <div className="font-semibold text-emerald-700 mb-1">目标1 初始筛选</div>
              <div className="text-slate-700">基于 `priority_score` 输出 Top-N 候选企业。</div>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="font-semibold text-amber-700 mb-1">目标2 排序不确定性</div>
              <div className="text-slate-700">同时输出 `risk_proxy + uncertainty_proxy`，支持审计解释。</div>
            </div>
            <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3">
              <div className="font-semibold text-cyan-700 mb-1">目标3 预算分配</div>
              <div className="text-slate-700">按 `budget_utility` 与 `coverage_gain` 进行贪心分配。</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link
              href="/modela-v2"
              className="inline-flex items-center px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-colors"
            >
              进入 ModeA 主界面
            </Link>
            <span className="text-xs text-slate-500">已移除首页嵌套 iframe，避免导航与图标重复挤压布局。</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow flex flex-col" style={{ minHeight: '82vh' }}>
      {/* ── Header ── */}
      <div className="border-b px-6 py-3 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-800">🕸️ 供应链子图研判 (Mode A)</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            基于 LLM 异构图 · 节点颜色映射风险 · 边粗细反映风险标签数 · 支持 k-hop 传播分析
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

      {/* ── Filter / Query Bar ── */}
      <div className="border-b px-6 py-3 flex flex-wrap gap-4 items-end text-sm bg-gray-50">
        {/* seed_node — smart search with dropdown */}
        <div className="flex-1 min-w-[200px] relative" ref={searchRef}>
          <label className="block text-xs text-gray-500 mb-1">企业搜索（种子节点）</label>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); if (!e.target.value) { setSeedNode(''); setSeedNodeDisplay(''); } }}
            onKeyDown={(e) => e.key === 'Enter' && fetchSubgraph()}
            placeholder={seedNodeDisplay || '输入企业名称搜索…留空则按区域检索'}
            className="border rounded px-3 py-1.5 w-full text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          {seedNodeDisplay && (
            <span className="absolute right-2 top-7 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded truncate max-w-[60%]">
              ✓ {seedNodeDisplay}
            </span>
          )}
          {showDropdown && searchResults.length > 0 && (
            <div className="absolute z-50 w-full bg-white border rounded-lg shadow-lg mt-1 max-h-52 overflow-y-auto">
              {searchResults.map((n) => (
                <button
                  key={n.node_id}
                  onMouseDown={(e) => { e.preventDefault(); setSeedNode(n.node_id); setSeedNodeDisplay(n.name); setSearchQuery(''); setShowDropdown(false); }}
                  className="w-full text-left px-3 py-2 hover:bg-blue-50 border-b last:border-0 flex items-center gap-2"
                >
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${n.risk_score > 0.2 ? 'bg-red-400' : n.risk_score > 0.1 ? 'bg-yellow-400' : 'bg-green-400'}`} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{n.name}</div>
                    <div className="text-xs text-gray-400">{n.node_type} · {n.product_tag} · risk={n.risk_score.toFixed(4)}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* region */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">区域</label>
          <input
            type="text"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="如: 上海"
            className="border rounded px-2 py-1.5 w-24 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>

        {/* time_window */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            时间窗口 <span className="font-medium text-gray-700">{timeWindow} 天</span>
          </label>
          <input
            type="range"
            min={30}
            max={365}
            step={30}
            value={timeWindow}
            onChange={(e) => setTimeWindow(Number(e.target.value))}
            className="w-36 accent-blue-600"
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
            className="w-24 accent-blue-600"
          />
        </div>

        <button
          onClick={fetchSubgraph}
          disabled={loading}
          className={`px-5 py-2 rounded-lg text-sm font-semibold text-white transition self-end ${
            loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {loading ? '查询中…' : '🔍 查询子图'}
        </button>

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

      {/* error */}
      {error && (
        <div className="mx-6 mt-3 px-4 py-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* 产品品类图例 */}
      {subgraph && (
        <div className="px-4 py-2 border-b bg-gray-50">
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <span className="text-gray-500 font-medium">图例:</span>
            <span className="text-gray-400">形状=品类</span>
            <span className="text-gray-400">颜色=风险</span>
            {Object.entries(PRODUCT_TAG_CONFIG).map(([tag, config]) => (
              tag !== 'unknown' && (
                <div key={tag} className="flex items-center gap-1">
                  <span>{config.emoji}</span>
                  <span className="text-gray-600">{config.label}</span>
                  <span className="text-gray-400">({productTagStats[tag] || 0})</span>
                </div>
              )
            ))}
          </div>
        </div>
      )}

      {/* ── Graph + Side Panel ── */}
      <div className="flex overflow-hidden" style={{ height: '54vh', minHeight: '420px' }}>
        {/* chart */}
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
              <div className="text-center">
                <div className="w-10 h-10 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto mb-2" />
                <p className="text-gray-500 text-sm">正在提取子图…</p>
              </div>
            </div>
          )}

          {!subgraph && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-gray-400">
              <div className="text-6xl mb-3">🕸️</div>
              <p className="text-sm font-medium mb-1">供应链子图研判</p>
              <p className="text-xs text-gray-400">输入企业关键词或直接点击「查询子图」以加载全区域子图</p>
            </div>
          )}

          {subgraph && nodes.length === 0 && (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
              无节点匹配当前筛选条件
            </div>
          )}

          {subgraph && nodes.length > 0 && (
            <ReactEcharts
              option={buildChartOption(nodes, edges, showOnlyRiskyEdges, selectedNode?.node_id ?? null)}
              style={{ width: '100%', height: '54vh', minHeight: '420px' }}
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
                  <span className="inline-block w-3 h-3 rounded-full" style={{ background: RISK_COLOR[lvl] }} />
                  <span className="text-gray-600">{RISK_LABEL[lvl]}</span>
                </div>
              ))}
              <div className="mt-1 text-gray-400 border-t pt-1">
                节点: {nodes.length} | 边:{' '}
                {showOnlyRiskyEdges ? edges.filter((e) => e.risk_positive_count > 0).length : edges.length}
              </div>
            </div>
          )}
        </div>

        {/* right panel */}
        <div className="w-72 bg-white border-l flex flex-col overflow-y-auto">
          {/* stats */}
          {subgraph && (
            <div className="px-4 py-3 border-b">
              <div className="font-semibold text-gray-800 text-sm mb-2">子图统计</div>

              {/* 风险等级分布 */}
              <div className="grid grid-cols-3 gap-1 text-center mb-3">
                {[
                  { label: '高', count: highCnt, color: RISK_COLOR.high },
                  { label: '中', count: medCnt, color: RISK_COLOR.medium },
                  { label: '低', count: lowCnt, color: RISK_COLOR.low },
                ].map(({ label, count, color }) => (
                  <div key={label} className="rounded border py-1">
                    <div className="text-lg font-bold" style={{ color }}>{count}</div>
                    <div className="text-xs text-gray-500">{label}风险</div>
                  </div>
                ))}
              </div>

              {/* 产品品类分布 */}
              <div className="mb-3">
                <div className="text-xs text-gray-500 mb-1.5">产品品类分布</div>
                <div className="space-y-1">
                  {Object.entries(productTagStats)
                    .sort(([,a], [,b]) => b - a)
                    .map(([tag, count]) => {
                      const config = PRODUCT_TAG_CONFIG[tag] || PRODUCT_TAG_CONFIG.unknown;
                      const percentage = (count / nodes.length * 100).toFixed(1);
                      return (
                        <div key={tag} className="flex items-center gap-2 text-xs">
                          <span className="w-4">{config.emoji}</span>
                          <span className="w-12 text-gray-600">{config.label}</span>
                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${percentage}%`,
                                backgroundColor: config.color
                              }}
                            />
                          </div>
                          <span className="w-10 text-right text-gray-700">{count}</span>
                          <span className="w-10 text-right text-gray-400">{percentage}%</span>
                        </div>
                      );
                    })}
                </div>
              </div>

              {subgraph.meta.capped && (
                <p className="text-xs text-orange-500 mt-2">
                  ⚠ 结果已截断至 {nodes.length} 节点 / {edges.length} 边
                </p>
              )}
              {subgraph.meta.start_time && (
                <p className="text-xs text-gray-400 mt-1">
                  时间范围: {subgraph.meta.start_time.slice(0, 10)} ~ {subgraph.meta.end_time?.slice(0, 10)}
                </p>
              )}
            </div>
          )}

          {/* node detail */}
          {selectedNode ? (
            <div className="px-4 py-3 flex-1">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-800 text-sm">节点详情</span>
                <button onClick={() => setSelectedNode(null)} className="text-gray-400 hover:text-gray-600 text-xs">
                  ✕
                </button>
              </div>
              <div className="space-y-1.5 text-sm">
                <div>
                  <span className="text-gray-500 text-xs">名称</span>
                  <p className="font-medium text-gray-800 leading-snug">{selectedNode.name}</p>
                </div>
                <div className="flex gap-3 flex-wrap">
                  <div>
                    <span className="text-gray-500 text-xs">类型</span>
                    <p className="text-gray-700">{selectedNode.node_type}</p>
                  </div>
                  <div>
                    <span className="text-gray-500 text-xs">品类</span>
                    <p className="text-gray-700">
                      {(() => {
                        const config = PRODUCT_TAG_CONFIG[selectedNode.product_tag] || PRODUCT_TAG_CONFIG.unknown;
                        return `${config.emoji} ${config.label}`;
                      })()}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500 text-xs">规模</span>
                    <p className="text-gray-700">{selectedNode.enterprise_scale}</p>
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">风险等级</span>
                  <p className="font-semibold" style={{ color: riskColor(selectedNode.risk_level) }}>
                    {RISK_LABEL[selectedNode.risk_level] ?? selectedNode.risk_level} (
                    {(selectedNode.risk_score * 100).toFixed(1)}%)
                  </p>
                </div>
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
                          <span className="text-xs text-gray-400 w-8 text-right">{pct.toFixed(0)}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
                <div className="text-xs text-gray-400">
                  ID: {selectedNode.node_id} | 边数: {selectedNode.observed_edge_count}
                </div>
                <button
                  onClick={() => triggerLlmAssess(selectedNode.node_id)}
                  disabled={llmLoading}
                  className={`w-full mt-2 py-1.5 rounded text-xs font-semibold text-white transition ${
                    llmLoading ? 'bg-gray-300 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'
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
        <div className="border-t bg-white rounded-b-xl">
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
                  {RISK_LABEL[llmResult.rule_summary.risk_level]} — {llmResult.rule_summary.risk_score.toFixed(1)} 分
                </span>
              )}
            </span>
            <span className="text-gray-400 text-xs">{showLlmPanel ? '▲ 收起' : '▼ 展开'}</span>
          </div>

          {llmLoading && (
            <div className="px-6 py-4 text-sm text-gray-500 animate-pulse">正在调用 LLM 评估…</div>
          )}
          {llmError && <div className="px-6 py-2 text-sm text-red-600">{llmError}</div>}

          {llmResult && !llmLoading && (
            <div className="px-6 pb-4 space-y-3">
              <div className="flex flex-wrap gap-6 text-sm mt-1">
                <span>节点: <b>{llmResult.subgraph_meta.node_count}</b></span>
                <span>边: <b>{llmResult.subgraph_meta.edge_count}</b></span>
                <span>高风险节点: <b className="text-red-500">{llmResult.rule_summary.high_count}</b></span>
                <span>中风险节点: <b className="text-orange-500">{llmResult.rule_summary.medium_count}</b></span>
                {llmResult.llm.mock && (
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">Mock 模式</span>
                )}
                {llmResult.llm.latency_ms && (
                  <span className="text-xs text-gray-400">耗时 {llmResult.llm.latency_ms} ms</span>
                )}
              </div>

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

// ── LLM content renderer ──
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
