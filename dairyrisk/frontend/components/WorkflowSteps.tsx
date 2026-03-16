'use client';

import { useState } from 'react';
import {
  MagnifyingGlassIcon,
  CircleStackIcon,
  ScaleIcon,
  CalculatorIcon,
  ShareIcon,
  BookOpenIcon,
  SparklesIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ClockIcon,
  CommandLineIcon,
  BeakerIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { AgentStep } from '@/hooks/useStreamingAgent';

interface StepConfig {
  id: string;
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  gradient: string;
}

const stepConfigs: StepConfig[] = [
  {
    id: 'workflow_start',
    label: '开始研判',
    description: '初始化风险研判流程',
    icon: ClockIcon,
    color: 'gray',
    gradient: 'from-gray-400 to-gray-500',
  },
  {
    id: 'identify',
    label: '识别对象',
    description: '解析用户查询，识别企业或批次',
    icon: MagnifyingGlassIcon,
    color: 'blue',
    gradient: 'from-blue-400 to-cyan-400',
  },
  {
    id: 'retrieve',
    label: '数据检索',
    description: '检索企业档案、批次记录、检验数据',
    icon: CircleStackIcon,
    color: 'indigo',
    gradient: 'from-indigo-400 to-purple-400',
  },
  {
    id: 'gb_match',
    label: '规则匹配',
    description: '匹配GB标准规则库，识别违规项',
    icon: ScaleIcon,
    color: 'amber',
    gradient: 'from-amber-400 to-orange-400',
  },
  {
    id: 'score',
    label: '风险计算',
    description: '计算风险评分，判定风险等级',
    icon: CalculatorIcon,
    color: 'rose',
    gradient: 'from-rose-400 to-pink-400',
  },
  {
    id: 'graph_analysis',
    label: '异构图分析',
    description: '分析供应链网络，获取上下游关系',
    icon: ShareIcon,
    color: 'violet',
    gradient: 'from-violet-400 to-purple-400',
  },
  {
    id: 'case_match',
    label: '案例匹配',
    description: '匹配历史案例，获取相似案例',
    icon: BookOpenIcon,
    color: 'teal',
    gradient: 'from-teal-400 to-emerald-400',
  },
  {
    id: 'llm_analysis',
    label: 'LLM增强',
    description: 'Minimax M2.5生成深度分析报告',
    icon: SparklesIcon,
    color: 'purple',
    gradient: 'from-purple-400 to-pink-400',
  },
  {
    id: 'generate_report',
    label: '报告生成',
    description: '组装最终报告，格式化输出',
    icon: DocumentTextIcon,
    color: 'cyan',
    gradient: 'from-cyan-400 to-blue-400',
  },
  {
    id: 'propagation',
    label: '传播分析',
    description: '分析风险传播路径和影响范围',
    icon: ArrowPathIcon,
    color: 'orange',
    gradient: 'from-orange-400 to-red-400',
  },
  {
    id: 'workflow_complete',
    label: '研判完成',
    description: '风险研判流程全部完成',
    icon: ShieldCheckIcon,
    color: 'emerald',
    gradient: 'from-emerald-400 to-green-400',
  },
];

interface WorkflowStepsProps {
  steps: AgentStep[];
  currentStep: string | null;
  isComplete: boolean;
}

// 风险评分仪表盘组件
function RiskGauge({ score, maxScore = 100 }: { score: number; maxScore?: number }) {
  const percentage = (score / maxScore) * 100;
  const color = percentage >= 70 ? 'text-rose-500' : percentage >= 40 ? 'text-amber-500' : 'text-emerald-500';
  const bgColor = percentage >= 70 ? 'bg-rose-500' : percentage >= 40 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className="flex items-center space-x-3">
      <div className="relative w-16 h-16">
        <svg className="w-16 h-16 transform -rotate-90">
          <circle
            cx="32"
            cy="32"
            r="28"
            stroke="currentColor"
            strokeWidth="4"
            fill="none"
            className="text-gray-200"
          />
          <circle
            cx="32"
            cy="32"
            r="28"
            stroke="currentColor"
            strokeWidth="4"
            fill="none"
            strokeDasharray={`${2 * Math.PI * 28}`}
            strokeDashoffset={`${2 * Math.PI * 28 * (1 - percentage / 100)}`}
            className={`${color} transition-all duration-1000`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`text-lg font-bold ${color}`}>{score}</span>
        </div>
      </div>
      <div className="flex-1">
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full ${bgColor} rounded-full transition-all duration-1000`}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">风险评分: {score}/{maxScore}</p>
      </div>
    </div>
  );
}

// Terminal 风格面板（用于LLM步骤）
function TerminalPanel({ title, content, type = 'prompt' }: { title: string; content: string; type?: 'prompt' | 'response' }) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div className={`rounded-lg overflow-hidden border ${type === 'prompt' ? 'border-purple-300' : 'border-green-300'}`}>
      <div className={`flex items-center justify-between px-3 py-2 ${type === 'prompt' ? 'bg-purple-900' : 'bg-green-900'}`}>
        <div className="flex items-center space-x-2">
          <CommandLineIcon className="h-4 w-4 text-gray-400" />
          <span className="text-xs font-mono text-gray-300">{title}</span>
        </div>
        <button
          onClick={handleCopy}
          className="text-xs text-gray-400 hover:text-white transition-colors"
        >
          {isCopied ? '已复制!' : '复制'}
        </button>
      </div>
      <div className={`p-3 max-h-48 overflow-y-auto ${type === 'prompt' ? 'bg-slate-900' : 'bg-slate-800'}`}>
        <pre className={`text-xs font-mono whitespace-pre-wrap ${type === 'prompt' ? 'text-purple-300' : 'text-green-300'}`}>
          {content}
        </pre>
      </div>
    </div>
  );
}

// 指标卡片
function MetricCard({ label, value, unit = '', color = 'blue' }: { label: string; value: string | number; unit?: string; color?: string }) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    green: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    rose: 'bg-rose-50 border-rose-200 text-rose-700',
  };

  return (
    <div className={`px-3 py-2 rounded-lg border ${colorClasses[color] || colorClasses.blue}`}>
      <div className="text-xs opacity-70">{label}</div>
      <div className="text-lg font-bold">
        {value}<span className="text-xs font-normal ml-1">{unit}</span>
      </div>
    </div>
  );
}

// 风险因子条形图
function RiskFactorBars({ factors }: { factors: any[] }) {
  return (
    <div className="space-y-2">
      {factors.map((factor, idx) => (
        <div key={idx}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-600">{factor.factor}</span>
            <span className={`font-medium ${
              factor.score >= 70 ? 'text-rose-600' :
              factor.score >= 40 ? 'text-amber-600' : 'text-emerald-600'
            }`}>
              {factor.score}分
            </span>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                factor.score >= 70 ? 'bg-rose-500' :
                factor.score >= 40 ? 'bg-amber-500' : 'bg-emerald-500'
              }`}
              style={{ width: `${factor.score}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// 案例相似度热力图
function CaseSimilarityHeatmap({ cases }: { cases: any[] }) {
  return (
    <div className="space-y-2">
      {cases.slice(0, 3).map((c, idx) => (
        <div key={idx} className="flex items-center space-x-3">
          <div className="flex-1 text-xs text-gray-600 truncate">{c.case_name}</div>
          <div className="w-24 h-4 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-400 to-purple-400 rounded-full"
              style={{ width: c.similarity }}
            />
          </div>
          <div className="text-xs font-medium text-gray-700 w-10 text-right">{c.similarity}</div>
        </div>
      ))}
    </div>
  );
}

export default function WorkflowSteps({ steps, currentStep, isComplete }: WorkflowStepsProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  const toggleExpanded = (stepId: string) => {
    const newSet = new Set(expandedSteps);
    if (newSet.has(stepId)) {
      newSet.delete(stepId);
    } else {
      newSet.add(stepId);
    }
    setExpandedSteps(newSet);
  };

  // 获取步骤的最新状态
  const getStepStatus = (stepId: string) => {
    const stepUpdates = steps.filter(s => s.step === stepId);
    if (stepUpdates.length === 0) return 'pending';

    const latest = stepUpdates[stepUpdates.length - 1];

    if (latest.status === 'error') return 'error';
    if (latest.status === 'skipped') return 'skipped';
    if (latest.status === 'complete') return 'completed';
    if (latest.status === 'started' || latest.status === 'progress' || latest.status === 'data') {
      return currentStep === stepId ? 'active' : 'completed';
    }
    return 'pending';
  };

  // 获取步骤的最新数据
  const getStepData = (stepId: string): AgentStep | null => {
    const stepUpdates = steps.filter(s => s.step === stepId);
    return stepUpdates.length > 0 ? stepUpdates[stepUpdates.length - 1] : null;
  };

  const getStepStyles = (status: string, config: StepConfig) => {
    const baseStyles = {
      pending: {
        container: 'bg-gray-50/50 border-gray-200',
        icon: 'bg-gray-200 text-gray-400',
        glow: '',
        line: 'bg-gray-200',
      },
      active: {
        container: `bg-${config.color}-50 border-${config.color}-300 shadow-lg`,
        icon: `bg-gradient-to-br ${config.gradient} text-white`,
        glow: `shadow-[0_0_20px_rgba(var(--tw-colors-${config.color}-400),0.5)] animate-pulse`,
        line: `bg-gradient-to-b ${config.gradient}`,
      },
      completed: {
        container: 'bg-white border-emerald-200 hover:border-emerald-300',
        icon: 'bg-emerald-500 text-white',
        glow: '',
        line: 'bg-emerald-400',
      },
      error: {
        container: 'bg-rose-50 border-rose-300',
        icon: 'bg-rose-500 text-white',
        glow: 'shadow-[0_0_15px_rgba(244,63,94,0.4)]',
        line: 'bg-rose-400',
      },
      skipped: {
        container: 'bg-gray-50 border-gray-200 opacity-60',
        icon: 'bg-gray-300 text-gray-500',
        glow: '',
        line: 'bg-gray-200',
      },
    };

    return baseStyles[status as keyof typeof baseStyles] || baseStyles.pending;
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { text: string; className: string }> = {
      completed: { text: '已完成', className: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
      active: { text: '进行中', className: 'bg-blue-100 text-blue-700 border-blue-200 animate-pulse' },
      error: { text: '出错', className: 'bg-rose-100 text-rose-700 border-rose-200' },
      skipped: { text: '已跳过', className: 'bg-gray-100 text-gray-600 border-gray-200' },
      pending: { text: '待执行', className: 'bg-gray-100 text-gray-400 border-gray-200' },
    };
    return badges[status] || badges.pending;
  };

  // 渲染步骤专属详情
  const renderStepSpecificDetails = (stepId: string, data: AgentStep | null) => {
    if (!data) return null;

    switch (stepId) {
      case 'identify':
        return (
          <div className="space-y-3">
            {data.input?.query && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">查询:</span>
                <code className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-mono">
                  {data.input.query}
                </code>
              </div>
            )}
            {data.output?.target_name && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">识别结果:</span>
                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs font-medium">
                  {data.output.target_type === 'batch' ? '📦' : '🏢'} {data.output.target_name}
                </span>
              </div>
            )}
          </div>
        );

      case 'retrieve':
        return (
          <div className="space-y-3">
            {data.items && data.items.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {data.items.map((item, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs border border-indigo-200"
                  >
                    {item.name || item.id}
                  </span>
                ))}
              </div>
            )}
            {data.output && (
              <div className="grid grid-cols-3 gap-2">
                {data.output.enterprise && (
                  <MetricCard label="企业" value={data.output.enterprise.enterprise_name || '1'} color="blue" />
                )}
                {data.output.batch && (
                  <MetricCard label="批次" value={data.output.batch.product_name || '1'} color="purple" />
                )}
                {data.output.inspections && (
                  <MetricCard label="检验记录" value={data.output.inspections.length} unit="条" color="green" />
                )}
              </div>
            )}
          </div>
        );

      case 'score':
        return (
          <div className="space-y-3">
            {data.output?.total_score !== undefined && (
              <RiskGauge score={data.output.total_score} />
            )}
            {data.factors && data.factors.length > 0 && (
              <div className="mt-4">
                <div className="text-xs text-gray-500 mb-2">风险因子分解:</div>
                <RiskFactorBars factors={data.factors} />
              </div>
            )}
          </div>
        );

      case 'gb_match':
        return (
          <div className="space-y-3">
            {data.violations_found !== undefined && (
              <div className="flex items-center space-x-4">
                <MetricCard
                  label="匹配规则"
                  value={data.violations_found}
                  unit="条"
                  color={data.violations_found > 0 ? 'rose' : 'green'}
                />
                {data.output?.rules_matched && (
                  <MetricCard label="触发规则" value={data.output.rules_matched} unit="条" color="amber" />
                )}
              </div>
            )}
            {data.violations_preview && data.violations_preview.length > 0 && (
              <div className="space-y-2 mt-3">
                <div className="text-xs text-gray-500">违规项详情:</div>
                {data.violations_preview.map((v, idx) => (
                  <div key={idx} className="flex items-start space-x-2 p-2 bg-rose-50 rounded-lg border border-rose-200">
                    <span className="text-rose-500 mt-0.5">⚠️</span>
                    <div>
                      <div className="text-xs font-medium text-rose-700">{v.gb_no}</div>
                      <div className="text-xs text-rose-600">{v.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      case 'graph_analysis':
        return (
          <div className="space-y-3">
            {data.metrics && (
              <div className="grid grid-cols-3 gap-2">
                <MetricCard label="节点数" value={data.metrics.total_nodes} color="violet" />
                <MetricCard label="边数" value={data.metrics.total_edges} color="purple" />
                <MetricCard
                  label="网络密度"
                  value={(data.metrics.network_density * 100).toFixed(1)}
                  unit="%"
                  color="blue"
                />
              </div>
            )}
            {data.output?.upstream && data.output?.downstream && (
              <div className="flex items-center justify-center space-x-4 mt-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-violet-600">{data.output.upstream.length}</div>
                  <div className="text-xs text-gray-500">上游节点</div>
                </div>
                <div className="flex items-center">
                  <div className="w-8 h-0.5 bg-violet-300"></div>
                  <div className="w-3 h-3 rounded-full bg-violet-500"></div>
                  <div className="w-8 h-0.5 bg-violet-300"></div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-violet-600">{data.output.downstream.length}</div>
                  <div className="text-xs text-gray-500">下游节点</div>
                </div>
              </div>
            )}
          </div>
        );

      case 'case_match':
        return (
          <div className="space-y-3">
            {data.cases_found !== undefined && (
              <MetricCard label="匹配案例" value={data.cases_found} unit="个" color="teal" />
            )}
            {data.matched_cases && data.matched_cases.length > 0 && (
              <div className="mt-3">
                <div className="text-xs text-gray-500 mb-2">相似度排行:</div>
                <CaseSimilarityHeatmap cases={data.matched_cases} />
              </div>
            )}
          </div>
        );

      case 'llm_analysis':
        return (
          <div className="space-y-3">
            {/* LLM Metrics Bar */}
            <div className="flex items-center space-x-3">
              {data.tokens_used && (
                <MetricCard label="Token用量" value={data.tokens_used} unit="tokens" color="purple" />
              )}
              {data.output?.latency_ms && (
                <MetricCard
                  label="响应时间"
                  value={(data.output.latency_ms / 1000).toFixed(1)}
                  unit="s"
                  color="blue"
                />
              )}
              <div className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                🤖 Minimax M2.5
              </div>
            </div>

            {/* LLM Prompt */}
            {data.llm_prompt && (
              <div className="mt-3">
                <TerminalPanel title="prompt.txt" content={data.llm_prompt} type="prompt" />
              </div>
            )}

            {/* LLM Response */}
            {data.llm_response_preview && (
              <div className="mt-3">
                <TerminalPanel title="response.md" content={data.llm_response_preview} type="response" />
              </div>
            )}
          </div>
        );

      case 'propagation':
        return (
          <div className="space-y-3">
            {data.output && (
              <div className="grid grid-cols-3 gap-2">
                <MetricCard label="影响节点" value={data.output.affected_nodes || 0} unit="个" color="orange" />
                <MetricCard label="传播半径" value={data.output.propagation_radius || 0} unit="跳" color="amber" />
                <MetricCard label="最大深度" value={data.output.max_hops || 0} unit="跳" color="rose" />
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  // 渲染步骤详情
  const renderStepDetails = (stepId: string, data: AgentStep | null, config: StepConfig) => {
    if (!data) return null;

    return (
      <div className="mt-4 space-y-4 border-t border-gray-200 pt-4">
        {/* 步骤专属可视化 */}
        {renderStepSpecificDetails(stepId, data)}

        {/* 通用数据展示 */}
        {data.input && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-xs font-medium text-gray-700 mb-2 flex items-center">
              <span className="w-2 h-2 bg-blue-400 rounded-full mr-2"></span>
              输入参数
            </div>
            <pre className="text-xs text-gray-600 overflow-x-auto bg-white p-2 rounded border border-gray-200">
              {JSON.stringify(data.input, null, 2)}
            </pre>
          </div>
        )}

        {data.output && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-xs font-medium text-gray-700 mb-2 flex items-center">
              <span className="w-2 h-2 bg-emerald-400 rounded-full mr-2"></span>
              输出结果
            </div>
            <pre className="text-xs text-gray-600 overflow-x-auto bg-white p-2 rounded border border-gray-200">
              {JSON.stringify(data.output, null, 2)}
            </pre>
          </div>
        )}

        {data.error && (
          <div className="bg-rose-50 rounded-lg p-3 border border-rose-200">
            <div className="text-xs font-medium text-rose-700 mb-2">❌ 错误信息</div>
            <p className="text-xs text-rose-600">{data.error}</p>
          </div>
        )}
      </div>
    );
  };

  const visibleSteps = stepConfigs.filter(config => {
    const status = getStepStatus(config.id);
    return status !== 'pending' || isComplete;
  });

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center">
              <BeakerIcon className="h-5 w-5 mr-2 text-cyan-400" />
              研判流程
            </h3>
            <p className="text-sm text-gray-400 mt-1">
              Agent 智能体实时处理中
            </p>
          </div>
          {isComplete && (
            <div className="flex items-center text-emerald-400 bg-emerald-400/10 px-4 py-2 rounded-full border border-emerald-400/30">
              <CheckCircleIcon className="h-5 w-5 mr-2" />
              <span className="text-sm font-medium">研判完成</span>
            </div>
          )}
        </div>
      </div>

      {/* Steps */}
      <div className="p-6 max-h-[700px] overflow-y-auto">
        <div className="relative">
          {/* 垂直连接线 */}
          <div className="absolute left-5 top-8 bottom-8 w-0.5 bg-gray-200"></div>

          <div className="space-y-4">
            {visibleSteps.map((config, index) => {
              const status = getStepStatus(config.id);
              const styles = getStepStyles(status, config);
              const data = getStepData(config.id);
              const Icon = config.icon;
              const isExpanded = expandedSteps.has(config.id);
              const isLast = index === visibleSteps.length - 1;
              const badge = getStatusBadge(status);

              return (
                <div key={config.id} className="relative">
                  {/* 步骤卡片 */}
                  <div
                    className={`relative rounded-xl border-2 transition-all duration-300 ${styles.container} ${
                      status === 'active' ? styles.glow : ''
                    } ${data ? 'cursor-pointer' : ''}`}
                    onClick={() => data && toggleExpanded(config.id)}
                  >
                    <div className="flex items-start p-4">
                      {/* 图标 */}
                      <div className="relative z-10">
                        <div
                          className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 ${styles.icon} ${
                            status === 'active' ? 'animate-pulse shadow-lg' : ''
                          }`}
                        >
                          {status === 'completed' ? (
                            <CheckCircleIcon className="h-5 w-5" />
                          ) : (
                            <Icon className="h-5 w-5" />
                          )}
                        </div>
                        {/* 连接线节点 */}
                        {!isLast && (
                          <div className={`absolute top-10 left-1/2 transform -translate-x-1/2 w-0.5 h-6 ${styles.line}`}></div>
                        )}
                      </div>

                      {/* 内容 */}
                      <div className="ml-4 flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className={`text-sm font-semibold ${
                              status === 'active' ? 'text-slate-800' :
                              status === 'completed' ? 'text-slate-700' : 'text-slate-500'
                            }`}>
                              {config.label}
                            </h4>
                            <p className={`text-xs mt-0.5 ${
                              status === 'active' ? 'text-slate-600' : 'text-slate-400'
                            }`}>
                              {config.description}
                            </p>
                          </div>
                          <div className="flex items-center space-x-2">
                            <span className={`text-xs px-2.5 py-1 rounded-full border ${badge.className}`}>
                              {badge.text}
                            </span>
                            {data && (
                              <button className="text-gray-400 hover:text-gray-600 transition-colors">
                                {isExpanded ? (
                                  <ChevronUpIcon className="h-4 w-4" />
                                ) : (
                                  <ChevronDownIcon className="h-4 w-4" />
                                )}
                              </button>
                            )}
                          </div>
                        </div>

                        {/* 当前消息 */}
                        {data?.message && (
                          <p className={`text-sm mt-2 ${
                            status === 'active' ? 'text-blue-600' : 'text-gray-500'
                          }`}>
                            {status === 'active' && <span className="inline-block w-1.5 h-1.5 bg-blue-500 rounded-full mr-2 animate-pulse"></span>}
                            {data.message}
                          </p>
                        )}

                        {/* 展开详情 */}
                        {isExpanded && renderStepDetails(config.id, data, config)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="bg-gray-50 px-6 py-3 border-t border-gray-200">
        <div className="flex items-center justify-center space-x-6 text-xs">
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-emerald-500 mr-2"></div>
            <span className="text-gray-600">已完成</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-blue-500 mr-2 animate-pulse"></div>
            <span className="text-gray-600">进行中</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-rose-500 mr-2"></div>
            <span className="text-gray-600">出错</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-gray-300 mr-2"></div>
            <span className="text-gray-600">待执行</span>
          </div>
        </div>
      </div>
    </div>
  );
}
