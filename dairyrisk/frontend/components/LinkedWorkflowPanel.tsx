'use client';

import { useState, useCallback, useRef } from 'react';
import {
  PlayIcon,
  StopIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  BeakerIcon,
  ArrowRightIcon,
  BuildingStorefrontIcon,
  MagnifyingGlassIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { linkedWorkflowApi } from '@/lib/api';
import {
  WorkflowStepEvent,
  LinkedWorkflowRequest,
  LinkedReport,
  WorkflowStep,
  StepStatus,
  RiskAssessmentReport,
} from '@/types';
import ReportView from './ReportView';

interface StepConfig {
  id: WorkflowStep;
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
  borderColor: string;
}

const stepConfigs: StepConfig[] = [
  {
    id: 'workflow_start',
    label: '启动联动工作流',
    description: '初始化 Mode A/B 联动研判流程',
    icon: ClockIcon,
    color: 'text-gray-600',
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
  },
  {
    id: 'mode_b_analysis',
    label: 'Mode B: 症状分析',
    description: '分析症状，推断风险因子和疑似环节',
    icon: BeakerIcon,
    color: 'text-rose-600',
    bgColor: 'bg-rose-50',
    borderColor: 'border-rose-200',
  },
  {
    id: 'hypothesis_generation',
    label: '生成风险假设',
    description: '构建 RiskHypothesis，确定候选企业范围',
    icon: MagnifyingGlassIcon,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
  },
  {
    id: 'mode_a_verification',
    label: 'Mode A: 企业核查',
    description: '对候选企业进行供应链风险研判',
    icon: BuildingStorefrontIcon,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
  },
  {
    id: 'report_generation',
    label: '生成联合报告',
    description: '整合双模式证据，生成完整报告',
    icon: DocumentTextIcon,
    color: 'text-violet-600',
    bgColor: 'bg-violet-50',
    borderColor: 'border-violet-200',
  },
  {
    id: 'workflow_complete',
    label: '研判完成',
    description: '联动研判流程全部完成',
    icon: ShieldCheckIcon,
    color: 'text-emerald-600',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
  },
];

interface WorkflowStepDisplayProps {
  config: StepConfig;
  status: StepStatus | 'pending';
  isActive: boolean;
  data?: any;
  isLast: boolean;
}

function WorkflowStepDisplay({ config, status, isActive, data, isLast }: WorkflowStepDisplayProps) {
  const Icon = config.icon;

  const getStatusStyles = () => {
    switch (status) {
      case 'started':
      case 'in_progress':
        return {
          container: `bg-gradient-to-r ${config.bgColor} to-white ${config.borderColor} shadow-lg ring-2 ring-offset-2 ring-blue-400`,
          icon: 'bg-blue-500 text-white animate-pulse',
          badge: 'bg-blue-100 text-blue-700 border-blue-200',
          badgeText: '进行中',
        };
      case 'complete':
        return {
          container: 'bg-white border-emerald-200 hover:border-emerald-300 shadow-sm',
          icon: 'bg-emerald-500 text-white',
          badge: 'bg-emerald-100 text-emerald-700 border-emerald-200',
          badgeText: '已完成',
        };
      case 'error':
        return {
          container: 'bg-rose-50 border-rose-300 shadow-sm',
          icon: 'bg-rose-500 text-white',
          badge: 'bg-rose-100 text-rose-700 border-rose-200',
          badgeText: '出错',
        };
      default:
        return {
          container: 'bg-gray-50/50 border-gray-200 opacity-60',
          icon: 'bg-gray-200 text-gray-400',
          badge: 'bg-gray-100 text-gray-400 border-gray-200',
          badgeText: '待执行',
        };
    }
  };

  const styles = getStatusStyles();

  return (
    <div className={`relative rounded-xl border-2 transition-all duration-500 ${styles.container}`}>
      <div className="flex items-start p-4">
        {/* Icon */}
        <div className="relative z-10 flex-shrink-0">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${styles.icon}`}>
            {status === 'complete' ? (
              <CheckCircleIcon className="h-6 w-6" />
            ) : (
              <Icon className="h-6 w-6" />
            )}
          </div>
          {/* Connector line */}
          {!isLast && (
            <div className={`absolute top-12 left-1/2 transform -translate-x-1/2 w-0.5 h-8 ${
              status === 'complete' ? 'bg-emerald-400' : 'bg-gray-200'
            }`} />
          )}
        </div>

        {/* Content */}
        <div className="ml-4 flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div>
              <h4 className={`text-sm font-semibold ${config.color}`}>
                {config.label}
              </h4>
              <p className="text-xs text-gray-500 mt-0.5">
                {config.description}
              </p>
            </div>
            <span className={`text-xs px-2.5 py-1 rounded-full border ${styles.badge}`}>
              {styles.badgeText}
            </span>
          </div>

          {/* Step-specific data display */}
          {data && (
            <div className="mt-3 space-y-2">
              {config.id === 'mode_b_analysis' && data.risk_factors && (
                <div className="flex flex-wrap gap-1">
                  {data.risk_factors.map((factor: string, idx: number) => (
                    <span key={idx} className="px-2 py-0.5 bg-rose-100 text-rose-700 rounded text-xs">
                      {factor}
                    </span>
                  ))}
                </div>
              )}

              {config.id === 'hypothesis_generation' && data.suspected_stage && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">疑似环节:</span>
                    <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-medium">
                      {data.suspected_stage}
                    </span>
                    <span className="text-xs text-gray-500 ml-2">置信度:</span>
                    <span className={`text-xs font-medium ${
                      data.confidence === 'high' ? 'text-emerald-600' :
                      data.confidence === 'medium' ? 'text-amber-600' : 'text-gray-600'
                    }`}>
                      {data.confidence === 'high' ? '高' : data.confidence === 'medium' ? '中' : '低'}
                    </span>
                  </div>
                  {data.matched_enterprises && (
                    <div className="text-xs text-gray-600">
                      匹配企业: <span className="font-medium text-blue-600">{data.matched_enterprises.length}</span> 家
                    </div>
                  )}
                </div>
              )}

              {config.id === 'mode_a_verification' && data.matched_enterprises && (
                <div className="text-xs text-gray-600">
                  匹配企业: <span className="font-medium text-blue-600">{data.matched_enterprises.length}</span> 家
                </div>
              )}

              {config.id === 'report_generation' && data.report_id && (
                <div className="text-xs text-gray-600">
                  报告ID: <span className="font-mono text-violet-600">{data.report_id.slice(0, 16)}...</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LinkedWorkflowPanel() {
  const [query, setQuery] = useState('');
  const [population, setPopulation] = useState('');
  const [locationHint, setLocationHint] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<WorkflowStepEvent[]>([]);
  const [currentStep, setCurrentStep] = useState<WorkflowStep | null>(null);
  const [result, setResult] = useState<LinkedReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const handleStep = useCallback((event: WorkflowStepEvent) => {
    setSteps(prev => {
      // Replace existing step or add new one
      const filtered = prev.filter(s => s.step !== event.step);
      return [...filtered, event];
    });
    setCurrentStep(event.step);
  }, []);

  const handleComplete = useCallback((data: any) => {
    setIsRunning(false);
    // Backend returns report in 'output' or 'result' field
    const reportData = data.result || data.output;
    if (reportData) {
      setResult(reportData);
    }
  }, []);

  const handleError = useCallback((err: string) => {
    setError(err);
    setIsRunning(false);
  }, []);

  const startWorkflow = useCallback(() => {
    if (!query.trim()) return;

    setIsRunning(true);
    setSteps([]);
    setCurrentStep(null);
    setResult(null);
    setError(null);

    const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    // Convert population string to object format expected by backend
    const populationObj = population
      ? {
          age_group: population,
          case_count: 1,
          region: locationHint || undefined,
        }
      : undefined;

    // Use fetch with readable stream to handle SSE from POST request
    const requestBody = {
      symptom_description: query,
      population: populationObj,
      location_hint: locationHint || undefined,
      top_k: 5,
    };

    const abortController = new AbortController();

    fetch(`${baseURL}/linked_workflow_stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(requestBody),
      signal: abortController.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        if (!response.body) {
          throw new Error('No response body');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        const processStream = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n\n');
              buffer = lines.pop() || '';

              for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith('data: ')) continue;

                const dataStr = trimmed.slice(6); // Remove 'data: ' prefix
                if (!dataStr) continue;

                try {
                  const data = JSON.parse(dataStr);
                  console.log('[SSE] Received:', data);

                  if (data.step && data.status) {
                    handleStep(data as WorkflowStepEvent);

                    // Check for workflow completion
                    if (data.step === 'workflow_complete' && data.status === 'complete') {
                      handleComplete(data);
                      return;
                    }

                    // Check for errors
                    if (data.status === 'failed' || data.status === 'error') {
                      handleError(data.error || '工作流执行失败');
                      return;
                    }
                  }

                  if (data.step === 'stream_end') {
                    return;
                  }
                } catch (err) {
                  console.error('[SSE] Parse error:', err, 'Data:', dataStr);
                }
              }
            }
          } catch (err: any) {
            if (err.name === 'AbortError') {
              console.log('[SSE] Aborted');
            } else {
              handleError(err.message || '流读取失败');
            }
          }
        };

        processStream();
      })
      .catch((err) => {
        handleError(err.message || '请求失败');
      });

    abortRef.current = () => {
      abortController.abort();
      setIsRunning(false);
    };
  }, [query, population, locationHint, handleStep, handleComplete, handleError]);

  const stopWorkflow = useCallback(() => {
    if (abortRef.current) {
      abortRef.current();
    }
  }, []);

  const resetWorkflow = useCallback(() => {
    setQuery('');
    setPopulation('');
    setLocationHint('');
    setSteps([]);
    setCurrentStep(null);
    setResult(null);
    setError(null);
    setIsRunning(false);
  }, []);

  // Get step data for display
  const getStepData = (stepId: WorkflowStep) => {
    const stepEvent = steps.find(s => s.step === stepId);
    return stepEvent?.data;
  };

  // Get step status
  const getStepStatus = (stepId: WorkflowStep): StepStatus | 'pending' => {
    const stepEvent = steps.find(s => s.step === stepId);
    if (!stepEvent) return 'pending';
    return stepEvent.status;
  };

  // Transform linked report to RiskAssessmentReport for ReportView
  const transformToReport = (linkedReport: LinkedReport): RiskAssessmentReport | null => {
    if (!linkedReport.enterprise_assessments || linkedReport.enterprise_assessments.length === 0) {
      return null;
    }
    // Use the first enterprise assessment as the main report
    const assessment = linkedReport.enterprise_assessments[0] as any;
    // The actual report data is in risk_assessment field or directly in the assessment object
    const mainReport = assessment.risk_assessment || assessment;

    if (!mainReport || !mainReport.report_id) {
      return null;
    }

    // Handle both old and new response formats for conclusion
    const conclusion = linkedReport.combined_conclusion ||
                       linkedReport.conclusion ||
                       (linkedReport.evidence_chain ? JSON.stringify(linkedReport.evidence_chain, null, 2) : '');

    return {
      ...mainReport,
      // Add combined conclusion as LLM analysis
      llm_analysis: conclusion,
    };
  };

  const reportForView = result ? transformToReport(result) : null;

  return (
    <div className="space-y-6">
      {/* Input Panel */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <ArrowPathIcon className="h-5 w-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Mode A/B 联动研判</h3>
            <p className="text-sm text-gray-500">症状驱动 → 风险假设 → 企业核查 → 联合报告</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              症状描述 <span className="text-rose-500">*</span>
            </label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="请输入症状描述，如：腹泻、发热、腹痛..."
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              rows={3}
              disabled={isRunning}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                人群类型
              </label>
              <select
                value={population}
                onChange={(e) => setPopulation(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isRunning}
              >
                <option value="">不限</option>
                <option value="infant">婴幼儿</option>
                <option value="child">儿童</option>
                <option value="adult">成人</option>
                <option value="elderly">老年人</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                地理位置提示
              </label>
              <input
                type="text"
                value={locationHint}
                onChange={(e) => setLocationHint(e.target.value)}
                placeholder="如：上海、浦东..."
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isRunning}
              />
            </div>
          </div>

          <div className="flex gap-3">
            {!isRunning ? (
              <button
                onClick={startWorkflow}
                disabled={!query.trim()}
                className="flex-1 flex items-center justify-center px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-medium hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <PlayIcon className="h-5 w-5 mr-2" />
                启动联动研判
              </button>
            ) : (
              <button
                onClick={stopWorkflow}
                className="flex-1 flex items-center justify-center px-6 py-3 bg-rose-600 text-white rounded-lg font-medium hover:bg-rose-700 transition-all"
              >
                <StopIcon className="h-5 w-5 mr-2" />
                停止研判
              </button>
            )}

            {(result || error) && (
              <button
                onClick={resetWorkflow}
                className="px-6 py-3 border border-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-all"
              >
                <ArrowPathIcon className="h-5 w-5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <ExclamationCircleIcon className="h-5 w-5 text-rose-600" />
            <div>
              <h4 className="text-sm font-medium text-rose-800">研判失败</h4>
              <p className="text-sm text-rose-600">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Workflow Steps */}
      {(isRunning || steps.length > 0) && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h4 className="text-sm font-semibold text-gray-900 flex items-center">
              <ClockIcon className="h-4 w-4 mr-2 text-blue-500" />
              处理流程
            </h4>
            {isRunning && (
              <span className="text-xs text-blue-600 animate-pulse">
                处理中...
              </span>
            )}
          </div>

          <div className="space-y-4">
            {stepConfigs.map((config, index) => (
              <WorkflowStepDisplay
                key={config.id}
                config={config}
                status={getStepStatus(config.id)}
                isActive={currentStep === config.id}
                data={getStepData(config.id)}
                isLast={index === stepConfigs.length - 1}
              />
            ))}
          </div>
        </div>
      )}

      {/* Matched Enterprises Summary */}
      {result?.enterprise_assessments && result.enterprise_assessments.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center">
            <BuildingStorefrontIcon className="h-4 w-4 mr-2 text-blue-500" />
            匹配企业 ({result.enterprise_assessments.length}家)
          </h4>
          <div className="space-y-3">
            {result.enterprise_assessments.map((assessment: any, idx: number) => {
              // 处理不同的数据结构
              const entId = assessment.enterprise_id || (assessment.risk_assessment?.enterprise_id);
              const entName = assessment.enterprise_name || (assessment.risk_assessment?.enterprise_name) || '未知企业';
              const nodeType = assessment.node_type || (assessment.risk_assessment?.node_type) || (assessment.risk_assessment?.enterprise_type) || '企业';
              const matchScore = assessment.match_score || assessment.score || 0;
              const signals = assessment.matched_signals || [];
              const riskLevel = assessment.risk_assessment?.risk_level || 'unknown';

              return (
                <div
                  key={entId || idx}
                  className="flex items-center justify-between p-3 bg-gradient-to-r from-gray-50 to-white rounded-lg border border-gray-100"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center text-white font-medium text-sm">
                      {idx + 1}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-900">{entName}</div>
                      <div className="text-xs text-gray-500">
                        {nodeType}
                        {signals.length > 0 && (
                          <span className="ml-2">· {signals.slice(0, 2).join(', ')}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {riskLevel !== 'unknown' && (
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        riskLevel === 'high' ? 'bg-rose-100 text-rose-700' :
                        riskLevel === 'medium' ? 'bg-amber-100 text-amber-700' :
                        'bg-emerald-100 text-emerald-700'
                      }`}>
                        {riskLevel === 'high' ? '高风险' : riskLevel === 'medium' ? '中风险' : '低风险'}
                      </span>
                    )}
                    <div className="text-right">
                      <div className={`text-lg font-bold ${
                        matchScore >= 70 ? 'text-rose-600' :
                        matchScore >= 40 ? 'text-amber-600' : 'text-emerald-600'
                      }`}>
                        {typeof matchScore === 'number' ? matchScore.toFixed(0) : matchScore}
                      </div>
                      <div className="text-xs text-gray-500">匹配分</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Final Report */}
      {reportForView && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-emerald-600">
            <CheckCircleIcon className="h-5 w-5" />
            <span className="font-medium">研判完成，以下是完整报告</span>
          </div>
          <ReportView report={reportForView} />
        </div>
      )}

      {/* Combined Conclusion */}
      {(result?.combined_conclusion || result?.conclusion || result?.evidence_chain) && !reportForView && (
        <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl border border-blue-200 p-6">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">联合研判结论</h4>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">
            {result.combined_conclusion || result.conclusion || JSON.stringify(result.evidence_chain, null, 2)}
          </p>
          {result.action_suggestions && result.action_suggestions.length > 0 && (
            <div className="mt-4">
              <h5 className="text-xs font-medium text-gray-500 mb-2">行动建议</h5>
              <ul className="space-y-1">
                {result.action_suggestions.map((suggestion, idx) => (
                  <li key={idx} className="text-sm text-gray-700 flex items-start">
                    <ArrowRightIcon className="h-4 w-4 text-blue-500 mr-2 mt-0.5 flex-shrink-0" />
                    {typeof suggestion === 'string' ? suggestion : suggestion.action || JSON.stringify(suggestion)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
