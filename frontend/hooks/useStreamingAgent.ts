'use client';

import { useState, useCallback, useRef } from 'react';
import { RiskAssessmentReport } from '@/types';

export interface AgentStep {
  step: string;
  status: 'started' | 'progress' | 'complete' | 'error' | 'skipped' | 'data' | 'stream_chunk';
  timestamp: number;
  message: string;
  input?: any;
  output?: any;
  progress?: any;
  data_type?: string;
  items?: any[];
  factors?: any[];
  intermediate_scores?: any;
  violations_found?: number;
  violations_preview?: any[];
  metrics?: any;
  cases_found?: number;
  matched_cases?: any[];
  llm_prompt?: string;
  llm_response_preview?: string;
  tokens_used?: number;
  has_analysis?: boolean;
  reason?: string;
  error?: string;
  report_summary?: any;
  // Stream chunk fields for LLM streaming
  chunk_content?: string;
  accumulated_length?: number;
  stream_mode?: boolean;
  analysis_length?: number;
}

export interface StreamingState {
  steps: AgentStep[];
  currentStep: string | null;
  isComplete: boolean;
  isError: boolean;
  error: string | null;
  report: RiskAssessmentReport | null;
  llmStreamContent: string; // Accumulated LLM stream content
}

interface UseStreamingAgentReturn {
  state: StreamingState;
  execute: (query: string, withPropagation?: boolean) => Promise<void>;
  reset: () => void;
  llmStreamContent: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18080';

export function useStreamingAgent(): UseStreamingAgentReturn {
  const [state, setState] = useState<StreamingState>({
    steps: [],
    currentStep: null,
    isComplete: false,
    isError: false,
    error: null,
    report: null,
    llmStreamContent: '',
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setState({
      steps: [],
      currentStep: null,
      isComplete: false,
      isError: false,
      error: null,
      report: null,
      llmStreamContent: '',
    });
  }, []);

  const execute = useCallback(async (query: string, withPropagation: boolean = false) => {
    reset();

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      // 使用非流式API获取完整步骤（简化实现）
      // 如果需要真正的SSE流式，可以使用 EventSource
      const response = await fetch(`${API_BASE_URL}/assess_with_steps`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          with_propagation: withPropagation,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();

      if (!result.success) {
        throw new Error(result.error || '研判失败');
      }

      // 模拟流式更新 - 逐个步骤显示
      const steps: AgentStep[] = result.data.steps || [];

      for (const step of steps) {
        // 根据步骤类型设置不同的延迟，让用户能看清每个步骤
        const stepDelays: Record<string, number> = {
          'identify': 800,      // 对象识别较快
          'retrieve': 1500,     // 数据检索需要更多时间
          'gb_match': 1200,     // 规则匹配
          'score': 1000,        // 风险计算
          'graph_analysis': 1500, // 图分析
          'case_match': 1000,   // 案例匹配
          'llm_analysis': 3000, // LLM分析最慢
          'generate_report': 800,
          'propagation': 2000,  // 传播分析
        };
        const delay = stepDelays[step.step] || 500;
        await new Promise(resolve => setTimeout(resolve, delay));

        setState(prev => ({
          ...prev,
          steps: [...prev.steps, step],
          currentStep: step.step,
        }));
      }

      // 最终报告
      setState(prev => ({
        ...prev,
        report: result.data.report,
        isComplete: true,
        currentStep: null,
      }));

    } catch (err: any) {
      if (err.name === 'AbortError') {
        return;
      }

      setState(prev => ({
        ...prev,
        isError: true,
        error: err.message || '执行失败',
        currentStep: null,
      }));
    }
  }, [reset]);

  return {
    state,
    execute,
    reset,
    llmStreamContent: state.llmStreamContent,
  };
}

// 真正的SSE流式版本（高级用法）
export function useStreamingAgentSSE(): UseStreamingAgentReturn & { llmStreamContent: string } {
  const [state, setState] = useState<StreamingState>({
    steps: [],
    currentStep: null,
    isComplete: false,
    isError: false,
    error: null,
    report: null,
    llmStreamContent: '',
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setState({
      steps: [],
      currentStep: null,
      isComplete: false,
      isError: false,
      error: null,
      report: null,
      llmStreamContent: '',
    });
  }, []);

  const execute = useCallback(async (query: string, withPropagation: boolean = false) => {
    reset();

    try {
      // 使用fetch获取流式响应
      const response = await fetch(`${API_BASE_URL}/assess_stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          with_propagation: withPropagation,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法获取响应流');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: AgentStep = JSON.parse(line.slice(6));

              setState(prev => {
                // Accumulate LLM stream content
                let newStreamContent = prev.llmStreamContent;
                if (data.step === 'llm_analysis' && data.status === 'stream_chunk' && data.chunk_content) {
                  newStreamContent = prev.llmStreamContent + data.chunk_content;
                }
                // Clear stream content when LLM analysis completes
                if (data.step === 'llm_analysis' && data.status === 'complete') {
                  newStreamContent = '';
                }

                return {
                  ...prev,
                  steps: [...prev.steps, data],
                  currentStep: data.step,
                  llmStreamContent: newStreamContent,
                };
              });

              if (data.step === 'stream_end') {
                setState(prev => ({
                  ...prev,
                  isComplete: true,
                  currentStep: null,
                }));
              }
            } catch (e) {
              console.error('解析SSE数据失败:', e);
            }
          }
        }
      }

    } catch (err: any) {
      setState(prev => ({
        ...prev,
        isError: true,
        error: err.message || '执行失败',
        currentStep: null,
      }));
    }
  }, [reset]);

  return {
    state,
    execute,
    reset,
    llmStreamContent: state.llmStreamContent,
  };
}
