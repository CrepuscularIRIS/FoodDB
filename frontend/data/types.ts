/**
 * 供应链可视化数据类型定义
 */

// 节点类型
export type NodeType = 'RAW_MILK' | 'PROCESSOR' | 'LOGISTICS' | 'WAREHOUSE' | 'DISTRIBUTOR' | 'RETAILER';

// 边类型
export type EdgeType = 'SUPPLY' | 'TRANSPORT' | 'STORE' | 'SELL' | 'PROCESS' | 'PARTNERSHIP' | 'CONTRACT' | 'LOGISTICS' | 'QUALITY' | 'OTHER';

// 风险等级
export type RiskLevel = 'high' | 'medium' | 'low' | 'unknown';

// 图节点
export interface GraphNode {
  id: string;
  name: string;
  type: NodeType;
  x: number; // 经度
  y: number; // 纬度
  riskScore: number;
  riskLevel: RiskLevel;
  scale: number; // 企业规模
  district: string;
  address: string;
  creditRating: string;
  violationCount: number;
  lastInspection: string;
}

// 图边
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  weight: number;
}

// 预警项
export interface AlertItem {
  id: string;
  level: 'high' | 'medium';
  title: string;
  message: string;
  timestamp: string;
  intensity: number;
  nodeId: string;
}

// 风险统计
export interface RiskStats {
  totalNodes: number;
  totalEdges: number;
  highRiskNodes: number;
  mediumRiskNodes: number;
  lowRiskNodes: number;
  activeAlerts: number;
  riskTrend: Array<{ date: string; value: number }>;
  nodeTypeDistribution: Record<NodeType, number>;
  topRiskyNodes: Array<{
    id: string;
    name: string;
    riskScore: number;
    type: NodeType;
  }>;
}

// 筛选条件
export interface FilterCriteria {
  nodeTypes: NodeType[];
  riskLevels: RiskLevel[];
  minScale: number;
  maxScale: number;
  districts: string[];
}

// 路径分析结果
export interface PathAnalysis {
  nodes: GraphNode[];
  edges: GraphEdge[];
  hopCount: number;
  pathType: 'upstream' | 'downstream' | 'full';
}
