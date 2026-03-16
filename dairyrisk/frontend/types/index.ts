// 风险等级
export type RiskLevel = 'high' | 'medium' | 'low';

// 研判目标类型
export type TargetType = 'batch' | 'enterprise';

// 企业信息
export interface Enterprise {
  enterprise_id: string;
  enterprise_name: string;
  enterprise_type: string;
  node_type: string;
  address: string;
  latitude?: number;
  longitude?: number;
  license_no: string;
  credit_rating: string;
  historical_violation_count: number;
  supervision_freq: number;
  haccp_certified: boolean;
  iso22000_certified: boolean;
}

// 批次信息
export interface Batch {
  batch_id: string;
  enterprise_id: string;
  product_name: string;
  product_type: string;
  batch_no: string;
  production_date: string;
  shelf_life: number;
  storage_temp_avg?: number;
  transport_temp_avg?: number;
  transport_duration_hours?: number;
}

// 检验记录
export interface Inspection {
  inspection_id: string;
  batch_id?: string;
  enterprise_id: string;
  inspection_type: string;
  inspection_date: string;
  test_result: 'qualified' | 'unqualified';
  unqualified_items?: string;
  risk_level?: RiskLevel;
}

// 风险评分结果
export interface RiskScore {
  total_score: number;
  risk_level: RiskLevel;
  product_risk: number;
  supply_chain_risk: number;
  supplier_risk: number;
  traceability_risk: number;
  label_risk: number;
  inspection_risk: number;
  regulatory_risk: number;
  cold_chain_risk: number;
  diffusion_risk: number;
  triggered_rules?: TriggeredRule[];
}

// 触发规则
export interface TriggeredRule {
  factor: string;
  score: number;
  reason: string;
}

// 抽检建议
export interface SamplingSuggestion {
  priority: 'immediate' | 'high' | 'normal';
  action: string;
  target: string;
  reason: string;
  sampling_items: string[];
  deadline: string;
}

// 溯源建议
export interface TraceabilitySuggestion {
  direction: 'upstream' | 'downstream' | 'internal';
  target: string;
  action: string;
  evidence_needed: string[];
}

// 数据来源
export interface DataSources {
  enterprise_source: string;
  inspection_source: string;
  event_source: string;
  data_version: string;
  frozen_at: string;
  source_type: string;
  real_data_ratio: string;
  note: string;
}

// 证据类型
export interface EvidenceType {
  type: string;
  count: number;
  evidence_level: string;
  data_source: string;
  reliability: string;
}

// 研判报告
export interface RiskAssessmentReport {
  report_id: string;
  generated_at: string;
  target_type: TargetType;
  target_id: string;
  target_name: string;
  risk_level: RiskLevel;
  risk_score: number;
  conclusion: string;
  evidence_summary: string;
  related_inspections: Inspection[];
  related_events: any[];
  supply_chain_path: SupplyChainNode[];
  gb_references: GBReference[];
  triggered_rules: TriggeredRule[];
  sampling_suggestions: SamplingSuggestion[];
  traceability_suggestions: TraceabilitySuggestion[];
  risk_mitigation_suggestions: any[];
  propagation_analysis?: PropagationAnalysis;
  data_sources?: DataSources;
  evidence_types?: EvidenceType[];
  // 增强报告字段
  llm_analysis?: string;
  llm_usage?: LLMUsage;
  llm_latency_ms?: number;
  case_analogies?: CaseAnalogy[];
  graph_metrics?: GraphMetrics;
}

// 供应链节点
export interface SupplyChainNode {
  direction: 'upstream' | 'current' | 'downstream';
  node_type: string;
  name: string;
  relation: string;
}

// GB标准引用
export interface GBReference {
  gb_no: string;
  clause: string;
  requirement: string;
}

// 传播分析
export interface PropagationAnalysis {
  source_node: string;
  max_hops: number;
  affected_nodes: number;
  propagation_radius: number;
  affected_list: Array<{
    node_id: string;
    hop: number;
  }>;
}

// 历史案例类比
export interface CaseAnalogy {
  case_id: string;
  case_name: string;
  similarity: string;
  key_lesson: string;
}

// 异构图指标
export interface GraphMetrics {
  total_nodes: number;
  total_edges: number;
  network_density: number;
  node_type_distribution: Record<string, number>;
}

// LLM使用统计
export interface LLMUsage {
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
}

// LLM分析报告（JSON格式）
export interface LLMAnalysisReport {
  executive_summary: string;
  deep_analysis: string;
  root_cause: string;
  regulatory_basis: string[];
  regulatory_basis_details: Array<{
    gb_no: string;
    clause: string;
    requirement: string;
  }>;
  immediate_actions: string[];
  short_term_actions: string[];
  long_term_recommendations: string[];
  key_risk_factors: string[];
  confidence_assessment: string;
}

// API响应
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// 演示案例目标提示（用于精准定位）
export interface TargetHint {
  type: 'batch' | 'enterprise';
  batch_id?: string;
  enterprise_id?: string;
  product_name?: string;
}

// 演示案例
export interface DemoCase {
  id: string;
  name: string;
  description: string;
  query: string;
  risk_level?: RiskLevel;
  risk_type?: string;
  year?: number;
  product_type?: string;
  target_hint?: TargetHint;
}

// ==================== Mode A/B 联动模式类型 ====================

// 工作流步骤
export type WorkflowStep =
  | 'workflow_start'
  | 'mode_b_analysis'
  | 'hypothesis_generation'
  | 'mode_a_verification'
  | 'report_generation'
  | 'workflow_complete'
  | 'workflow_error';

// 步骤状态
export type StepStatus = 'started' | 'in_progress' | 'complete' | 'error';

// 工作流步骤事件（SSE）
export interface WorkflowStepEvent {
  step: WorkflowStep;
  status: StepStatus;
  timestamp: string;
  message?: string;
  data?: any;
}

// 风险假设
export interface RiskHypothesis {
  risk_factors: string[];
  suspected_stage: string;
  confidence: 'high' | 'medium' | 'low';
  target_candidates: string[];
  suggested_checks: string[];
  population?: string;
  location_hint?: string;
  time_window_days: number;
}

// 企业候选
export interface EnterpriseCandidate {
  enterprise_id: string;
  enterprise_name: string;
  node_type: string;
  score: number;
  matched_signals: string[];
  evidence: {
    violation_records?: string[];
    inspection_records?: string[];
    supply_chain_paths?: string[];
  };
}

// Mode B 症状分析结果
export interface SymptomAnalysisResult {
  symptoms_detected: Array<{
    symptom: string;
    confidence: number;
  }>;
  risk_factors: string[];
  suspected_stage: string;
  risk_level: RiskLevel;
  population?: string;
  recommended_tests: string[];
}

// 联动报告
export interface LinkedReport {
  report_id: string;
  created_at?: string;
  generated_at?: string;
  risk_hypothesis?: RiskHypothesis;
  mode_b_result?: SymptomAnalysisResult;
  hypothesis?: RiskHypothesis;
  matched_enterprises?: EnterpriseCandidate[];
  enterprise_assessments: RiskAssessmentReport[];
  overall_risk_level?: string;
  overall_risk_score?: number;
  combined_conclusion?: string;
  conclusion?: string;
  evidence_chain?: any;
  gb_basis?: any[];
  action_suggestions: any[];
}

// 联动工作流请求
export interface LinkedWorkflowRequest {
  symptom_query: string;
  population?: string;
  location_hint?: string;
  product_type?: string;
  top_k?: number;
}

// 联动工作流响应
export interface LinkedWorkflowResponse {
  success: boolean;
  workflow_id: string;
  status: 'completed' | 'failed' | 'in_progress';
  steps: WorkflowStepEvent[];
  result?: LinkedReport;
  error?: string;
}
