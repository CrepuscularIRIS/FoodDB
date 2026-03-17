// API调用库
import axios, { AxiosResponse } from 'axios';
import {
  RiskAssessmentReport,
  ApiResponse,
  Enterprise,
  Batch,
  DemoCase,
  LinkedWorkflowRequest,
  LinkedWorkflowResponse,
  WorkflowStepEvent,
} from '@/types';

// 创建axios实例
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 90000, // 90秒超时 - LLM调用需要更长时间
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 获取更友好的错误信息
const getErrorMessage = (error: any): string => {
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return '请求超时，请检查后端服务是否正常运行';
  }
  if (error.code === 'ECONNREFUSED') {
    return '无法连接到后端服务，请确认服务已启动 (python backend/api.py)';
  }
  if (error.response?.status === 404) {
    return '未找到请求的资源，请检查查询对象是否存在';
  }
  if (error.response?.status === 500) {
    return '服务器内部错误，请稍后重试';
  }
  if (error.response?.status === 503) {
    return '服务暂不可用，Agent正在初始化中，请稍后重试';
  }
  return error.message || '请求失败，请检查网络连接';
};

// 响应拦截器
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error) => {
    console.error('[API Error]', error);
    // 增强错误信息
    error.message = getErrorMessage(error);
    return Promise.reject(error);
  }
);

// 风险研判API
export const assessmentApi = {
  // 执行风险研判
  assess: async (query: string, withPropagation: boolean = false): Promise<ApiResponse<RiskAssessmentReport>> => {
    try {
      const response = await api.post('/assess', {
        query,
        with_propagation: withPropagation,
      });
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 批量研判
  batchAssess: async (queries: string[]): Promise<ApiResponse<RiskAssessmentReport[]>> => {
    try {
      const response = await api.post('/batch_assess', {
        queries,
      });
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取演示案例
  getDemoCases: async (): Promise<ApiResponse<DemoCase[]>> => {
    try {
      const response = await api.get('/demo_cases');
      const payload = response.data;
      // Backend returns { success: true, data: [...] }
      return {
        success: !!payload?.success,
        data: payload?.data as DemoCase[],
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },
};

// 数据查询API
export const dataApi = {
  // 获取企业列表
  getEnterprises: async (): Promise<ApiResponse<Enterprise[]>> => {
    try {
      const response = await api.get('/enterprises');
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取批次列表
  getBatches: async (): Promise<ApiResponse<Batch[]>> => {
    try {
      const response = await api.get('/batches');
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取企业详情
  getEnterprise: async (id: string): Promise<ApiResponse<Enterprise>> => {
    try {
      const response = await api.get(`/enterprises/${encodeURIComponent(id)}`);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取批次详情
  getBatch: async (id: string): Promise<ApiResponse<Batch>> => {
    try {
      const response = await api.get(`/batches/${encodeURIComponent(id)}`);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },
};

// 抽检优化API
export const samplingApi = {
  // 获取抽检建议
  getSamplingSuggestions: async (enterpriseId?: string): Promise<ApiResponse<any>> => {
    try {
      const response = await api.post('/sampling/suggestions', {
        enterprise_id: enterpriseId,
      });
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取Top-N抽检清单
  getTopNList: async (n: number = 10): Promise<ApiResponse<any>> => {
    try {
      const response = await api.get(`/sampling/top_n?n=${n}`);
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },
};

// 传播分析API
export const propagationApi = {
  // 执行传播分析
  analyze: async (nodeId: string, maxHops: number = 3): Promise<ApiResponse<any>> => {
    try {
      const response = await api.post('/propagation/analyze', {
        node_id: nodeId,
        max_hops: maxHops,
      });
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },
};

// 数据源信息API
export const dataSourceApi = {
  // 获取当前数据源信息
  getDataSource: async (): Promise<ApiResponse<any>> => {
    try {
      const response = await api.get('/data_source');
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },
};

// Mode A/B 联动工作流API
export const linkedWorkflowApi = {
  // 执行联动工作流（非流式）
  execute: async (request: LinkedWorkflowRequest): Promise<ApiResponse<LinkedWorkflowResponse>> => {
    try {
      const response = await api.post('/linked_workflow', request);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 执行联动工作流（流式SSE）
  executeStream: (
    request: LinkedWorkflowRequest,
    onStep: (event: WorkflowStepEvent) => void,
    onComplete: (result: LinkedWorkflowResponse) => void,
    onError: (error: string) => void
  ) => {
    const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const url = new URL('/linked_workflow_stream', baseURL);

    const eventSource = new EventSource(url.toString(), {
      withCredentials: false,
    });

    let finalResult: LinkedWorkflowResponse | null = null;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // 处理步骤事件
        if (data.step && data.status) {
          onStep(data as WorkflowStepEvent);
        }

        // 处理完整结果
        if (data.workflow_id && data.result) {
          finalResult = data as LinkedWorkflowResponse;
        }

        // 处理完成或错误
        if (data.status === 'completed' || data.status === 'failed') {
          eventSource.close();
          if (finalResult) {
            onComplete(finalResult);
          } else if (data.status === 'failed') {
            onError(data.error || '工作流执行失败');
          }
        }
      } catch (error) {
        console.error('[SSE] Parse error:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[SSE] Error:', error);
      eventSource.close();
      onError('SSE连接错误');
    };

    // 发送POST请求启动工作流（通过fetch）
    fetch(`${baseURL}/linked_workflow_stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }).catch((error) => {
      eventSource.close();
      onError(error.message || '启动工作流失败');
    });

    // 返回取消函数
    return () => {
      eventSource.close();
    };
  },
};

// 图数据API
export const graphApi = {
  // 获取完整图数据（节点和边）
  getGraphData: async (): Promise<ApiResponse<{ nodes: any[]; edges: any[] }>> => {
    try {
      const response = await api.get('/api/graph/data');
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取节点列表
  getNodes: async (filters?: { type?: string; risk_level?: string; limit?: number }): Promise<ApiResponse<{ total: number; nodes: any[] }>> => {
    try {
      const params = new URLSearchParams();
      if (filters?.type) params.append('type', filters.type);
      if (filters?.risk_level) params.append('risk_level', filters.risk_level);
      if (filters?.limit) params.append('limit', filters.limit.toString());
      
      const response = await api.get(`/api/graph/nodes?${params.toString()}`);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取边列表
  getEdges: async (filters?: { source?: string; target?: string; edge_type?: string; limit?: number }): Promise<ApiResponse<{ total: number; edges: any[] }>> => {
    try {
      const params = new URLSearchParams();
      if (filters?.source) params.append('source', filters.source);
      if (filters?.target) params.append('target', filters.target);
      if (filters?.edge_type) params.append('edge_type', filters.edge_type);
      if (filters?.limit) params.append('limit', filters.limit.toString());
      
      const response = await api.get(`/api/graph/edges?${params.toString()}`);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取统计数据
  getStats: async (): Promise<ApiResponse<any>> => {
    try {
      const response = await api.get('/api/graph/stats');
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取节点详情
  getNodeDetail: async (nodeId: string): Promise<ApiResponse<any>> => {
    try {
      const response = await api.get(`/api/graph/node/${encodeURIComponent(nodeId)}`);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 获取邻居节点
  getNeighbors: async (nodeId: string, direction: 'upstream' | 'downstream' | 'both' = 'both', maxDepth: number = 1): Promise<ApiResponse<any>> => {
    try {
      const response = await api.get(`/api/graph/neighbors/${encodeURIComponent(nodeId)}?direction=${direction}&max_depth=${maxDepth}`);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // 刷新图数据缓存
  refresh: async (): Promise<ApiResponse<any>> => {
    try {
      const response = await api.post('/api/graph/refresh');
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '请求失败',
      };
    }
  },

  // WebSocket连接（用于实时更新）
  connectWebSocket: (onMessage: (data: any) => void, onError?: (error: any) => void): WebSocket => {
    const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsUrl = baseURL.replace('http://', 'ws://').replace('https://', 'wss://') + '/api/graph/ws';
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('[Graph WebSocket] Connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('[Graph WebSocket] Parse error:', error);
      }
    };
    
    ws.onerror = (error) => {
      console.error('[Graph WebSocket] Error:', error);
      if (onError) onError(error);
    };
    
    ws.onclose = () => {
      console.log('[Graph WebSocket] Disconnected');
    };
    
    return ws;
  },
};

export default api;
