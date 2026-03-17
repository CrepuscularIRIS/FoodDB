'use client';

import { useState } from 'react';
import { RiskAssessmentReport } from '@/types';
import {
  ExclamationTriangleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
  ClipboardDocumentListIcon,
  BeakerIcon,
  ArrowPathIcon,
  LightBulbIcon,
  ShareIcon,
  ChartPieIcon,
  SparklesIcon,
  BookOpenIcon,
  HomeIcon,
} from '@heroicons/react/24/outline';
import RiskRadarChart from './RiskRadarChart';
import SupplyChainGraph from './SupplyChainGraph';
import EnterpriseModal from './EnterpriseModal';
import BatchModal from './BatchModal';
import CaseAnalogies from './CaseAnalogies';
import GraphMetrics from './GraphMetrics';
import LLMAnalysis from './LLMAnalysis';
import RiskTimeline from './RiskTimeline';

interface ReportViewProps {
  report: RiskAssessmentReport;
}

export default function ReportView({ report }: ReportViewProps) {
  const [activeTab, setActiveTab] = useState<'conclusion' | 'visualization' | 'evidence' | 'basis' | 'suggestions' | 'llm' | 'cases' | 'network'>('conclusion');
  const [selectedEnterprise, setSelectedEnterprise] = useState<string | null>(null);
  const [selectedBatch, setSelectedBatch] = useState<string | null>(null);

  const getRiskBadgeClass = (level: string) => {
    switch (level) {
      case 'high':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'medium':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'low':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getRiskLabel = (level: string) => {
    switch (level) {
      case 'high':
        return '高风险（红色预警）';
      case 'medium':
        return '中风险（橙色预警）';
      case 'low':
        return '低风险（绿色）';
      default:
        return '未知';
    }
  };

  const tabs = [
    { id: 'conclusion', label: '结论', icon: InformationCircleIcon },
    { id: 'visualization', label: '可视化', icon: ChartPieIcon },
    { id: 'evidence', label: '证据', icon: ClipboardDocumentListIcon },
    { id: 'basis', label: '依据', icon: BeakerIcon },
    { id: 'suggestions', label: '建议', icon: LightBulbIcon },
  ];

  // Add enhanced tabs conditionally
  const enhancedTabs = [
    ...tabs,
    ...(report.case_analogies ? [{ id: 'cases', label: '案例类比', icon: BookOpenIcon }] : []),
    ...(report.llm_analysis ? [{ id: 'llm', label: 'AI分析', icon: SparklesIcon }] : []),
    ...(report.graph_metrics ? [{ id: 'network', label: '网络分析', icon: HomeIcon }] : []),
  ];

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      {/* 报告头部 */}
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">风险研判报告</h2>
            <p className="text-sm text-gray-500 mt-1">
              报告编号: {report.report_id} | 生成时间: {report.generated_at}
            </p>
          </div>
          <div className={`px-4 py-2 rounded-lg border ${getRiskBadgeClass(report.risk_level)}`}>
            <span className="font-medium">{getRiskLabel(report.risk_level)}</span>
            <span className="ml-2">{report.risk_score}/100</span>
          </div>
        </div>
        <div className="mt-3">
          <p className="text-sm text-gray-600">
            <span className="font-medium">研判对象:</span>{' '}
            <button
              onClick={() => {
                if (report.target_type === 'batch') {
                  setSelectedBatch(report.target_id);
                } else {
                  setSelectedEnterprise(report.target_id);
                }
              }}
              className="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
            >
              {report.target_name}
            </button>
            {' '}({report.target_type === 'batch' ? '批次' : '企业'})
          </p>
        </div>
      </div>

      {/* Tab导航 */}
      <div className="border-b border-gray-200">
        <div className="flex flex-wrap">
          {enhancedTabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <Icon className="h-4 w-4 mr-2" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab内容 */}
      <div className="p-6">
        {activeTab === 'conclusion' && (
          <div className="space-y-6">
            <div>
              <h3 className="text-base font-medium text-gray-900 mb-3">研判结论</h3>
              <p className="text-gray-700 leading-relaxed">{report.conclusion}</p>
            </div>

            <div>
              <h3 className="text-base font-medium text-gray-900 mb-3">证据摘要</h3>
              <p className="text-gray-700">{report.evidence_summary}</p>
            </div>

            {report.propagation_analysis && (
              <div className="bg-blue-50 rounded-lg p-4">
                <h3 className="text-base font-medium text-blue-900 mb-2 flex items-center">
                  <ShareIcon className="h-5 w-5 mr-2" />
                  风险传播分析
                </h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-blue-600">影响节点:</span>
                    <span className="ml-2 font-medium">{report.propagation_analysis.affected_nodes} 个</span>
                  </div>
                  <div>
                    <span className="text-blue-600">传播半径:</span>
                    <span className="ml-2 font-medium">{report.propagation_analysis.propagation_radius} 跳</span>
                  </div>
                  <div>
                    <span className="text-blue-600">最大深度:</span>
                    <span className="ml-2 font-medium">{report.propagation_analysis.max_hops} 跳</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'visualization' && (
          <div className="space-y-6">
            {/* 风险雷达图 */}
            <RiskRadarChart riskScore={{
              total_score: report.risk_score,
              risk_level: report.risk_level,
              product_risk: report.triggered_rules?.find(r => r.factor === 'product_type')?.score || 0,
              supply_chain_risk: report.triggered_rules?.find(r => r.factor === 'supply_chain')?.score || 0,
              supplier_risk: report.triggered_rules?.find(r => r.factor === 'supplier')?.score || 0,
              traceability_risk: report.triggered_rules?.find(r => r.factor === 'traceability')?.score || 0,
              label_risk: report.triggered_rules?.find(r => r.factor === 'label')?.score || 0,
              inspection_risk: report.triggered_rules?.find(r => r.factor === 'inspection')?.score || 0,
              regulatory_risk: report.triggered_rules?.find(r => r.factor === 'regulatory')?.score || 0,
              cold_chain_risk: report.triggered_rules?.find(r => r.factor === 'cold_chain')?.score || 0,
              diffusion_risk: report.triggered_rules?.find(r => r.factor === 'diffusion')?.score || 0,
            }} />

            {/* 供应链网络图 */}
            <SupplyChainGraph supplyChainPath={report.supply_chain_path || []} />

            {/* 风险演化时间线 */}
            <RiskTimeline sourceNodeId={report.target_id} />

            {/* 触发规则柱状图 */}
            {report.triggered_rules && report.triggered_rules.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-4">风险因子评分详情</h3>
                <div className="space-y-3">
                  {report.triggered_rules.map((rule, idx) => (
                    <div key={idx}>
                      <div className="flex justify-between text-xs text-gray-600 mb-1">
                        <span>{rule.factor}</span>
                        <span>{rule.score}分</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            rule.score >= 70 ? 'bg-red-500' :
                            rule.score >= 40 ? 'bg-orange-500' :
                            'bg-green-500'
                          }`}
                          style={{ width: `${rule.score}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-400 mt-1">{rule.reason}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'evidence' && (
          <div className="space-y-6">
            {/* 数据来源说明 */}
            {report.data_sources && (
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <h3 className="text-base font-medium text-blue-900 mb-3 flex items-center">
                  <InformationCircleIcon className="h-5 w-5 mr-2" />
                  数据来源
                </h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-blue-600">数据版本:</span>
                    <span className="ml-2 font-medium">{report.data_sources.data_version}</span>
                  </div>
                  <div>
                    <span className="text-blue-600">冻结时间:</span>
                    <span className="ml-2 font-medium">{report.data_sources.frozen_at}</span>
                  </div>
                  <div>
                    <span className="text-blue-600">来源类型:</span>
                    <span className="ml-2 font-medium">{report.data_sources.source_type}</span>
                  </div>
                  <div>
                    <span className="text-blue-600">真实数据占比:</span>
                    <span className="ml-2 font-medium">{report.data_sources.real_data_ratio}</span>
                  </div>
                </div>
                <p className="text-sm text-blue-700 mt-2">{report.data_sources.note}</p>
              </div>
            )}

            {/* 证据类型分布 */}
            {report.evidence_types && report.evidence_types.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3">证据类型分布</h3>
                <div className="space-y-3">
                  {report.evidence_types.map((et, idx) => (
                    <div key={idx} className="bg-gray-50 rounded-lg p-4 flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{et.type}</div>
                        <div className="text-sm text-gray-500">{et.evidence_level}</div>
                        <div className="text-sm text-gray-400">来源: {et.data_source}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold text-gray-900">{et.count}</div>
                        <div className={`text-xs ${
                          et.reliability === '高' ? 'text-green-600' : 'text-orange-600'
                        }`}>
                          可信度: {et.reliability}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 检验记录 */}
            {report.related_inspections && report.related_inspections.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3">相关检验记录</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">检验ID</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">日期</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">结果</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">不合格项</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {report.related_inspections.slice(0, 5).map((ins) => (
                        <tr key={ins.inspection_id}>
                          <td className="px-4 py-2 text-sm text-gray-900">{ins.inspection_id}</td>
                          <td className="px-4 py-2 text-sm text-gray-500">{ins.inspection_date}</td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-1 text-xs rounded-full ${
                              ins.test_result === 'qualified'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              {ins.test_result === 'qualified' ? '合格' : '不合格'}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-500">{ins.unqualified_items || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 供应链路径 */}
            {report.supply_chain_path && report.supply_chain_path.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3">供应链路径</h3>
                <div className="space-y-2">
                  {report.supply_chain_path.map((node, idx) => {
                    const isUpstream = node.direction === 'upstream';
                    const isDownstream = node.direction === 'downstream';
                    const isCurrent = node.direction === 'current';
                    return (
                      <div
                        key={idx}
                        className={`flex items-center p-3 rounded-lg ${
                          isUpstream ? 'bg-gray-50' : isDownstream ? 'bg-gray-50' : 'bg-blue-50 border border-blue-200'
                        }`}
                      >
                        <span className="text-lg mr-3">
                          {isUpstream ? '⬆️' : isDownstream ? '⬇️' : '⏺️'}
                        </span>
                        <div>
                          <button
                            onClick={() => setSelectedEnterprise(node.name)}
                            className={`font-medium hover:underline cursor-pointer ${
                              isCurrent ? 'text-blue-700' : 'text-gray-900'
                            }`}
                          >
                            {node.name}
                          </button>
                          <span className="text-sm text-gray-500 ml-2">({node.node_type})</span>
                          <span className="text-sm text-gray-400 ml-2">- {node.relation}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'basis' && (
          <div className="space-y-6">
            {/* GB标准引用 */}
            {report.gb_references && report.gb_references.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3">GB标准条款</h3>
                <div className="space-y-3">
                  {report.gb_references.map((ref, idx) => (
                    <div key={idx} className="bg-gray-50 rounded-lg p-4">
                      <div className="font-medium text-gray-900">{ref.gb_no} {ref.clause}</div>
                      <div className="text-sm text-gray-600 mt-1">{ref.requirement}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 触发规则 */}
            {report.triggered_rules && report.triggered_rules.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3">触发规则</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">因子</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">风险分</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">原因</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {report.triggered_rules.map((rule, idx) => (
                        <tr key={idx}>
                          <td className="px-4 py-2 text-sm text-gray-900">{rule.factor}</td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-1 text-xs rounded-full ${
                              rule.score >= 70 ? 'bg-red-100 text-red-800' :
                              rule.score >= 40 ? 'bg-orange-100 text-orange-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {rule.score}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-600">{rule.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'suggestions' && (
          <div className="space-y-6">
            {/* 抽检建议 */}
            {report.sampling_suggestions && report.sampling_suggestions.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3 flex items-center">
                  <BeakerIcon className="h-5 w-5 mr-2" />
                  抽检建议
                </h3>
                <div className="space-y-3">
                  {report.sampling_suggestions.map((sug, idx) => (
                    <div key={idx} className={`rounded-lg p-4 border ${
                      sug.priority === 'immediate' ? 'bg-red-50 border-red-200' :
                      sug.priority === 'high' ? 'bg-orange-50 border-orange-200' :
                      'bg-blue-50 border-blue-200'
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-gray-900">{sug.action}</span>
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          sug.priority === 'immediate' ? 'bg-red-100 text-red-800' :
                          sug.priority === 'high' ? 'bg-orange-100 text-orange-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {sug.priority === 'immediate' ? '紧急' :
                           sug.priority === 'high' ? '优先' : '常规'}
                        </span>
                      </div>
                      <div className="text-sm text-gray-600 space-y-1">
                        <p><span className="font-medium">目标:</span> {sug.target}</p>
                        <p><span className="font-medium">原因:</span> {sug.reason}</p>
                        <p><span className="font-medium">检验项:</span> {sug.sampling_items.join(', ')}</p>
                        <p><span className="font-medium">时限:</span> {sug.deadline}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 溯源建议 */}
            {report.traceability_suggestions && report.traceability_suggestions.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3 flex items-center">
                  <ArrowPathIcon className="h-5 w-5 mr-2" />
                  溯源建议
                </h3>
                <div className="space-y-3">
                  {report.traceability_suggestions.map((sug, idx) => (
                    <div key={idx} className="bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center mb-2">
                        <span className="text-lg mr-2">
                          {sug.direction === 'upstream' ? '⬆️' :
                           sug.direction === 'downstream' ? '⬇️' : '🏭'}
                        </span>
                        <span className="font-medium text-gray-900">{sug.target}</span>
                      </div>
                      <div className="text-sm text-gray-600 space-y-1">
                        <p><span className="font-medium">行动:</span> {sug.action}</p>
                        <p><span className="font-medium">需核查:</span> {sug.evidence_needed.join(', ')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 风险缓解建议 */}
            {report.risk_mitigation_suggestions && report.risk_mitigation_suggestions.length > 0 && (
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3 flex items-center">
                  <LightBulbIcon className="h-5 w-5 mr-2" />
                  风险缓解建议
                </h3>
                <div className="space-y-3">
                  {report.risk_mitigation_suggestions.map((sug, idx) => (
                    <div key={idx} className="bg-green-50 rounded-lg p-4 border border-green-200">
                      <div className="font-medium text-green-900 mb-1">
                        {sug.category}: {sug.action}
                      </div>
                      <div className="text-sm text-green-700">{sug.details}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* New enhanced tabs */}
        {activeTab === 'cases' && report.case_analogies && (
          <div>
            <h3 className="text-base font-medium text-gray-900 mb-4">历史案例类比</h3>
            <CaseAnalogies analogies={report.case_analogies} />
          </div>
        )}

        {activeTab === 'llm' && report.llm_analysis && (
          <div>
            <LLMAnalysis
              analysis={report.llm_analysis}
              usage={report.llm_usage}
              latencyMs={report.llm_latency_ms}
            />
          </div>
        )}

        {activeTab === 'network' && report.graph_metrics && (
          <div>
            <h3 className="text-base font-medium text-gray-900 mb-4">异构图网络分析</h3>
            <GraphMetrics metrics={report.graph_metrics} />
          </div>
        )}
      </div>

      {/* Modals */}
      {selectedEnterprise && (
        <EnterpriseModal
          enterpriseId={selectedEnterprise}
          onClose={() => setSelectedEnterprise(null)}
        />
      )}
      {selectedBatch && (
        <BatchModal
          batchId={selectedBatch}
          onClose={() => setSelectedBatch(null)}
        />
      )}
    </div>
  );
}
