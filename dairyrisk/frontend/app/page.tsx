'use client';

import { useState } from 'react';
import { assessmentApi } from '@/lib/api';
import { RiskAssessmentReport, TargetHint } from '@/types';
import SearchPanel from '@/components/SearchPanel';
import ReportView from '@/components/ReportView';
import DemoCases from '@/components/DemoCases';
import WorkflowSteps from '@/components/WorkflowSteps';
import SymptomSearchPanel from '@/components/SymptomSearchPanel';
import SymptomRiskResult from '@/components/SymptomRiskResult';
import LinkedWorkflowPanel from '@/components/LinkedWorkflowPanel';
import RiskStatsCard from '@/components/RiskStatsCard';
import ModelAControlTower from '@/components/modela/ModelAControlTower';
import { useStreamingAgentSSE } from '@/hooks/useStreamingAgent';
import LLMStreamDisplay from '@/components/LLMStreamDisplay';
import {
  ExclamationTriangleIcon,
  PlayIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  BeakerIcon,
  LinkIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline';
import { addHistory } from '@/lib/history';

interface SymptomAssessResult {
  query: string;
  symptoms_detected: Array<{
    symptom: string;
    symptom_id: string;
    source: string;
  }>;
  risk_factors: Array<{
    risk_factor_id: string;
    name: string;
    category: string;
    description: string;
    score: number;
    typical_sources: string[];
    linked_stages: string[];
  }>;
  stage_candidates: Array<{
    stage: string;
    score: number;
    related_risks: string[];
  }>;
  linked_enterprises: Array<{
    enterprise_id: string;
    enterprise_name: string;
    node_type: string;
    risk_score: number;
    risk_level: 'high' | 'medium' | 'low';
    reasons: string[];
    credit_rating: string;
    historical_violations: number;
  }>;
  risk_level: 'high' | 'medium' | 'low';
  confidence: number;
  suggested_actions: string[];
}

function SectionCard({
  title,
  subtitle,
  icon,
  open,
  onToggle,
  children,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between rounded-2xl px-5 py-4 text-left hover:bg-gray-50"
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded-lg bg-gray-100 p-2 text-gray-700">{icon}</div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
            <p className="text-sm text-gray-500">{subtitle}</p>
          </div>
        </div>
        {open ? <ChevronUpIcon className="h-5 w-5 text-gray-500" /> : <ChevronDownIcon className="h-5 w-5 text-gray-500" />}
      </button>
      {open && <div className="border-t border-gray-100 px-5 py-5">{children}</div>}
    </section>
  );
}

export default function Home() {
  const [report, setReport] = useState<RiskAssessmentReport | null>(null);
  const [symptomResult, setSymptomResult] = useState<SymptomAssessResult | null>(null);
  const [showStreaming, setShowStreaming] = useState(false);
  const [symptomLoading, setSymptomLoading] = useState(false);
  const [showStats, setShowStats] = useState(true);

  const [openClassicA, setOpenClassicA] = useState(false);
  const [openModeB, setOpenModeB] = useState(true);
  const [openLinked, setOpenLinked] = useState(false);

  const { state, execute, reset, llmStreamContent } = useStreamingAgentSSE();

  const handleAssess = async (query: string, withPropagation: boolean = false) => {
    setReport(null);
    setShowStreaming(true);
    reset();

    try {
      await execute(query, withPropagation);
    } catch (err) {
      console.error('研判失败:', err);
    }
  };

  const handleComplete = async (query: string, withPropagation: boolean = false) => {
    try {
      const result = await assessmentApi.assess(query, withPropagation);
      if (result.success && result.data) {
        setReport(result.data);
        addHistory({
          query,
          targetType: result.data.target_type,
          targetName: result.data.target_name,
          riskLevel: result.data.risk_level,
          riskScore: result.data.risk_score,
          report: result.data,
        });
      }
    } catch (err: any) {
      console.error('获取报告失败:', err);
    }
  };

  const handleDemoSelect = async (query: string, targetHint?: TargetHint) => {
    const actualQuery = targetHint?.batch_id || targetHint?.enterprise_id || query;
    await handleAssess(actualQuery);
    setTimeout(() => handleComplete(actualQuery), 100);
  };

  const handleSearch = async (query: string, withPropagation: boolean) => {
    await handleAssess(query, withPropagation);
    setTimeout(() => handleComplete(query, withPropagation), 100);
  };

  const handleSymptomAssess = (result: SymptomAssessResult) => {
    setSymptomResult(result);
    setSymptomLoading(false);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-300 bg-gradient-to-r from-slate-900 via-blue-900 to-slate-800 px-6 py-6 text-white shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold">乳制品供应链风险监管工作站</h1>
            <p className="mt-1 text-sm text-blue-100">统一入口：ModelA 闭环预测 + ModeB 证据输入 + A+B 联动研判</p>
            <p className="mt-1 text-xs text-blue-200">核心数据: dataset_3_24（4,276 节点 / 209,982 边）+ 7类风险 + 智能抽检闭环</p>
          </div>
          <div className="rounded-full bg-white/15 px-3 py-1 text-xs font-semibold">Unified Dashboard v2.1</div>
        </div>
      </div>

      <ModelAControlTower />

      {showStats && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-800">基础风险统计面板（旧版能力保留）</h3>
            <button
              type="button"
              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
              onClick={() => setShowStats(false)}
            >
              收起
            </button>
          </div>
          <RiskStatsCard onClose={() => setShowStats(false)} />
        </div>
      )}

      <SectionCard
        title="Mode A 经典检索与流式报告（兼容旧链路）"
        subtitle="保留搜索、演示案例、LLM步骤流和详细报告，和新的 ModelA v2 并行共存"
        icon={<ArrowsRightLeftIcon className="h-5 w-5" />}
        open={openClassicA}
        onToggle={() => setOpenClassicA((v) => !v)}
      >
        <div className="space-y-6">
          <SearchPanel onSearch={handleSearch} loading={state.currentStep !== null} />

          {!report && !showStreaming && <DemoCases onSelect={handleDemoSelect} />}

          {state.isError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <h3 className="text-sm font-medium text-red-800">研判请求失败</h3>
                  {state.error?.includes('\n') ? (
                    <div className="mt-2">
                      {state.error.split('\n').map((line, idx) => (
                        <p key={idx} className={`text-sm ${line.startsWith('  •') ? 'text-red-600 ml-4' : 'text-red-700 font-medium'}`}>
                          {line}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-red-600 mt-1">{state.error}</p>
                  )}
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => setShowStreaming(false)}
                  className="text-xs bg-red-100 hover:bg-red-200 text-red-700 px-3 py-1.5 rounded transition-colors"
                >
                  关闭提示
                </button>
                <button
                  onClick={() => {
                    setShowStreaming(false);
                    window.open('/history', '_blank');
                  }}
                  className="text-xs bg-white border border-red-200 hover:bg-red-50 text-red-700 px-3 py-1.5 rounded transition-colors"
                >
                  查看历史记录
                </button>
              </div>
            </div>
          )}

          {showStreaming && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <WorkflowSteps steps={state.steps} currentStep={state.currentStep} isComplete={state.isComplete} />
              </div>
              <div className="space-y-4">
                {state.currentStep && (
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <h3 className="text-sm font-medium text-blue-900 flex items-center">
                      <PlayIcon className="h-4 w-4 mr-2" />
                      正在执行
                    </h3>
                    <p className="text-sm text-blue-700 mt-1">{state.steps.find((s) => s.step === state.currentStep)?.message || '处理中...'}</p>
                  </div>
                )}

                {(llmStreamContent.length > 0 || state.steps.some((s) => s.step === 'llm_analysis')) && (
                  <LLMStreamDisplay
                    streamContent={llmStreamContent}
                    isActive={state.currentStep === 'llm_analysis' || state.steps.some((s) => s.step === 'llm_analysis' && s.status !== 'complete')}
                  />
                )}

                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3">处理摘要</h3>
                  <div className="space-y-2 text-sm">
                    {state.steps
                      .filter((s) => s.status === 'complete' || s.status === 'data')
                      .slice(-5)
                      .map((step, idx) => (
                        <div key={idx} className="flex items-center text-gray-600">
                          <span className="w-2 h-2 bg-green-500 rounded-full mr-2" />
                          <span className="truncate">{step.message}</span>
                        </div>
                      ))}
                  </div>
                </div>

                {state.isComplete && (
                  <div className="bg-green-50 rounded-lg p-4 border border-green-200 text-center">
                    <p className="text-green-800 font-medium">研判完成</p>
                    <p className="text-sm text-green-600 mt-1">下方显示完整报告</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {report && <ReportView report={report} />}
        </div>
      </SectionCard>

      <SectionCard
        title="Mode B 症状驱动研判"
        subtitle="输入症状证据并关联供应链节点，作为闭环证据入口"
        icon={<BeakerIcon className="h-5 w-5" />}
        open={openModeB}
        onToggle={() => setOpenModeB((v) => !v)}
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <SymptomSearchPanel onAssess={handleSymptomAssess} loading={symptomLoading} />
          </div>
          <div>
            <SymptomRiskResult result={symptomResult} />
            {!symptomResult && !symptomLoading && (
              <div className="bg-gray-50 rounded-xl p-8 text-center border border-gray-200 border-dashed">
                <div className="w-16 h-16 bg-rose-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="h-8 w-8 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-700 mb-2">请输入症状描述</h3>
                <p className="text-sm text-gray-500 max-w-sm mx-auto">如腹泻、发热、呕吐，系统会推断风险因子并映射到候选企业。</p>
              </div>
            )}
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="A+B 联动研判"
        subtitle="症状证据 -> 供应链核查 -> 联合报告的全链路执行"
        icon={<LinkIcon className="h-5 w-5" />}
        open={openLinked}
        onToggle={() => setOpenLinked((v) => !v)}
      >
        <LinkedWorkflowPanel />
      </SectionCard>
    </div>
  );
}
