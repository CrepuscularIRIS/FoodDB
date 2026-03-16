'use client';

import { useState } from 'react';
import { SparklesIcon, ClockIcon, DocumentTextIcon, ChevronDownIcon, ChevronUpIcon, CommandLineIcon } from '@heroicons/react/24/outline';
import { LLMUsage, LLMAnalysisReport } from '@/types';

interface LLMAnalysisProps {
  analysis: string;
  usage?: LLMUsage;
  latencyMs?: number;
}

export default function LLMAnalysis({ analysis, usage, latencyMs }: LLMAnalysisProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showRaw, setShowRaw] = useState(false);

  // Parse JSON analysis
  let parsedAnalysis: LLMAnalysisReport | null = null;
  let parseError = false;

  try {
    // Try to parse as JSON
    parsedAnalysis = JSON.parse(analysis);
  } catch (e) {
    parseError = true;
  }

  if (!analysis) {
    return (
      <div className="bg-gray-50 rounded-lg p-6 text-center">
        <SparklesIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">未启用LLM分析</p>
        <p className="text-sm text-gray-400 mt-1">
          设置 MINIMAX_API_KEY 环境变量以启用AI深度分析
        </p>
      </div>
    );
  }

  // If not valid JSON, show raw content
  if (parseError) {
    return (
      <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-lg border border-purple-200 overflow-hidden">
        <div className="px-4 py-3 bg-gradient-to-r from-purple-100 to-blue-100 border-b border-purple-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <SparklesIcon className="h-5 w-5 text-purple-600 mr-2" />
              <h3 className="font-semibold text-purple-900">AI深度分析报告</h3>
              <span className="ml-2 text-xs bg-purple-200 text-purple-700 px-2 py-0.5 rounded-full">
                Minimax M2.5
              </span>
            </div>
            {(usage || latencyMs) && (
              <div className="flex items-center space-x-3 text-xs text-purple-700">
                {latencyMs && (
                  <div className="flex items-center">
                    <ClockIcon className="h-3 w-3 mr-1" />
                    <span>{latencyMs.toFixed(0)}ms</span>
                  </div>
                )}
                {usage && (
                  <div className="flex items-center">
                    <DocumentTextIcon className="h-3 w-3 mr-1" />
                    <span>{usage.total_tokens.toLocaleString()} tokens</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="p-4">
          <div className="prose prose-sm max-w-none prose-purple">
            <div className="text-gray-700 whitespace-pre-wrap leading-relaxed">
              {analysis}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-lg border border-purple-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-purple-100 to-blue-100 border-b border-purple-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <SparklesIcon className="h-5 w-5 text-purple-600 mr-2" />
            <h3 className="font-semibold text-purple-900">AI深度分析报告</h3>
            <span className="ml-2 text-xs bg-purple-200 text-purple-700 px-2 py-0.5 rounded-full">
              Minimax M2.5
            </span>
          </div>
          <div className="flex items-center space-x-2">
            {(usage || latencyMs) && (
              <div className="flex items-center space-x-3 text-xs text-purple-700 mr-3">
                {latencyMs && (
                  <div className="flex items-center bg-white/50 px-2 py-1 rounded">
                    <ClockIcon className="h-3 w-3 mr-1" />
                    <span>{latencyMs.toFixed(0)}ms</span>
                  </div>
                )}
                {usage && (
                  <div className="flex items-center bg-white/50 px-2 py-1 rounded">
                    <DocumentTextIcon className="h-3 w-3 mr-1" />
                    <span>{usage.total_tokens.toLocaleString()} tokens</span>
                  </div>
                )}
              </div>
            )}
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="text-xs bg-purple-200 text-purple-700 px-2 py-1 rounded hover:bg-purple-300 transition-colors"
            >
              {showRaw ? '查看解析' : '查看原始JSON'}
            </button>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-purple-600 hover:text-purple-800"
            >
              {isExpanded ? (
                <ChevronUpIcon className="h-5 w-5" />
              ) : (
                <ChevronDownIcon className="h-5 w-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="p-4">
          {showRaw ? (
            // Raw JSON view
            <div className="bg-slate-900 rounded-lg p-4 overflow-x-auto">
              <pre className="text-xs text-green-300 font-mono whitespace-pre-wrap">
                {JSON.stringify(parsedAnalysis, null, 2)}
              </pre>
            </div>
          ) : (
            // Parsed structured view
            <div className="space-y-4">
              {/* Executive Summary */}
              {parsedAnalysis?.executive_summary && (
                <div className="bg-white rounded-lg p-4 border border-purple-200">
                  <h4 className="text-sm font-semibold text-purple-900 mb-2 flex items-center">
                    <span className="w-2 h-2 bg-purple-500 rounded-full mr-2"></span>
                    执行摘要
                  </h4>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {parsedAnalysis.executive_summary}
                  </p>
                </div>
              )}

              {/* Key Risk Factors */}
              {parsedAnalysis?.key_risk_factors && parsedAnalysis.key_risk_factors.length > 0 && (
                <div className="bg-white rounded-lg p-4 border border-purple-200">
                  <h4 className="text-sm font-semibold text-purple-900 mb-2">关键风险因子</h4>
                  <div className="flex flex-wrap gap-2">
                    {parsedAnalysis.key_risk_factors.map((factor, idx) => (
                      <span key={idx} className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs">
                        ⚠️ {factor}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Deep Analysis */}
              {parsedAnalysis?.deep_analysis && (
                <div className="bg-white rounded-lg p-4 border border-purple-200">
                  <h4 className="text-sm font-semibold text-purple-900 mb-2">深度风险分析</h4>
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {parsedAnalysis.deep_analysis}
                  </p>
                </div>
              )}

              {/* Root Cause */}
              {parsedAnalysis?.root_cause && (
                <div className="bg-white rounded-lg p-4 border border-purple-200">
                  <h4 className="text-sm font-semibold text-purple-900 mb-2">根因分析</h4>
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {parsedAnalysis.root_cause}
                  </p>
                </div>
              )}

              {/* Regulatory Basis */}
              {parsedAnalysis?.regulatory_basis_details && parsedAnalysis.regulatory_basis_details.length > 0 && (
                <div className="bg-white rounded-lg p-4 border border-purple-200">
                  <h4 className="text-sm font-semibold text-purple-900 mb-2">法规依据</h4>
                  <div className="space-y-2">
                    {parsedAnalysis.regulatory_basis_details.map((reg, idx) => (
                      <div key={idx} className="text-sm border-l-2 border-purple-300 pl-3">
                        <div className="font-medium text-purple-700">{reg.gb_no} {reg.clause}</div>
                        <div className="text-gray-600">{reg.requirement}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Items */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Immediate Actions */}
                {parsedAnalysis?.immediate_actions && parsedAnalysis.immediate_actions.length > 0 && (
                  <div className="bg-red-50 rounded-lg p-3 border border-red-200">
                    <h4 className="text-xs font-semibold text-red-800 mb-2">🚨 立即行动（24小时内）</h4>
                    <ul className="space-y-1">
                      {parsedAnalysis.immediate_actions.map((action, idx) => (
                        <li key={idx} className="text-xs text-red-700 flex items-start">
                          <span className="mr-1">•</span>
                          {action}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Short Term Actions */}
                {parsedAnalysis?.short_term_actions && parsedAnalysis.short_term_actions.length > 0 && (
                  <div className="bg-orange-50 rounded-lg p-3 border border-orange-200">
                    <h4 className="text-xs font-semibold text-orange-800 mb-2">⚠️ 短期整改（1周内）</h4>
                    <ul className="space-y-1">
                      {parsedAnalysis.short_term_actions.map((action, idx) => (
                        <li key={idx} className="text-xs text-orange-700 flex items-start">
                          <span className="mr-1">•</span>
                          {action}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Long Term Recommendations */}
                {parsedAnalysis?.long_term_recommendations && parsedAnalysis.long_term_recommendations.length > 0 && (
                  <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
                    <h4 className="text-xs font-semibold text-blue-800 mb-2">💡 长期优化</h4>
                    <ul className="space-y-1">
                      {parsedAnalysis.long_term_recommendations.map((action, idx) => (
                        <li key={idx} className="text-xs text-blue-700 flex items-start">
                          <span className="mr-1">•</span>
                          {action}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Confidence Assessment */}
              {parsedAnalysis?.confidence_assessment && (
                <div className="bg-purple-100 rounded-lg p-3 border border-purple-300">
                  <h4 className="text-xs font-semibold text-purple-800 mb-1">置信度评估</h4>
                  <p className="text-xs text-purple-700">{parsedAnalysis.confidence_assessment}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-purple-50/50 border-t border-purple-100 text-xs text-purple-500 flex justify-between">
        <span>* 本分析由Minimax M2.5生成，仅供参考</span>
        <span>{usage && `${usage.prompt_tokens} → ${usage.completion_tokens} tokens`}</span>
      </div>
    </div>
  );
}
