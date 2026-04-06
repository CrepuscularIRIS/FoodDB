'use client';

import type { ModelAIntegratedClosedLoopResponse } from '@/types';

interface Props {
  integrated: ModelAIntegratedClosedLoopResponse | null;
}

function StepCard({
  idx,
  title,
  desc,
  status,
}: {
  idx: number;
  title: string;
  desc: string;
  status: 'ready' | 'pending';
}) {
  const ready = status === 'ready';
  return (
    <div className={`rounded-xl border p-3 ${ready ? 'border-emerald-600/60 bg-emerald-950/20' : 'border-slate-700 bg-slate-950/60'}`}>
      <div className="text-[11px] text-slate-400 mb-1">阶段 {idx}</div>
      <div className="text-sm font-semibold mb-1">{title}</div>
      <div className="text-xs text-slate-300">{desc}</div>
      <div className={`mt-2 inline-flex rounded px-2 py-0.5 text-[11px] ${ready ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-700/60 text-slate-300'}`}>
        {ready ? '已完成' : '待执行'}
      </div>
    </div>
  );
}

export default function WorkflowPipeline({ integrated }: Props) {
  const ready = !!integrated;
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-3">
      <div className="text-sm font-semibold mb-2">L2 机制层：风险闭环流水线</div>
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 md:col-span-3">
          <StepCard
            idx={1}
            title="风险感知"
            desc="节点/边 7类风险概率 + priority 生成候选。"
            status={ready ? 'ready' : 'pending'}
          />
        </div>
        <div className="col-span-12 md:col-span-3">
          <StepCard
            idx={2}
            title="抽检优化"
            desc="基于风险收益/成本/不确定性进行双目标选择。"
            status={ready ? 'ready' : 'pending'}
          />
        </div>
        <div className="col-span-12 md:col-span-3">
          <StepCard
            idx={3}
            title="反馈更新"
            desc="抽检阳性/阴性回写，更新节点与边风险张量。"
            status={ready ? 'ready' : 'pending'}
          />
        </div>
        <div className="col-span-12 md:col-span-3">
          <StepCard
            idx={4}
            title="传播推演"
            desc="12小时 预测路径 vs 真实路径 对照评估。"
            status={ready ? 'ready' : 'pending'}
          />
        </div>
      </div>
    </div>
  );
}
