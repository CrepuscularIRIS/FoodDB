'use client';

import dynamic from 'next/dynamic';
import { useEffect, useMemo, useState } from 'react';
import { modelAV2Api } from '@/lib/api';
import type {
  ModelAV2Edge,
  ModelAV2GraphView,
  ModelAV2Node,
  ModelAModeAReportResponse,
  ModelARankingEvalResponse,
  ModelAResourcePlanResponse,
  ModelAScreeningResponse,
  ModelATemporalSimResponse,
} from '@/types';

const ReactEcharts = dynamic(() => import('echarts-for-react'), { ssr: false });

const RISK_NAMES = ['非食用添加剂', '农药兽药残留', '食品添加剂', '微生物', '重金属污染物', '生物毒素', '其他污染物'];
const TYPE_COLORS = ['#22d3ee', '#38bdf8', '#34d399', '#fbbf24', '#fb7185', '#a78bfa', '#f97316', '#2dd4bf', '#60a5fa'];

function riskColor(score: number): string {
  if (score >= 0.82) return '#ef4444';
  if (score >= 0.66) return '#f97316';
  if (score >= 0.5) return '#eab308';
  if (score >= 0.38) return '#84cc16';
  return '#10b981';
}

function edgeColor(score: number): string {
  if (score >= 0.75) return '#f43f5e';
  if (score >= 0.55) return '#fb923c';
  if (score >= 0.35) return '#facc15';
  return '#22d3ee';
}

function parseJSONText(content?: string): any {
  if (!content) return null;
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function nodeScore(n: ModelAV2Node): number {
  return Number(n.priority_score ?? n.risk_proxy ?? n.view_risk_score ?? n.category_risk_score ?? n.risk_score ?? 0);
}

function edgeScore(e: ModelAV2Edge): number {
  if (e.edge_priority !== undefined) return Number(e.edge_priority);
  if (e.edge_risk_proxy !== undefined) return Number(e.edge_risk_proxy);
  if (e.view_risk_score !== undefined) return Number(e.view_risk_score);
  return Number(Math.max(...(e.risk_probabilities || [0])));
}

export default function ModelAV2Page() {
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [viewMode, setViewMode] = useState<'full' | 'product'>('product');
  const [seedNode, setSeedNode] = useState('');
  const [kHop, setKHop] = useState(0);
  const [maxNodes, setMaxNodes] = useState(600);
  const [maxEdges, setMaxEdges] = useState(3500);
  const [topRatio, setTopRatio] = useState(0.05);
  const [showOnlyTop5, setShowOnlyTop5] = useState(false);
  const [edgeMinScore, setEdgeMinScore] = useState(0.12);
  const [labelMode, setLabelMode] = useState<'auto' | 'all' | 'none'>('auto');

  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState('');

  const [graph, setGraph] = useState<ModelAV2GraphView | null>(null);
  const [selectedNode, setSelectedNode] = useState<ModelAV2Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<ModelAV2Edge | null>(null);

  const [screeningType, setScreeningType] = useState('原奶供应商');
  const [topN, setTopN] = useState(10);
  const [budget, setBudget] = useState(20);
  const [screening, setScreening] = useState<ModelAScreeningResponse | null>(null);
  const [rankingEval, setRankingEval] = useState<ModelARankingEvalResponse | null>(null);
  const [resourcePlan, setResourcePlan] = useState<ModelAResourcePlanResponse | null>(null);
  const [temporalSim, setTemporalSim] = useState<ModelATemporalSimResponse | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [trainMonth, setTrainMonth] = useState('2025-01');
  const [testMonth, setTestMonth] = useState('2025-02');
  const [simTopK, setSimTopK] = useState(50);
  const [inspectCount, setInspectCount] = useState(120);
  const [exploreWeight, setExploreWeight] = useState(0.35);
  const [report, setReport] = useState<ModelAModeAReportResponse | null>(null);

  useEffect(() => {
    const loadInit = async () => {
      setError('');
      const [catsRes] = await Promise.all([modelAV2Api.getCategories(), modelAV2Api.getMeta()]);
      if (catsRes.success && catsRes.data) {
        setCategories(catsRes.data);
        if (catsRes.data.length > 0) setSelectedCategory(catsRes.data[0]);
      } else if (catsRes.error) {
        setError(catsRes.error);
      }
    };
    loadInit();
  }, []);

  const fetchView = async () => {
    if (viewMode === 'product' && !selectedCategory) {
      setError('请选择乳制品品类');
      return;
    }
    setLoading(true);
    setError('');
    setSelectedNode(null);
    setSelectedEdge(null);

    const res = await modelAV2Api.getView({
      view_mode: viewMode,
      product_type: viewMode === 'product' ? selectedCategory : undefined,
      seed_node: seedNode.trim() || undefined,
      k_hop: kHop,
      max_nodes: maxNodes,
      max_edges: maxEdges,
      top_ratio: topRatio,
    });
    setLoading(false);
    if (res.success && res.data) {
      setGraph(res.data);
    } else {
      setError(res.error || '图加载失败');
    }
  };

  useEffect(() => {
    if (viewMode === 'product' && !selectedCategory) return;
    fetchView();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, selectedCategory]);

  const runScreening = async () => {
    setError('');
    const product = viewMode === 'product' ? selectedCategory : undefined;
    const [sRes, eRes] = await Promise.all([
      modelAV2Api.screening({
        product_type: product,
        node_type: screeningType || undefined,
        top_n: topN,
        max_nodes: maxNodes,
        max_edges: maxEdges,
      }),
      modelAV2Api.rankingEval({
        product_type: product,
        node_type: screeningType || undefined,
        top_k: topN,
        max_nodes: maxNodes,
        max_edges: maxEdges,
      }),
    ]);

    if (sRes.success && sRes.data) setScreening(sRes.data);
    else setError(sRes.error || '初筛失败');

    if (eRes.success && eRes.data) setRankingEval(eRes.data);
    else if (eRes.error) setError(eRes.error);
  };

  const runResourcePlan = async () => {
    setError('');
    const product = viewMode === 'product' ? selectedCategory : undefined;
    const res = await modelAV2Api.resourcePlan({
      product_type: product,
      node_type: screeningType || undefined,
      budget,
      max_enterprises: topN,
      max_nodes: maxNodes,
      max_edges: maxEdges,
      min_samples_per_type: 0,
    });
    if (res.success && res.data) setResourcePlan(res.data);
    else setError(res.error || '资源分配失败');
  };

  const runTemporalSim = async () => {
    setError('');
    setSimLoading(true);
    const product = viewMode === 'product' ? selectedCategory : undefined;
    const res = await modelAV2Api.temporalSimulate({
      train_month: trainMonth,
      test_month: testMonth,
      product_type: product,
      node_type: screeningType || undefined,
      max_nodes: maxNodes,
      max_edges: maxEdges,
      top_ratio: topRatio,
      top_k: simTopK,
      inspect_count: inspectCount,
      explore_weight: exploreWeight,
      seed: 42,
    });
    setSimLoading(false);
    if (res.success && res.data) setTemporalSim(res.data);
    else setError(res.error || '月度训练测试模拟失败');
  };

  const runModeAReport = async () => {
    setReportLoading(true);
    setError('');
    const res = await modelAV2Api.modeAReport({
      view_mode: viewMode,
      product_type: viewMode === 'product' ? selectedCategory : undefined,
      seed_node: seedNode.trim() || undefined,
      k_hop: kHop,
      max_nodes: maxNodes,
      max_edges: maxEdges,
      top_ratio: topRatio,
      use_mock_llm: false,
    });
    setReportLoading(false);
    if (res.success && res.data) setReport(res.data);
    else setError(res.error || 'Mode A 报告生成失败');
  };

  const chartOption = useMemo(() => {
    const rawNodes = graph?.nodes || [];
    const rawEdges = graph?.edges || [];

    let selectedNodes: ModelAV2Node[] = [];
    let selectedEdges: ModelAV2Edge[] = [];

    if (showOnlyTop5) {
      const topNodeIds = new Set(rawNodes.filter((n) => !!n.is_top5_any).map((n) => n.node_id));
      selectedEdges = rawEdges.filter((e) => {
        if (edgeScore(e) < edgeMinScore) return false;
        return topNodeIds.has(e.source) || topNodeIds.has(e.target);
      });
      const contextNodeIds = new Set<string>();
      topNodeIds.forEach((id) => contextNodeIds.add(id));
      for (const e of selectedEdges) {
        contextNodeIds.add(e.source);
        contextNodeIds.add(e.target);
      }
      selectedNodes = rawNodes.filter((n) => contextNodeIds.has(n.node_id));
    } else {
      selectedNodes = rawNodes;
      const keepIds = new Set(selectedNodes.map((n) => n.node_id));
      selectedEdges = rawEdges.filter((e) => {
        if (!keepIds.has(e.source) || !keepIds.has(e.target)) return false;
        if (edgeScore(e) < edgeMinScore) return false;
        return true;
      });
    }

    const typeList = Array.from(new Set(selectedNodes.map((n) => n.node_type || '未知')));
    const typeColorMap = new Map<string, string>();
    typeList.forEach((t, i) => typeColorMap.set(t, TYPE_COLORS[i % TYPE_COLORS.length]));

    return {
      backgroundColor: '#020617',
      animationDuration: 1200,
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(2, 6, 23, 0.92)',
        borderColor: '#334155',
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const n = params.data._raw as ModelAV2Node;
            const s = nodeScore(n);
            return `${n.name}<br/>${n.node_type} · ${n.enterprise_scale}<br/>优先级: ${(s * 100).toFixed(1)}%<br/>风险代理: ${((n.risk_proxy ?? n.view_risk_score ?? 0) * 100).toFixed(1)}%<br/>不确定性: ${((n.uncertainty_proxy ?? 0) * 100).toFixed(1)}%<br/>Top5标签数: ${n.top5_count || 0}`;
          }
          if (params.dataType === 'edge') {
            const e = params.data._raw as ModelAV2Edge;
            const s = edgeScore(e);
            return `${e.source_name} → ${e.target_name}<br/>品类: ${e.dairy_product_type}<br/>边优先级: ${(s * 100).toFixed(1)}%<br/>边风险代理: ${((e.edge_risk_proxy ?? e.view_risk_score ?? s) * 100).toFixed(1)}%<br/>Top5标签数: ${e.top5_count || 0}`;
          }
          return '';
        },
      },
      toolbox: {
        right: 10,
        top: 8,
        iconStyle: { borderColor: '#cbd5e1' },
        feature: {
          restore: {},
          saveAsImage: {},
        },
      },
      legend: [
        {
          top: 8,
          left: 8,
          textStyle: { color: '#e2e8f0' },
          data: typeList,
        },
      ],
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          focusNodeAdjacency: true,
          force: {
            repulsion: selectedNodes.length > 300 ? 65 : 110,
            edgeLength: [28, 95],
            gravity: 0.06,
            friction: 0.2,
          },
          categories: typeList.map((t) => ({ name: t })),
          label: {
            show: labelMode !== 'none',
            color: '#f8fafc',
            fontSize: 10,
            formatter: (x: any) => {
              const n = x.data?._raw as ModelAV2Node;
              const s = nodeScore(n);
              if (labelMode === 'all') return n?.name || '';
              return n?.is_top5_any || s >= 0.8 ? n.name : '';
            },
          },
          lineStyle: {
            curveness: 0.18,
            opacity: 0.45,
          },
          emphasis: {
            scale: true,
            lineStyle: { width: 3 },
          },
          data: selectedNodes.map((n) => {
            const s = nodeScore(n);
            const top = !!n.is_top5_any;
            const c = n.top5_count || 0;
            return {
              id: n.node_id,
              name: n.name,
              category: typeList.indexOf(n.node_type || '未知'),
              symbolSize: Math.max(10, 10 + s * 28 + c * 1.8),
              itemStyle: {
                color: riskColor(s),
                borderColor: top ? '#f59e0b' : typeColorMap.get(n.node_type || '未知'),
                borderWidth: top ? 2.8 : 0.9,
                shadowBlur: top ? 18 : 5,
                shadowColor: top ? 'rgba(245,158,11,0.55)' : 'rgba(56,189,248,0.2)',
              },
              _raw: n,
            };
          }),
          links: selectedEdges.map((e) => {
            const s = edgeScore(e);
            return {
              source: e.source,
              target: e.target,
              lineStyle: {
                width: 0.6 + s * 3.6 + (e.is_top5_any ? 1.2 : 0),
                color: edgeColor(s),
                opacity: e.is_top5_any ? 0.9 : 0.5,
              },
              _raw: e,
            };
          }),
        },
      ],
    };
  }, [edgeMinScore, graph, labelMode, showOnlyTop5]);

  const topRiskNodes = useMemo(() => {
    const nodes = [...(graph?.nodes || [])];
    nodes.sort((a, b) => nodeScore(b) - nodeScore(a));
    return nodes.slice(0, 20);
  }, [graph]);

  const llmJSON = parseJSONText(report?.llm?.content);
  const formulaParams = graph?.meta?.formula?.params || {};
  const formulaMeta = graph?.meta?.formula;
  const fmtParam = (k: string) => {
    const v = formulaParams[k];
    if (v === undefined || v === null) return '--';
    return Number(v).toFixed(2);
  };

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4 text-slate-100 shadow-2xl min-h-[84vh]">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-700/60 bg-slate-900/60 p-3 mb-4">
        <div>
          <label className="block text-xs text-slate-300 mb-1">视图模式</label>
          <select
            value={viewMode}
            onChange={(e) => setViewMode(e.target.value as 'full' | 'product')}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm min-w-[130px]"
          >
            <option value="product">品类子图</option>
            <option value="full">供应链全图</option>
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-300 mb-1">乳制品品类</label>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            disabled={viewMode === 'full'}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm min-w-[220px] disabled:opacity-40"
          >
            {categories.map((c) => (
              <option value={c} key={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-300 mb-1">种子节点</label>
          <input
            value={seedNode}
            onChange={(e) => setSeedNode(e.target.value)}
            placeholder="企业名或N-xxxxx"
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-52"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-300 mb-1">k-hop</label>
          <input
            type="number"
            min={0}
            max={5}
            value={kHop}
            onChange={(e) => setKHop(Number(e.target.value))}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-20"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-300 mb-1">节点上限</label>
          <input
            type="number"
            min={100}
            max={5000}
            value={maxNodes}
            onChange={(e) => setMaxNodes(Number(e.target.value))}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-300 mb-1">边上限</label>
          <input
            type="number"
            min={100}
            max={50000}
            value={maxEdges}
            onChange={(e) => setMaxEdges(Number(e.target.value))}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-300 mb-1">Top比例</label>
          <input
            type="number"
            min={0.01}
            max={0.2}
            step={0.01}
            value={topRatio}
            onChange={(e) => setTopRatio(Number(e.target.value))}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-300 mb-1">边风险阈值</label>
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={edgeMinScore}
            onChange={(e) => setEdgeMinScore(Number(e.target.value))}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-300 mb-1">标签模式</label>
          <select
            value={labelMode}
            onChange={(e) => setLabelMode(e.target.value as 'auto' | 'all' | 'none')}
            className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm min-w-[98px]"
          >
            <option value="auto">智能</option>
            <option value="all">全部</option>
            <option value="none">隐藏</option>
          </select>
        </div>

        <button
          onClick={fetchView}
          className="px-3 py-1.5 rounded bg-cyan-600 text-white text-sm hover:bg-cyan-500"
          disabled={loading}
        >
          {loading ? '加载中...' : '刷新图谱'}
        </button>

        <label className="flex items-center gap-2 text-xs text-slate-200">
          <input type="checkbox" checked={showOnlyTop5} onChange={(e) => setShowOnlyTop5(e.target.checked)} />
          仅看Top5%节点及其关联风险边
        </label>
      </div>

      {error && <div className="text-sm text-rose-300 mb-3">{error}</div>}

      <div className="mb-4 rounded-xl border border-slate-700 bg-slate-900/70 p-3">
        <div className="text-sm font-semibold mb-2">5.4Pro 公式落地状态</div>
        <div className="grid grid-cols-12 gap-3 text-xs">
          <div className="col-span-6 rounded border border-emerald-700/50 bg-emerald-950/25 p-2">
            <div className="text-emerald-300 mb-1 font-medium">已接入</div>
            <div className="text-slate-200">1. risk / credibility / uncertainty 三代理</div>
            <div className="text-slate-200">2. exploit + explore 双支路优先级</div>
            <div className="text-slate-200">3. edge_time_fragility + edge_priority</div>
            <div className="text-slate-200">4. 预算贪心分配（utility + coverage_gain）</div>
            <div className="text-slate-200">5. 贡献拆解与公式参数透出（可审计）</div>
          </div>
          <div className="col-span-6 rounded border border-cyan-700/50 bg-cyan-950/20 p-2">
            <div className="text-cyan-300 mb-1 font-medium">增强层状态</div>
            <div className="text-slate-200">piecewise override: {formulaMeta ? (formulaMeta.piecewise_enabled ? '已启用' : '未启用') : '加载后显示'}</div>
            <div className="text-slate-200">KQV overlay: {formulaMeta ? (formulaMeta.kqv_enabled ? '已启用' : '未启用') : '加载后显示'}</div>
            <div className="text-slate-200">优先级链路: base → piecewise → KQV → final</div>
            <div className="text-slate-200">节点与边都参与最终排序分数</div>
          </div>
        </div>
        <div className="mt-2 text-[11px] text-slate-300">
          当前参数：λ={fmtParam('lambda')}，a_x={fmtParam('a_x')}，c_m={fmtParam('c_m')}，μ={fmtParam('kqv_mu')}，τ={fmtParam('kqv_tau')}，θA={fmtParam('piece_theta_a')}，θB={fmtParam('piece_theta_b')}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-8 rounded-xl border border-slate-700 bg-slate-950/80 overflow-hidden">
          <ReactEcharts
            option={chartOption}
            style={{ height: 680 }}
            onEvents={{
              click: (params: any) => {
                if (params.dataType === 'node') {
                  setSelectedNode(params.data._raw);
                  setSelectedEdge(null);
                }
                if (params.dataType === 'edge') {
                  setSelectedEdge(params.data._raw);
                  setSelectedNode(null);
                }
              },
            }}
          />
        </div>

        <div className="col-span-4 rounded-xl border border-slate-700 bg-slate-900/80 p-3">
          <h3 className="font-semibold text-slate-100 mb-2">图谱指标</h3>
          {graph && (
            <div className="text-xs text-slate-300 space-y-1 mb-3">
              <div>节点: {graph.meta.node_count}</div>
              <div>边: {graph.meta.edge_count}（显示阈值≥{edgeMinScore.toFixed(2)}）</div>
              <div>模式: {graph.meta.view_mode === 'full' ? '全图' : '品类子图'}</div>
              <div>Top阈值比例: {(graph.meta.top5_thresholds.ratio * 100).toFixed(1)}%</div>
              {graph.meta.formula?.formula_version && <div>公式版本: {graph.meta.formula.formula_version}</div>}
              {graph.meta.capped_nodes && <div className="text-amber-300">节点已截断为上限</div>}
              {graph.meta.capped_edges && <div className="text-amber-300">边已截断为上限</div>}
            </div>
          )}

          {selectedNode && (
            <div className="mb-4">
              <div className="text-sm font-semibold">{selectedNode.name}</div>
              <div className="text-xs text-slate-300 mb-2">{selectedNode.node_type} · {selectedNode.enterprise_scale}</div>
              <div className="text-xs mb-1">优先级: {(nodeScore(selectedNode) * 100).toFixed(1)}%</div>
              <div className="text-xs mb-1">base/piecewise: {((selectedNode.priority_base_score ?? 0) * 100).toFixed(1)}% / {((selectedNode.priority_piecewise_score ?? 0) * 100).toFixed(1)}%</div>
              <div className="text-xs mb-1">KQV增益: {((selectedNode.kqv_overlay?.delta ?? 0) * 100).toFixed(1)}%（μ={((selectedNode.kqv_overlay?.mu ?? 0) * 100).toFixed(0)}%）</div>
              <div className="text-xs mb-1">风险代理: {((selectedNode.risk_proxy ?? selectedNode.view_risk_score ?? 0) * 100).toFixed(1)}%</div>
              <div className="text-xs mb-1">可信度: {((selectedNode.credibility_proxy ?? 0) * 100).toFixed(1)}%</div>
              <div className="text-xs mb-2">不确定性: {((selectedNode.uncertainty_proxy ?? 0) * 100).toFixed(1)}%</div>
              {selectedNode.formula_contrib && (
                <div className="mb-2 rounded border border-slate-700 bg-slate-950/70 p-2 text-[11px] text-slate-300">
                  <div className="mb-1 text-slate-200">贡献拆解</div>
                  <div>风险: 内生 {((selectedNode.formula_contrib.risk?.intrinsic ?? 0) * 100).toFixed(1)}% / 暴露 {((selectedNode.formula_contrib.risk?.exposure ?? 0) * 100).toFixed(1)}% / 画像 {((selectedNode.formula_contrib.risk?.profile ?? 0) * 100).toFixed(1)}%</div>
                  <div>不确定性: 缺失 {((selectedNode.formula_contrib.uncertainty?.unexpected_missing ?? 0) * 100).toFixed(1)}% / 波动 {((selectedNode.formula_contrib.uncertainty?.neighbor_variance ?? 0) * 100).toFixed(1)}%</div>
                </div>
              )}
              {((selectedNode.view_risk_probabilities || selectedNode.category_risk_probabilities || []) as number[]).map((v, i) => (
                <div key={`n-${i}`} className="text-xs flex justify-between py-0.5 text-slate-200">
                  <span>{RISK_NAMES[i]}</span>
                  <span>{(v * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          )}

          {selectedEdge && (
            <div>
              <div className="text-sm font-semibold">{selectedEdge.source_name} → {selectedEdge.target_name}</div>
              <div className="text-xs text-slate-300 mb-2">{selectedEdge.dairy_product_type}</div>
              <div className="text-xs mb-1">边优先级: {(edgeScore(selectedEdge) * 100).toFixed(1)}%</div>
              <div className="text-xs mb-1">边风险代理: {((selectedEdge.edge_risk_proxy ?? selectedEdge.view_risk_score ?? 0) * 100).toFixed(1)}%</div>
              <div className="text-xs mb-2">边不确定性: {((selectedEdge.edge_uncertainty ?? 0) * 100).toFixed(1)}%</div>
              {(selectedEdge.view_risk_probabilities || selectedEdge.risk_probabilities || []).map((v, i) => (
                <div key={`e-${i}`} className="text-xs flex justify-between py-0.5 text-slate-200">
                  <span>{RISK_NAMES[i]}</span>
                  <span>{(v * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          )}

          {!selectedNode && !selectedEdge && (
            <div className="text-xs text-slate-400">点击节点或边查看优先级、风险代理、不确定性与7类风险概率。</div>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-12 gap-4">
        <div className="col-span-6 rounded-xl border border-slate-700 bg-slate-900/70 p-3">
          <div className="text-sm font-semibold mb-2">Top5%高风险节点（按公式优先级）</div>
          <div className="max-h-60 overflow-auto text-xs">
            <table className="w-full">
              <thead className="text-slate-400">
                <tr>
                  <th className="text-left py-1">企业</th>
                  <th className="text-left py-1">类型</th>
                  <th className="text-left py-1">优先级</th>
                  <th className="text-left py-1">Top标签数</th>
                </tr>
              </thead>
              <tbody>
                {topRiskNodes.map((n) => (
                  <tr key={n.node_id} className="border-t border-slate-700/70">
                    <td className="py-1 pr-2">{n.name}</td>
                    <td className="py-1 pr-2">{n.node_type}</td>
                    <td className="py-1 pr-2">{(nodeScore(n) * 100).toFixed(1)}%</td>
                    <td className="py-1">{n.top5_count || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="col-span-6 rounded-xl border border-slate-700 bg-slate-900/70 p-3">
          <div className="text-sm font-semibold mb-3">监管决策支持（目标1-3）</div>
          <div className="flex flex-wrap gap-3 items-end mb-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">企业类型</label>
              <select
                value={screeningType}
                onChange={(e) => setScreeningType(e.target.value)}
                className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm min-w-[150px]"
              >
                {['原奶供应商', '乳制品加工厂', '冷链仓储中心', '物流公司', '零售终端'].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Top-N</label>
              <input
                type="number"
                min={1}
                max={100}
                value={topN}
                onChange={(e) => setTopN(Number(e.target.value))}
                className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-20"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">预算</label>
              <input
                type="number"
                min={1}
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
              />
            </div>
            <button onClick={runScreening} className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm hover:bg-blue-500">
              1+2 初筛与排序
            </button>
            <button onClick={runResourcePlan} className="px-3 py-1.5 rounded bg-emerald-600 text-white text-sm hover:bg-emerald-500">
              3 预算分配
            </button>
          </div>

          <div className="text-xs text-slate-200 space-y-1">
            {screening ? (
              <div>候选企业总量: {screening.total_candidates}（展示Top {screening.top_n}）</div>
            ) : (
              <div className="text-slate-400">执行“1+2”后显示候选池规模。</div>
            )}
            {rankingEval ? (
              <>
                <div>Precision@{rankingEval.top_k}: {(rankingEval.precision_at_k * 100).toFixed(1)}%</div>
                <div>Recall@{rankingEval.top_k}: {(rankingEval.recall_at_k * 100).toFixed(1)}%</div>
              </>
            ) : (
              <div className="text-slate-400">执行“1+2”后显示排序指标。</div>
            )}

            {resourcePlan ? (
              <>
                <div>预算使用: {resourcePlan.budget_used.toFixed(2)} / {resourcePlan.budget.toFixed(2)}</div>
                <div>覆盖企业数: {resourcePlan.selected_count}</div>
                <div>预期风险覆盖: {(resourcePlan.expected_risk_covered * 100).toFixed(1)}%</div>
              </>
            ) : (
              <div className="text-slate-400">执行“3”后显示预算方案。</div>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-700 bg-slate-900/70 p-3">
        <div className="text-sm font-semibold mb-3">月度训练/测试 + 抽检反馈闭环（流程验证）</div>
        <div className="flex flex-wrap items-end gap-3 mb-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">训练月</label>
            <input
              value={trainMonth}
              onChange={(e) => setTrainMonth(e.target.value)}
              placeholder="YYYY-MM"
              className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-28"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">测试月</label>
            <input
              value={testMonth}
              onChange={(e) => setTestMonth(e.target.value)}
              placeholder="YYYY-MM"
              className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-28"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Top-K</label>
            <input
              type="number"
              min={10}
              max={500}
              value={simTopK}
              onChange={(e) => setSimTopK(Number(e.target.value))}
              className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">抽检数量</label>
            <input
              type="number"
              min={20}
              max={2000}
              value={inspectCount}
              onChange={(e) => setInspectCount(Number(e.target.value))}
              className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">探索权重</label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={exploreWeight}
              onChange={(e) => setExploreWeight(Number(e.target.value))}
              className="border border-slate-600 bg-slate-950 text-slate-100 rounded px-2 py-1.5 text-sm w-24"
            />
          </div>
          <button
            onClick={runTemporalSim}
            disabled={simLoading}
            className="px-3 py-1.5 rounded bg-violet-600 text-white text-sm hover:bg-violet-500 disabled:opacity-60"
          >
            {simLoading ? '模拟中...' : '执行月度模拟'}
          </button>
        </div>

        {!temporalSim && <div className="text-xs text-slate-400">用于展示跨月泛化与抽检反馈增益（弱监督流程验证）。</div>}

        {temporalSim && (
          <div className="grid grid-cols-12 gap-4 text-xs">
            <div className="col-span-4 rounded border border-slate-700 bg-slate-950/70 p-2 space-y-1">
              <div>训练月: {temporalSim.train_snapshot.month}，节点 {temporalSim.train_snapshot.node_count}，边 {temporalSim.train_snapshot.edge_count}</div>
              <div>测试月: {temporalSim.test_snapshot.month}，节点 {temporalSim.test_snapshot.node_count}，边 {temporalSim.test_snapshot.edge_count}</div>
              <div>抽检命中率: {(temporalSim.inspection.hit_rate * 100).toFixed(1)}%</div>
              <div>抽检阳性数: {temporalSim.inspection.positive_found}/{temporalSim.inspection.selected_count}</div>
              <div>反馈前风险分层: 高{temporalSim.risk_buckets_before.high} / 中{temporalSim.risk_buckets_before.medium} / 低{temporalSim.risk_buckets_before.low}</div>
              <div>反馈后风险分层: 高{temporalSim.risk_buckets_after_feedback.high} / 中{temporalSim.risk_buckets_after_feedback.medium} / 低{temporalSim.risk_buckets_after_feedback.low}</div>
            </div>
            <div className="col-span-4 rounded border border-slate-700 bg-slate-950/70 p-2 space-y-1">
              <div className="text-slate-300">反馈前指标</div>
              <div>Precision@{temporalSim.metrics_before.top_k}: {(temporalSim.metrics_before.precision_at_k * 100).toFixed(1)}%</div>
              <div>Recall@{temporalSim.metrics_before.top_k}: {(temporalSim.metrics_before.recall_at_k * 100).toFixed(1)}%</div>
              <div className="text-slate-300 pt-1">反馈后指标</div>
              <div>Precision@{temporalSim.metrics_after_feedback.top_k}: {(temporalSim.metrics_after_feedback.precision_at_k * 100).toFixed(1)}%</div>
              <div>Recall@{temporalSim.metrics_after_feedback.top_k}: {(temporalSim.metrics_after_feedback.recall_at_k * 100).toFixed(1)}%</div>
              <div className="pt-1 text-emerald-300">
                ΔPrecision: {((temporalSim.metrics_after_feedback.precision_at_k - temporalSim.metrics_before.precision_at_k) * 100).toFixed(1)}pp
              </div>
              <div className="text-emerald-300">
                ΔRecall: {((temporalSim.metrics_after_feedback.recall_at_k - temporalSim.metrics_before.recall_at_k) * 100).toFixed(1)}pp
              </div>
            </div>
            <div className="col-span-4 rounded border border-slate-700 bg-slate-950/70 p-2">
              <div className="text-slate-300 mb-1">建议</div>
              <div className="space-y-1">
                {(temporalSim.recommendations || []).map((x, idx) => (
                  <div key={`rec-${idx}`}>{idx + 1}. {x}</div>
                ))}
              </div>
            </div>

            <div className="col-span-12 rounded border border-slate-700 bg-slate-950/70 p-2">
              <div className="text-slate-300 mb-1">抽检样本（前30）</div>
              <div className="max-h-48 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="text-slate-400">
                    <tr>
                      <th className="text-left py-1">#</th>
                      <th className="text-left py-1">节点ID</th>
                      <th className="text-left py-1">预测分</th>
                      <th className="text-left py-1">不确定性</th>
                      <th className="text-left py-1">抽检标签</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(temporalSim.inspection.items || []).slice(0, 30).map((it) => (
                      <tr key={`${it.node_id}-${it.rank}`} className="border-t border-slate-700/70">
                        <td className="py-1">{it.rank}</td>
                        <td className="py-1">{it.node_id}</td>
                        <td className="py-1">{(it.predicted_score * 100).toFixed(1)}%</td>
                        <td className="py-1">{(it.uncertainty * 100).toFixed(1)}%</td>
                        <td className={`py-1 ${it.inspection_label === 1 ? 'text-rose-300' : 'text-emerald-300'}`}>{it.inspection_label}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 rounded-xl border border-slate-700 bg-slate-900/70 p-3">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">Mode A 结论与策略报告（LLM驱动）</div>
          <button
            onClick={runModeAReport}
            disabled={reportLoading}
            className="px-3 py-1.5 rounded bg-fuchsia-600 text-white text-sm hover:bg-fuchsia-500 disabled:opacity-60"
          >
            {reportLoading ? '生成中...' : '生成Mode A报告'}
          </button>
        </div>

        {!report && <div className="text-xs text-slate-400">点击按钮生成当前视图的结论与策略。</div>}

        {report && (
          <div className="grid grid-cols-12 gap-4 text-xs">
            <div className="col-span-4 border border-slate-700 rounded p-2 bg-slate-950/70">
              <div className="mb-1">风险等级: <b>{report.rule_summary.risk_level}</b></div>
              <div className="mb-1">综合分: <b>{report.rule_summary.risk_score.toFixed(2)}</b></div>
              <div className="mb-1">节点均值: {(report.rule_summary.avg_node_risk * 100).toFixed(1)}%</div>
              {report.rule_summary.avg_priority !== undefined && <div className="mb-1">优先级均值: {(report.rule_summary.avg_priority * 100).toFixed(1)}%</div>}
              <div className="mb-1">边均值: {(report.rule_summary.avg_edge_risk * 100).toFixed(1)}%</div>
              <div className="mb-1">不确定性: {(report.rule_summary.avg_uncertainty * 100).toFixed(1)}%</div>
              {report.rule_summary.avg_credibility !== undefined && <div className="mb-1">可信度: {(report.rule_summary.avg_credibility * 100).toFixed(1)}%</div>}
              <div className="mb-1">高风险节点数: {report.rule_summary.high_count}</div>
              <div>LLM: {report.llm.mock ? 'mock' : 'real'} / {report.llm.success ? 'success' : 'failed'}</div>
            </div>

            <div className="col-span-8 border border-slate-700 rounded p-2 bg-slate-950/70">
              {llmJSON ? (
                <div className="space-y-2">
                  <div>
                    <div className="text-slate-400">执行摘要</div>
                    <div>{String(llmJSON.executive_summary || '')}</div>
                  </div>
                  <div>
                    <div className="text-slate-400">关键风险因子</div>
                    <div>{Array.isArray(llmJSON.key_risk_factors) ? llmJSON.key_risk_factors.join('；') : ''}</div>
                  </div>
                  <div>
                    <div className="text-slate-400">立即行动项</div>
                    <div>{Array.isArray(llmJSON.immediate_actions) ? llmJSON.immediate_actions.join('；') : ''}</div>
                  </div>
                </div>
              ) : (
                <pre className="whitespace-pre-wrap text-slate-200 max-h-56 overflow-auto">
                  {report.llm.content || report.llm.error || '无可用报告内容'}
                </pre>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
