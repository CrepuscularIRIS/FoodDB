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

// ==================== 子图 & LLM 评估类型 ====================

export interface SubgraphNodeRiskVector {
  non_food_additives: number;
  pesticide_vet_residue: number;
  food_additive_excess: number;
  microbial_contamination: number;
  heavy_metal: number;
  physical_damage: number;
  other_contaminants: number;
}

export interface SubgraphNode {
  node_id: string;
  name: string;
  node_type: string;
  longitude: number | null;
  latitude: number | null;
  enterprise_scale: string;
  region: string;
  district: string | null;
  product_tag: string;
  observed_edge_count: number;
  risk_score: number;
  risk_level: RiskLevel;
  risk_vector: SubgraphNodeRiskVector;
}

export interface SubgraphEdge {
  edge_id: string;
  source: string;
  target: string;
  source_name: string;
  target_name: string;
  source_type: string;
  target_type: string;
  timestamp: string;
  transit_hours: number | null;
  logistics_company: string;
  logistics_scale: string;
  risk_labels: number[];
  risk_positive_count: number;
  edge_type: string;
}

export interface SubgraphMeta {
  region: string | null;
  start_time: string | null;
  end_time: string | null;
  seed_node: string | null;
  k_hop: number;
  node_count: number;
  edge_count: number;
  capped: boolean;
}

export interface SubgraphResponse {
  meta: SubgraphMeta;
  nodes: SubgraphNode[];
  edges: SubgraphEdge[];
}

export interface TopNodeSummary {
  node_id: string;
  name: string;
  risk_level: RiskLevel;
  risk_score: number;
}

export interface RuleSummary {
  risk_level: RiskLevel;
  risk_score: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  top_nodes: TopNodeSummary[];
}

export interface LLMResult {
  success: boolean;
  latency_ms: number;
  error: string | null;
  content: any;
  usage: any;
  mock: boolean;
}

export interface LLMAssessResponse {
  query: {
    region: string | null;
    time_window: number;
    k_hop: number;
    seed_node: string | null;
  };
  subgraph_meta: SubgraphMeta;
  rule_summary: RuleSummary;
  llm: LLMResult;
}

export interface SubgraphQueryParams {
  region?: string;
  time_window?: number;
  k_hop?: number;
  seed_node?: string;
  max_nodes?: number;
  max_edges?: number;
}

// ==================== ModelA v2 类型 ====================

export interface ModelARiskVector {
  non_food_additives: number;
  pesticide_vet_residue: number;
  food_additive_excess: number;
  microbial_contamination: number;
  heavy_metal: number;
  biotoxin: number;
  other_contaminants: number;
}

export interface ModelAV2Node {
  node_id: string;
  name: string;
  node_type: string;
  enterprise_scale: string;
  longitude: number | null;
  latitude: number | null;
  region: string;
  risk_score: number;
  risk_level: RiskLevel;
  risk_probabilities: number[];
  risk_vector: ModelARiskVector;
  category: string;
  category_risk_probabilities: number[];
  category_risk_vector: ModelARiskVector;
  category_risk_score: number;
  category_risk_level: RiskLevel;
  profile_features: Record<string, number>;
  top5_flags?: Record<string, boolean>;
  top5_count?: number;
  is_top5_any?: boolean;
  view_scope?: 'full' | 'product';
  view_product_type?: string | null;
  view_risk_probabilities?: number[];
  view_risk_score?: number;
  view_risk_level?: RiskLevel;
  risk_proxy?: number;
  credibility_proxy?: number;
  uncertainty_proxy?: number;
  priority_base_score?: number;
  priority_piecewise_score?: number;
  priority_score?: number;
  exploit_score?: number;
  explore_score?: number;
  budget_cost?: number;
  budget_utility?: number;
  coverage_gain?: number;
  source_mix?: Record<string, number>;
  formula_contrib?: {
    risk: Record<string, number>;
    credibility: Record<string, number>;
    uncertainty: Record<string, number>;
    priority?: Record<string, number>;
  };
  kqv_overlay?: {
    enabled: boolean;
    base: number;
    delta: number;
    enhanced: number;
    mu: number;
    tau: number;
    weights: Record<string, number>;
    values: Record<string, number>;
  };
}

export interface ModelAV2Edge {
  edge_id: string;
  batch_id: number;
  source: string;
  target: string;
  source_name: string;
  target_name: string;
  source_type: string;
  target_type: string;
  timestamp: string;
  dairy_product_type: string;
  transit_hours: number;
  origin_stay_hours: number;
  target_stay_hours: number;
  retail_stay_hours: number;
  logistics_company: string;
  logistics_scale: string;
  risk_probabilities: number[];
  risk_vector: ModelARiskVector;
  top5_flags?: Record<string, boolean>;
  top5_count?: number;
  is_top5_any?: boolean;
  view_scope?: 'full' | 'product';
  view_product_type?: string | null;
  view_risk_probabilities?: number[];
  view_risk_score?: number;
  view_risk_level?: RiskLevel;
  time_fragility?: number;
  edge_risk_proxy?: number;
  edge_uncertainty?: number;
  edge_priority?: number;
}

export interface ModelAV2Meta {
  version: string;
  source_dataset: string;
  node_count: number;
  edge_count: number;
  risk_dimensions: string[];
  risk_dimensions_zh: string[];
  product_categories: string[];
  notes: string[];
}

export interface ModelAV2Subgraph {
  meta: {
    product_type: string;
    k_hop: number;
    seed_node: string | null;
    node_count: number;
    edge_count: number;
    risk_dimensions: string[];
    risk_dimensions_zh: string[];
  };
  nodes: ModelAV2Node[];
  edges: ModelAV2Edge[];
}

export interface ModelAV2GraphView {
  meta: {
    view_mode: 'full' | 'product';
    product_type: string | null;
    seed_node: string | null;
    k_hop: number;
    node_count: number;
    edge_count: number;
    risk_dimensions: string[];
    risk_dimensions_zh: string[];
    top5_thresholds: {
      ratio: number;
      node: Record<string, number>;
      edge: Record<string, number>;
    };
    capped_nodes: boolean;
    capped_edges: boolean;
    formula?: {
      formula_version: string;
      parameter_set_id?: string;
      data_version?: string;
      piecewise_enabled?: boolean;
      kqv_enabled?: boolean;
      params?: Record<string, number>;
      query_context?: Record<string, unknown>;
    };
  };
  nodes: ModelAV2Node[];
  edges: ModelAV2Edge[];
}

export interface ModelAModeAReportResponse {
  query: {
    view_mode: 'full' | 'product';
    product_type?: string;
    seed_node?: string;
    k_hop: number;
    max_nodes: number;
    max_edges: number;
    top_ratio: number;
    use_mock_llm: boolean;
  };
  view_meta: ModelAV2GraphView['meta'];
  rule_summary: {
    risk_level: RiskLevel;
    risk_score: number;
    high_count: number;
    low_count: number;
    avg_node_risk: number;
    avg_priority?: number;
    avg_edge_risk: number;
    avg_uncertainty: number;
    avg_credibility?: number;
    top_nodes: Array<{
      node_id: string;
      name: string;
      risk_level: RiskLevel;
      risk_score: number;
    }>;
  };
  llm: {
    success: boolean;
    latency_ms?: number;
    error?: string;
    content?: string;
    usage?: Record<string, unknown>;
    mock: boolean;
  };
}

export interface ModelAScreeningItem {
  node_id: string;
  name: string;
  node_type: string;
  enterprise_scale: string;
  risk_score: number;
  uncertainty: number;
  priority_score: number;
  priority_base_score?: number;
  priority_piecewise_score?: number;
  profile_features: Record<string, number>;
  sample_cost?: number;
  budget_utility?: number;
  coverage_gain?: number;
  source_mix?: Record<string, number>;
  formula_contrib?: {
    risk: Record<string, number>;
    credibility: Record<string, number>;
    uncertainty: Record<string, number>;
    priority?: Record<string, number>;
  };
  kqv_overlay?: {
    enabled: boolean;
    base: number;
    delta: number;
    enhanced: number;
    mu: number;
    tau: number;
    weights: Record<string, number>;
    values: Record<string, number>;
  };
}

export interface ModelAScreeningResponse {
  total_candidates: number;
  top_n: number;
  items: ModelAScreeningItem[];
}

export interface ModelARankingEvalResponse {
  total: number;
  top_k: number;
  positive_total_proxy: number;
  positive_in_top_k_proxy: number;
  precision_at_k: number;
  recall_at_k: number;
}

export interface ModelAResourcePlanResponse {
  budget: number;
  budget_used: number;
  budget_left: number;
  selected_count: number;
  expected_risk_covered: number;
  items: ModelAScreeningItem[];
}

// ==================== ModeB 舆情模块类型 ====================

export interface ModeBOpinionImportPayload {
  media_root?: string;
  enterprise_csv?: string;
  platform?: string;
  days?: number;
}

export interface ModeBOpinionCrawlStartPayload {
  mediacrawler_root?: string;
  platform?: string;
  crawler_type?: 'search' | 'detail' | 'creator';
  login_type?: 'qrcode' | 'phone' | 'cookie';
  keywords?: string;
  headless?: boolean;
  get_comment?: boolean;
  get_sub_comment?: boolean;
  start_page?: number;
  max_comments_count_singlenotes?: number;
  save_data_option?: 'json' | 'csv' | 'excel' | 'sqlite' | 'db' | 'mongodb' | 'postgres';
}

export interface ModeBOpinionCrawlStatus {
  status: 'idle' | 'running' | 'success' | 'failed' | 'stopped' | string;
  run_id?: string | null;
  pid?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  return_code?: number | null;
  command?: string[];
  log_path?: string;
  mediacrawler_root?: string;
  platform_request?: string;
  platform_cli?: string;
  crawler_type?: string;
  keywords?: string;
  log_tail?: string[];
}

export interface ModeBOpinionTopItem {
  enterprise_id: string;
  enterprise_name: string;
  platform: string;
  mention_count_30d: string;
  post_count_30d: string;
  comment_count_30d: string;
  total_engagement_30d: string;
  negative_count_30d: string;
  negative_ratio_30d: string;
  risk_keyword_hits_30d: string;
  hot_negative_count_30d: string;
  opinion_risk_index: string;
  latest_mention_time: string;
}

export interface ModeBOpinionSummary {
  platform: string;
  platforms_scanned?: string[];
  days_window: number;
  scanned_records: number;
  matched_records: number;
  matched_enterprises: number;
  files_scanned: string[];
  media_root: string;
  enterprise_csv: string;
  opinion_feature_loaded_count?: number;
  outputs: {
    feature_csv: string;
    summary_json: string;
    raw_jsonl: string;
  };
  top_enterprises?: ModeBOpinionTopItem[];
}

export interface ModeBSymptomLinkedEnterprise {
  enterprise_id: string;
  enterprise_name: string;
  node_type: string;
  risk_score: number;
  combined_risk_score?: number;
  risk_level: RiskLevel | string;
  reasons: string[];
  credit_rating?: string;
  historical_violations?: number;
  opinion_risk_index?: number;
  opinion_mentions_30d?: number;
  opinion_negative_ratio_30d?: number;
  opinion_risk_keyword_hits_30d?: number;
}

export interface ModeBSymptomAssessData {
  query: string;
  risk_level: string;
  confidence: number;
  risk_factors: any[];
  stage_candidates: any[];
  linked_enterprises: ModeBSymptomLinkedEnterprise[];
  suggested_actions: string[];
  opinion_enabled?: boolean;
  opinion_feature_loaded_count?: number;
}
