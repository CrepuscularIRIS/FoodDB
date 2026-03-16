'use client';

import { useState, useRef } from 'react';
import { MagnifyingGlassIcon, BeakerIcon, ExclamationTriangleIcon, SparklesIcon } from '@heroicons/react/24/outline';
import { RiskLevel } from '@/types';

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
    risk_level: RiskLevel;
    reasons: string[];
    credit_rating: string;
    historical_violations: number;
  }>;
  risk_level: RiskLevel;
  confidence: number;
  suggested_actions: string[];
  llm_extraction?: {
    raw_symptoms: string[];
    standardized_symptoms: string[];
    confidence: number;
    latency_ms: number;
  };
  processing_steps?: Array<{
    step: string;
    status: string;
    [key: string]: any;
  }>;
}

interface StreamUpdate {
  step: string;
  status: string;
  message: string;
  query?: string;
  raw_symptoms?: string[];
  standardized_symptoms?: string[];
  confidence?: number;
  latency_ms?: number;
  data?: SymptomAssessResult;
  [key: string]: any;
}

interface SymptomSearchPanelProps {
  onAssess: (result: SymptomAssessResult) => void;
  loading?: boolean;
}

const commonSymptoms = [
  { emoji: '💩', name: '腹泻', desc: '水样便或稀便' },
  { emoji: '🌡️', name: '发热', desc: '体温升高' },
  { emoji: '🤮', name: '呕吐', desc: '胃内容物排出' },
  { emoji: '💢', name: '腹痛', desc: '腹部疼痛' },
  { emoji: '😵', name: '恶心', desc: '想吐的感觉' },
  { emoji: '🌀', name: '头晕', desc: '头部昏沉' },
  { emoji: '😴', name: '乏力', desc: '全身无力' },
  { emoji: '🔴', name: '皮疹', desc: '皮肤过敏反应' },
];

export default function SymptomSearchPanel({ onAssess, loading: externalLoading }: SymptomSearchPanelProps) {
  const [query, setQuery] = useState('');
  const [productType, setProductType] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamUpdates, setStreamUpdates] = useState<StreamUpdate[]>([]);
  const [llmStatus, setLlmStatus] = useState<'idle' | 'processing' | 'completed' | 'skipped'>('idle');
  const abortControllerRef = useRef<AbortController | null>(null);

  const loading = externalLoading || isLoading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setStreamUpdates([]);
    setLlmStatus('idle');

    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      console.log(`[SymptomSearch] Starting stream to ${apiUrl}/symptom/assess_stream`);

      const response = await fetch(`${apiUrl}/symptom/assess_stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
          query: query.trim(),
          product_type: productType || undefined
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`Stream request failed: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) {
        throw new Error('No response body');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: StreamUpdate = JSON.parse(line.slice(6));
              console.log('[Stream]', data);
              setStreamUpdates(prev => [...prev, data]);

              // Update LLM status
              if (data.step === 'llm_extraction') {
                if (data.status === 'started') setLlmStatus('processing');
                else if (data.status === 'completed') setLlmStatus('completed');
                else if (data.status === 'skipped') setLlmStatus('skipped');
              }

              // Final result
              if (data.step === 'assessment' && data.status === 'completed' && data.data) {
                onAssess(data.data);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', line, e);
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Request aborted');
        return;
      }
      console.error('[SymptomSearch] 症状评估失败:', error);
      setError(error.message || '网络请求失败，请检查后端服务是否运行');
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const addSymptom = (symptom: string) => {
    setQuery(prev => {
      const symptoms = prev.split(/[,，\s]+/).filter(s => s.trim());
      if (!symptoms.includes(symptom)) {
        return prev ? `${prev}，${symptom}` : symptom;
      }
      return prev;
    });
  };

  // Get latest update for each step
  const getLatestUpdate = (step: string) => {
    return streamUpdates.filter(u => u.step === step).pop();
  };

  const llmUpdate = getLatestUpdate('llm_extraction');
  const assessmentUpdate = getLatestUpdate('assessment');

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-rose-500 to-orange-500 px-6 py-4">
        <div className="flex items-center space-x-2">
          <BeakerIcon className="h-6 w-6 text-white" />
          <h2 className="text-lg font-bold text-white">症状驱动风险评估</h2>
        </div>
        <p className="text-rose-100 text-sm mt-1">
          输入症状描述，Minimax M2.5 将实时分析并推断风险因子
        </p>
      </div>

      {/* Search Form */}
      <div className="p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Error Display */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mt-0.5 mr-2 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Query Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              症状描述 <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="例如：腹泻、发热、腹痛..."
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500 resize-none"
                rows={3}
                disabled={loading}
              />
              <div className="absolute bottom-3 right-3">
                <span className="text-xs text-gray-400">
                  {query.length} 字
                </span>
              </div>
            </div>
          </div>

          {/* Quick Select Symptoms */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">
              快速选择常见症状
            </label>
            <div className="flex flex-wrap gap-2">
              {commonSymptoms.map((symptom) => (
                <button
                  key={symptom.name}
                  type="button"
                  onClick={() => addSymptom(symptom.name)}
                  disabled={loading}
                  className="inline-flex items-center px-3 py-1.5 rounded-full text-sm bg-rose-50 text-rose-700 hover:bg-rose-100 transition-colors border border-rose-200 disabled:opacity-50"
                >
                  <span className="mr-1">{symptom.emoji}</span>
                  {symptom.name}
                </button>
              ))}
            </div>
          </div>

          {/* Product Type Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              产品类型（可选）
            </label>
            <select
              value={productType}
              onChange={(e) => setProductType(e.target.value)}
              disabled={loading}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500 disabled:opacity-50"
            >
              <option value="">全部产品类型</option>
              <option value="巴氏杀菌乳">巴氏杀菌乳</option>
              <option value="灭菌乳">灭菌乳</option>
              <option value="调制乳">调制乳</option>
              <option value="发酵乳">发酵乳</option>
              <option value="奶粉">奶粉</option>
              <option value="奶酪">奶酪</option>
            </select>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="w-full flex items-center justify-center px-6 py-3 bg-gradient-to-r from-rose-500 to-orange-500 text-white font-medium rounded-lg hover:from-rose-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2" />
                分析中...
              </>
            ) : (
              <>
                <MagnifyingGlassIcon className="h-5 w-5 mr-2" />
                开始风险评估
              </>
            )}
          </button>
        </form>

        {/* Stream Progress Display */}
        {loading && streamUpdates.length > 0 && (
          <div className="mt-4 space-y-3">
            {/* LLM Extraction Status */}
            {llmStatus !== 'idle' && (
              <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4">
                <div className="flex items-center space-x-2 mb-2">
                  <SparklesIcon className="h-5 w-5 text-purple-600" />
                  <span className="font-medium text-purple-900">Minimax M2.5 症状提取</span>
                  {llmStatus === 'processing' && (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-600" />
                  )}
                  {llmStatus === 'completed' && (
                    <span className="text-green-600 text-sm">✓</span>
                  )}
                </div>

                {llmUpdate?.raw_symptoms && (
                  <div className="text-sm text-purple-700 mb-1">
                    识别原始症状: <span className="font-medium">{llmUpdate.raw_symptoms.join(', ')}</span>
                  </div>
                )}

                {llmUpdate?.standardized_symptoms && (
                  <div className="text-sm text-purple-700">
                    标准化:
                    <span className="font-medium text-green-700">
                      {llmUpdate.standardized_symptoms.join(', ')}
                    </span>
                    {llmUpdate.confidence && (
                      <span className="text-xs text-purple-500 ml-2">
                        (置信度: {(llmUpdate.confidence * 100).toFixed(0)}%)
                      </span>
                    )}
                  </div>
                )}

                {llmUpdate?.latency_ms && (
                  <div className="text-xs text-purple-500 mt-1">
                    延迟: {llmUpdate.latency_ms.toFixed(0)}ms
                  </div>
                )}
              </div>
            )}

            {/* Assessment Status */}
            {assessmentUpdate && (
              <div className="bg-rose-50 border border-rose-200 rounded-lg p-3">
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-rose-600" />
                  <span className="text-sm text-rose-800">{assessmentUpdate.message}</span>
                </div>
              </div>
            )}

            {/* Processing Steps */}
            <div className="flex flex-wrap gap-2">
              {streamUpdates
                .filter(u => u.step !== 'complete')
                .map((update, idx) => (
                  <span
                    key={idx}
                    className={`px-2 py-1 rounded text-xs ${
                      update.status === 'completed'
                        ? 'bg-green-100 text-green-700'
                        : update.status === 'started'
                        ? 'bg-blue-100 text-blue-700'
                        : update.status === 'progress'
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {update.step}: {update.status}
                  </span>
                ))}
            </div>
          </div>
        )}

        {/* Workflow Description */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-3">评估流程</h3>
          <div className="flex items-center justify-between text-sm">
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-1">
                1
              </div>
              <span className="text-gray-600">症状识别</span>
            </div>
            <div className="flex-1 h-0.5 bg-rose-200 mx-2" />
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center mb-1">
                2
              </div>
              <span className="text-gray-600">风险推断</span>
            </div>
            <div className="flex-1 h-0.5 bg-orange-200 mx-2" />
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center mb-1">
                3
              </div>
              <span className="text-gray-600">环节定位</span>
            </div>
            <div className="flex-1 h-0.5 bg-amber-200 mx-2" />
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-yellow-100 text-yellow-600 flex items-center justify-center mb-1">
                4
              </div>
              <span className="text-gray-600">企业关联</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
