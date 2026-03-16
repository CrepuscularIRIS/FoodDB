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
import { useStreamingAgent, useStreamingAgentSSE } from '@/hooks/useStreamingAgent';
import LLMStreamDisplay from '@/components/LLMStreamDisplay';
import { ExclamationTriangleIcon, PlayIcon, ArrowsRightLeftIcon, LinkIcon, ChartBarIcon } from '@heroicons/react/24/outline';
import { addHistory } from '@/lib/history';

type AssessmentMode = 'supply_chain' | 'symptom_driven' | 'linked';

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

export default function Home() {
  const [mode, setMode] = useState<AssessmentMode>('supply_chain');
  const [report, setReport] = useState<RiskAssessmentReport | null>(null);
  const [symptomResult, setSymptomResult] = useState<SymptomAssessResult | null>(null);
  const [showStreaming, setShowStreaming] = useState(false);
  const [symptomLoading, setSymptomLoading] = useState(false);
  const [showStats, setShowStats] = useState(true);

  // 页面标题
  const PageHeader = () => (
    <div className="text-center mb-8 relative">
      {/* 版本标识 */}
      <div className="absolute top-0 right-0 flex items-center gap-2">
        <span className="px-3 py-1 bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-bold rounded-full shadow-lg">
          V2.0
        </span>
      </div>
      {/* 主标题 */}
      <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-indigo-600 bg-clip-text text-transparent mb-2 drop-shadow-sm">
        食品安全风险监管大屏
      </h1>
      <p className="text-gray-500 text-sm mt-2">
        智能供应链风险研判系统 | Food Safety Risk Monitoring Dashboard
      </p>
    </div>
  );
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

  // 当流式处理完成时，获取完整报告
  const handleComplete = async (query: string, withPropagation: boolean = false) => {
    try {
      const result = await assessmentApi.assess(query, withPropagation);
      if (result.success && result.data) {
        setReport(result.data);
        // 保存到历史记录
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
    // 如果有target_hint，使用精确的batch_id进行查询
    const actualQuery = targetHint?.batch_id || targetHint?.enterprise_id || query;
    await handleAssess(actualQuery);
    // 流式完成后获取报告
    setTimeout(() => handleComplete(actualQuery), 100);
  };

  const handleSearch = async (query: string, withPropagation: boolean) => {
    await handleAssess(query, withPropagation);
    // 流式完成后获取报告
    setTimeout(() => handleComplete(query, withPropagation), 100);
  };

  // 症状驱动评估
  const handleSymptomAssess = (result: SymptomAssessResult) => {
    setSymptomResult(result);
    setSymptomLoading(false);
  };

  const switchMode = (newMode: AssessmentMode) => {
    setMode(newMode);
    // 清除之前的结果
    setReport(null);
    setSymptomResult(null);
    setShowStreaming(false);
  };

  return (
    <div className="space-y-8">
      {/* 页面标题 */}
      <PageHeader />

      {/* 模式切换器 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-1">
        <div className="flex space-x-1">
          <button
            onClick={() => switchMode('supply_chain')}
            className={`flex-1 flex items-center justify-center px-4 py-3 rounded-lg text-sm font-medium transition-all ${
              mode === 'supply_chain'
                ? 'bg-blue-600 text-white shadow-md'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            <ArrowsRightLeftIcon className="h-4 w-4 mr-2" />
            供应链研判 (Mode A)
          </button>
          <button
            onClick={() => switchMode('symptom_driven')}
            className={`flex-1 flex items-center justify-center px-4 py-3 rounded-lg text-sm font-medium transition-all ${
              mode === 'symptom_driven'
                ? 'bg-rose-600 text-white shadow-md'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
            症状驱动研判 (Mode B)
          </button>
          <button
            onClick={() => switchMode('linked')}
            className={`flex-1 flex items-center justify-center px-4 py-3 rounded-lg text-sm font-medium transition-all ${
              mode === 'linked'
                ? 'bg-violet-600 text-white shadow-md'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            <LinkIcon className="h-4 w-4 mr-2" />
            联动研判 (A+B)
          </button>
        </div>
      </div>

      {/* 风险统计仪表盘 */}
      {mode === 'supply_chain' && showStats && (
        <div className="relative">
          <RiskStatsCard onClose={() => setShowStats(false)} />
        </div>
      )}

      {/* Mode A: 供应链研判 */}
      {mode === 'supply_chain' && (
        <>
          {/* 搜索面板 */}
          <SearchPanel
            onSearch={handleSearch}
            loading={state.currentStep !== null}
          />

          {/* 演示案例 */}
          {!report && !showStreaming && (
            <DemoCases onSelect={handleDemoSelect} />
          )}

          {/* 错误提示 - 增强版 */}
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

          {/* 流式处理状态 */}
          {showStreaming && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 左侧：流程步骤 */}
              <div>
                <WorkflowSteps
                  steps={state.steps}
                  currentStep={state.currentStep}
                  isComplete={state.isComplete}
                />
              </div>

              {/* 右侧：实时数据展示 */}
              <div className="space-y-4">
                {/* 当前步骤详情 */}
                {state.currentStep && (
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <h3 className="text-sm font-medium text-blue-900 flex items-center">
                      <PlayIcon className="h-4 w-4 mr-2" />
                      正在执行
                    </h3>
                    <p className="text-sm text-blue-700 mt-1">
                      {state.steps.find(s => s.step === state.currentStep)?.message || '处理中...'}
                    </p>
                  </div>
                )}

                {/* LLM 流式输出显示 */}
                {(llmStreamContent.length > 0 || state.steps.some(s => s.step === 'llm_analysis')) && (
                  <LLMStreamDisplay
                    streamContent={llmStreamContent}
                    isActive={state.currentStep === 'llm_analysis' || state.steps.some(s => s.step === 'llm_analysis' && s.status !== 'complete')}
                  />
                )}

                {/* 已完成的步骤摘要 */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3">处理摘要</h3>
                  <div className="space-y-2 text-sm">
                    {state.steps
                      .filter(s => s.status === 'complete' || s.status === 'data')
                      .slice(-5)
                      .map((step, idx) => (
                        <div key={idx} className="flex items-center text-gray-600">
                          <span className="w-2 h-2 bg-green-500 rounded-full mr-2" />
                          <span className="truncate">{step.message}</span>
                        </div>
                      ))}
                  </div>
                </div>

                {/* 完成提示 */}
                {state.isComplete && (
                  <div className="bg-green-50 rounded-lg p-4 border border-green-200 text-center">
                    <p className="text-green-800 font-medium">研判完成！</p>
                    <p className="text-sm text-green-600 mt-1">下方显示完整报告</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 报告展示 */}
          {report && (
            <ReportView report={report} />
          )}
        </>
      )}

      {/* Mode B: 症状驱动研判 */}
      {mode === 'symptom_driven' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左侧：搜索面板 */}
          <div>
            <SymptomSearchPanel
              onAssess={handleSymptomAssess}
              loading={symptomLoading}
            />
          </div>

          {/* 右侧：结果展示 */}
          <div>
            <SymptomRiskResult result={symptomResult} />
            {!symptomResult && !symptomLoading && (
              <div className="bg-gray-50 rounded-xl p-8 text-center border border-gray-200 border-dashed">
                <div className="w-16 h-16 bg-rose-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="h-8 w-8 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-700 mb-2">
                  请输入症状描述
                </h3>
                <p className="text-sm text-gray-500 max-w-sm mx-auto">
                  在左侧输入症状（如腹泻、发热、呕吐等），系统将自动推断风险因子并关联供应链企业
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mode A+B: 联动研判 */}
      {mode === 'linked' && (
        <LinkedWorkflowPanel />
      )}
    </div>
  );
}
