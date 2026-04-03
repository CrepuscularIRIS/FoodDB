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
  SubgraphResponse,
  LLMAssessResponse,
  SubgraphQueryParams,
  ModelAV2Meta,
  ModelAV2Subgraph,
  ModelAV2GraphView,
  ModelAModeAReportResponse,
  ModelAScreeningResponse,
  ModelARankingEvalResponse,
  ModelAResourcePlanResponse,
  ModelATemporalSimResponse,
  ModeBOpinionCrawlStartPayload,
  ModeBOpinionCrawlStatus,
  ModeBOpinionImportPayload,
  ModeBOpinionSummary,
  ModeBOpinionTopItem,
  ModeBSymptomAssessData,
  ModeBMultimodalAssessPayload,
  ModeBMultimodalAssessData,
  ModeBQingmingBriefData,
  ModeBQingmingQuickStartPayload,
} from '@/types';

// 创建axios实例
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18080',
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
    const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18080';
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
    const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18080';
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

// 子图 & LLM 评估 API
export const subgraphApi = {
  // 获取子图数据
  getSubgraph: async (params: SubgraphQueryParams): Promise<ApiResponse<SubgraphResponse>> => {
    try {
      const query = new URLSearchParams();
      if (params.region !== undefined) query.append('region', params.region);
      if (params.time_window !== undefined) query.append('time_window', String(params.time_window));
      if (params.k_hop !== undefined) query.append('k_hop', String(params.k_hop));
      if (params.seed_node) query.append('seed_node', params.seed_node);
      if (params.max_nodes !== undefined) query.append('max_nodes', String(params.max_nodes));
      if (params.max_edges !== undefined) query.append('max_edges', String(params.max_edges));

      const response = await api.get(`/api/graph/subgraph?${query.toString()}`);
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  // 触发 LLM 风险评估
  llmAssess: async (params: {
    region?: string;
    time_window?: number;
    k_hop?: number;
    seed_node?: string;
    use_mock_llm?: boolean;
  }): Promise<ApiResponse<LLMAssessResponse>> => {
    try {
      const response = await api.post('/api/modea/llm_assess', {
        region: params.region ?? '上海',
        time_window: params.time_window ?? 30,
        k_hop: params.k_hop ?? 2,
        seed_node: params.seed_node ?? null,
        use_mock_llm: params.use_mock_llm ?? false,
      });
      const payload = response.data;
      return {
        success: !!payload?.success,
        data: payload?.data,
        error: payload?.error,
      };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  // 按企业名搜索节点
  searchNodes: async (q: string, limit = 10): Promise<{
    success: boolean;
    data?: Array<{ node_id: string; name: string; node_type: string; risk_score: number; risk_level: string; product_tag: string }>;
    total?: number;
    error?: string;
  }> => {
    try {
      const response = await api.get(`/api/graph/search?q=${encodeURIComponent(q)}&limit=${limit}`);
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, total: payload?.total };
    } catch (error: any) {
      return { success: false, error: error.message || '搜索失败' };
    }
  },
};

export const modelAV2Api = {
  getMeta: async (): Promise<ApiResponse<ModelAV2Meta>> => {
    try {
      const response = await api.get('/api/modela/v2/meta');
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, error: payload?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  getCategories: async (): Promise<ApiResponse<string[]>> => {
    try {
      const response = await api.get('/api/modela/v2/categories');
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, error: payload?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  getSubgraph: async (params: {
    product_type: string;
    seed_node?: string;
    k_hop?: number;
    max_nodes?: number;
    max_edges?: number;
  }): Promise<ApiResponse<ModelAV2Subgraph>> => {
    try {
      const query = new URLSearchParams();
      query.append('product_type', params.product_type);
      if (params.seed_node) query.append('seed_node', params.seed_node);
      if (params.k_hop !== undefined) query.append('k_hop', String(params.k_hop));
      if (params.max_nodes !== undefined) query.append('max_nodes', String(params.max_nodes));
      if (params.max_edges !== undefined) query.append('max_edges', String(params.max_edges));

      const response = await api.get(`/api/modela/v2/subgraph?${query.toString()}`);
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, error: payload?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  getView: async (params: {
    view_mode: 'full' | 'product';
    product_type?: string;
    seed_node?: string;
    k_hop?: number;
    max_nodes?: number;
    max_edges?: number;
    top_ratio?: number;
  }): Promise<ApiResponse<ModelAV2GraphView>> => {
    try {
      const query = new URLSearchParams();
      query.append('view_mode', params.view_mode);
      if (params.product_type) query.append('product_type', params.product_type);
      if (params.seed_node) query.append('seed_node', params.seed_node);
      if (params.k_hop !== undefined) query.append('k_hop', String(params.k_hop));
      if (params.max_nodes !== undefined) query.append('max_nodes', String(params.max_nodes));
      if (params.max_edges !== undefined) query.append('max_edges', String(params.max_edges));
      if (params.top_ratio !== undefined) query.append('top_ratio', String(params.top_ratio));
      const response = await api.get(`/api/modela/v2/view?${query.toString()}`);
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, error: payload?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  modeAReport: async (payload: {
    view_mode: 'full' | 'product';
    product_type?: string;
    seed_node?: string;
    k_hop?: number;
    max_nodes?: number;
    max_edges?: number;
    top_ratio?: number;
    use_mock_llm?: boolean;
  }): Promise<ApiResponse<ModelAModeAReportResponse>> => {
    try {
      const response = await api.post('/api/modela/v2/modea_report', payload);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  rebuild: async (): Promise<ApiResponse<ModelAV2Meta>> => {
    try {
      const response = await api.post('/api/modela/v2/rebuild');
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, error: payload?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  screening: async (params: {
    product_type?: string;
    node_type?: string;
    top_n?: number;
    max_nodes?: number;
    max_edges?: number;
  }): Promise<ApiResponse<ModelAScreeningResponse>> => {
    try {
      const query = new URLSearchParams();
      if (params.product_type) query.append('product_type', params.product_type);
      if (params.node_type) query.append('node_type', params.node_type);
      query.append('top_n', String(params.top_n ?? 10));
      if (params.max_nodes !== undefined) query.append('max_nodes', String(params.max_nodes));
      if (params.max_edges !== undefined) query.append('max_edges', String(params.max_edges));
      const response = await api.get(`/api/modela/v2/screening?${query.toString()}`);
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, error: payload?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  rankingEval: async (params: {
    product_type?: string;
    node_type?: string;
    top_k?: number;
    max_nodes?: number;
    max_edges?: number;
  }): Promise<ApiResponse<ModelARankingEvalResponse>> => {
    try {
      const query = new URLSearchParams();
      if (params.product_type) query.append('product_type', params.product_type);
      if (params.node_type) query.append('node_type', params.node_type);
      query.append('top_k', String(params.top_k ?? 10));
      if (params.max_nodes !== undefined) query.append('max_nodes', String(params.max_nodes));
      if (params.max_edges !== undefined) query.append('max_edges', String(params.max_edges));
      const response = await api.get(`/api/modela/v2/ranking_eval?${query.toString()}`);
      const payload = response.data;
      return { success: !!payload?.success, data: payload?.data, error: payload?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  resourcePlan: async (payload: {
    product_type?: string;
    node_type?: string;
    budget: number;
    max_enterprises?: number;
    max_nodes?: number;
    max_edges?: number;
    cost_large?: number;
    cost_medium?: number;
    cost_small?: number;
    min_samples_per_type?: number;
  }): Promise<ApiResponse<ModelAResourcePlanResponse>> => {
    try {
      const response = await api.post('/api/modela/v2/resource_plan', payload);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '请求失败' };
    }
  },

  temporalSimulate: async (payload: {
    train_month: string;
    test_month: string;
    product_type?: string;
    node_type?: string;
    max_nodes?: number;
    max_edges?: number;
    top_ratio?: number;
    top_k?: number;
    inspect_count?: number;
    explore_weight?: number;
    seed?: number;
  }): Promise<ApiResponse<ModelATemporalSimResponse>> => {
    try {
      const response = await api.post('/api/modela/v2/temporal_simulate', payload);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '月度训练测试模拟失败' };
    }
  },
};

// ModeB 舆情模块 API（MediaCrawler）
export const modebOpinionApi = {
  startCrawl: async (payload: ModeBOpinionCrawlStartPayload): Promise<ApiResponse<ModeBOpinionCrawlStatus>> => {
    try {
      const response = await api.post('/modeb/opinion/crawl/start', payload);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '启动抓取失败' };
    }
  },

  getCrawlStatus: async (tailLines: number = 80): Promise<ApiResponse<ModeBOpinionCrawlStatus>> => {
    try {
      const response = await api.get(`/modeb/opinion/crawl/status?tail_lines=${tailLines}`);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '获取抓取状态失败' };
    }
  },

  stopCrawl: async (): Promise<ApiResponse<ModeBOpinionCrawlStatus>> => {
    try {
      const response = await api.post('/modeb/opinion/crawl/stop');
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '停止抓取失败' };
    }
  },

  qingmingQuickStart: async (
    payload: ModeBQingmingQuickStartPayload
  ): Promise<ApiResponse<ModeBOpinionCrawlStatus>> => {
    try {
      const response = await api.post('/modeb/opinion/qingming/quick_start', payload);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '清明一键抓取启动失败' };
    }
  },

  importOpinion: async (payload: ModeBOpinionImportPayload): Promise<ApiResponse<ModeBOpinionSummary>> => {
    try {
      const response = await api.post('/modeb/opinion/import', payload);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error };
    } catch (error: any) {
      return { success: false, error: error.message || '导入失败' };
    }
  },

  getSummary: async (): Promise<ApiResponse<ModeBOpinionSummary>> => {
    try {
      const response = await api.get('/modeb/opinion/summary');
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '获取摘要失败' };
    }
  },

  getQingmingBrief: async (params?: {
    platform?: string;
    days?: number;
    top_n?: number;
    media_root?: string;
  }): Promise<ApiResponse<ModeBQingmingBriefData>> => {
    try {
      const q = new URLSearchParams();
      if (params?.platform) q.append('platform', params.platform);
      if (params?.days) q.append('days', String(params.days));
      if (params?.top_n) q.append('top_n', String(params.top_n));
      if (params?.media_root) q.append('media_root', params.media_root);
      const query = q.toString();
      const response = await api.get(`/modeb/opinion/qingming/brief${query ? `?${query}` : ''}`);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '获取清明简报失败' };
    }
  },

  getTop: async (topN: number = 20): Promise<ApiResponse<ModeBOpinionTopItem[]>> => {
    try {
      const response = await api.get(`/modeb/opinion/top?top_n=${topN}`);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '获取Top企业失败' };
    }
  },

  symptomAssess: async (query: string, productType?: string): Promise<ApiResponse<ModeBSymptomAssessData>> => {
    try {
      const response = await api.post('/symptom/assess', {
        query,
        product_type: productType || null,
      });
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error };
    } catch (error: any) {
      return { success: false, error: error.message || 'ModeB评估失败' };
    }
  },

  multimodalAssess: async (payload: ModeBMultimodalAssessPayload): Promise<ApiResponse<ModeBMultimodalAssessData>> => {
    try {
      const response = await api.post('/modeb/multimodal/assess', payload);
      const data = response.data;
      return { success: !!data?.success, data: data?.data, error: data?.error || data?.message };
    } catch (error: any) {
      return { success: false, error: error.message || '四模态评估失败' };
    }
  },
};

export default api;
