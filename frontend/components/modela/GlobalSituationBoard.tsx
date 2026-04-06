'use client';

import type { ModelAV2GraphView, ModelAIntegratedClosedLoopResponse } from '@/types';

function pct(v?: number | null, d: number = 1): string {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return '--';
  return `${(Number(v) * 100).toFixed(d)}%`;
}

interface Props {
  graph: ModelAV2GraphView | null;
  integrated: ModelAIntegratedClosedLoopResponse | null;
}

export default function GlobalSituationBoard({ graph, integrated }: Props) {
  const nodeCount = graph?.meta?.node_count ?? 0;
  const edgeCount = graph?.meta?.edge_count ?? 0;
  const highNodeCount = (graph?.nodes || []).filter((n) => {
    const s = Number(n.priority_score ?? n.risk_proxy ?? n.view_risk_score ?? n.risk_score ?? 0);
    return s >= 0.72;
  }).length;
  const highEdgeCount = (graph?.edges || []).filter((e) => {
    const s = Number(e.edge_priority ?? e.edge_risk_proxy ?? e.view_risk_score ?? 0);
    return s >= 0.72;
  }).length;

  const gain = integrated?.optimization?.gain_pp;
  const hit = integrated?.feedback?.hit_rate;
  const reduction = integrated?.inspection_strategy?.expected_risk_reduction_proxy;
  const frames = integrated?.propagation?.frames || [];
  const peakPred = frames.length > 0 ? Math.max(...frames.map((x) => Number(x.predicted_max_score || 0))) : null;
  const peakReal = frames.length > 0 ? Math.max(...frames.map((x) => Number(x.real_max_score || 0))) : null;

  const autoSummary = integrated
    ? `闭环已执行：抽检命中率 ${pct(hit)}，节点Precision增益 ${gain?.node_precision_pp?.toFixed(2) ?? '--'}pp，边Precision增益 ${gain?.edge_precision_pp?.toFixed(2) ?? '--'}pp，建议优先复核高风险传播路径。`
    : '尚未执行闭环模拟。建议先运行“整合闭环”，再查看传播峰值与策略增益。';

  const cardCls = 'rounded-xl border border-slate-700 bg-slate-950/70 p-3';

  return (
    <div className="rounded-xl border border-cyan-700/60 bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/20 p-3">
      <div className="text-sm font-semibold text-cyan-100 mb-2">L1 总览层：监管决策看板</div>
      <div className="grid grid-cols-12 gap-3 text-xs">
        <div className={`${cardCls} col-span-12 md:col-span-3`}>
          <div className="text-slate-400 mb-1">图谱规模</div>
          <div>节点: <span className="text-white font-semibold">{nodeCount}</span></div>
          <div>边: <span className="text-white font-semibold">{edgeCount}</span></div>
          <div>高风险节点: <span className="text-rose-300 font-semibold">{highNodeCount}</span></div>
          <div>高风险边: <span className="text-rose-300 font-semibold">{highEdgeCount}</span></div>
        </div>

        <div className={`${cardCls} col-span-12 md:col-span-3`}>
          <div className="text-slate-400 mb-1">抽检执行</div>
          <div>命中率: <span className="text-emerald-300 font-semibold">{pct(hit)}</span></div>
          <div>抽检对象: <span className="text-white font-semibold">{integrated?.inspection_strategy?.selected_count ?? '--'}</span></div>
          <div>节点/边: <span className="text-white">{integrated?.inspection_strategy?.node_selected ?? '--'} / {integrated?.inspection_strategy?.edge_selected ?? '--'}</span></div>
          <div>风险压制代理: <span className="text-cyan-300 font-semibold">{pct(reduction, 2)}</span></div>
        </div>

        <div className={`${cardCls} col-span-12 md:col-span-3`}>
          <div className="text-slate-400 mb-1">排序增益（反馈后）</div>
          <div>节点 Precision: <span className="text-emerald-300 font-semibold">{gain?.node_precision_pp?.toFixed(2) ?? '--'}pp</span></div>
          <div>节点 Recall: <span className="text-emerald-300 font-semibold">{gain?.node_recall_pp?.toFixed(2) ?? '--'}pp</span></div>
          <div>边 Precision: <span className="text-emerald-300 font-semibold">{gain?.edge_precision_pp?.toFixed(2) ?? '--'}pp</span></div>
          <div>边 Recall: <span className="text-emerald-300 font-semibold">{gain?.edge_recall_pp?.toFixed(2) ?? '--'}pp</span></div>
        </div>

        <div className={`${cardCls} col-span-12 md:col-span-3`}>
          <div className="text-slate-400 mb-1">传播态势 (12h)</div>
          <div>峰值(预测): <span className="text-amber-300 font-semibold">{pct(peakPred, 2)}</span></div>
          <div>峰值(真实): <span className="text-rose-300 font-semibold">{pct(peakReal, 2)}</span></div>
          <div>时序帧数: <span className="text-white font-semibold">{frames.length || '--'}</span></div>
          <div>种子节点: <span className="text-white">{integrated?.propagation?.seed_nodes?.length ?? '--'}</span></div>
        </div>
      </div>
      <div className="mt-2 rounded border border-slate-700 bg-slate-950/60 p-2 text-xs text-slate-200">
        <span className="text-cyan-300 font-medium">自动简报：</span>{autoSummary}
      </div>
    </div>
  );
}
