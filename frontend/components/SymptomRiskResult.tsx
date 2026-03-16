'use client';

import { useState } from 'react';
import {
  ExclamationTriangleIcon,
  BeakerIcon,
  BuildingOfficeIcon,
  ArrowTrendingUpIcon,
  ClipboardDocumentListIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  LightBulbIcon
} from '@heroicons/react/24/outline';
import { RiskLevel } from '@/types';

interface SymptomRiskFactor {
  risk_factor_id: string;
  name: string;
  category: string;
  description: string;
  score: number;
  typical_sources: string[];
  linked_stages: string[];
}

interface LinkedEnterprise {
  enterprise_id: string;
  enterprise_name: string;
  node_type: string;
  risk_score: number;
  risk_level: RiskLevel;
  reasons: string[];
  credit_rating: string;
  historical_violations: number;
}

interface SymptomAssessResult {
  query: string;
  symptoms_detected: Array<{
    symptom: string;
    symptom_id: string;
    source: string;
  }>;
  risk_factors: SymptomRiskFactor[];
  stage_candidates: Array<{
    stage: string;
    score: number;
    related_risks: string[];
  }>;
  linked_enterprises: LinkedEnterprise[];
  risk_level: RiskLevel;
  confidence: number;
  suggested_actions: string[];
}

interface SymptomRiskResultProps {
  result: SymptomAssessResult | null;
}

const riskLevelConfig: Record<RiskLevel, { bg: string; text: string; border: string; label: string }> = {
  high: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', label: '高风险' },
  medium: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200', label: '中风险' },
  low: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200', label: '低风险' }
};

const categoryColors: Record<string, string> = {
  '微生物污染': 'bg-red-100 text-red-800',
  '化学污染': 'bg-purple-100 text-purple-800',
  '过敏原': 'bg-yellow-100 text-yellow-800',
  '物理污染': 'bg-gray-100 text-gray-800',
  '未知': 'bg-gray-100 text-gray-600'
};

const nodeTypeIcons: Record<string, string> = {
  '牧场': '🐄',
  '乳企': '🏭',
  '物流': '🚚',
  '仓储': '📦',
  '零售': '🏪'
};

export default function SymptomRiskResult({ result }: SymptomRiskResultProps) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    symptoms: true,
    risks: true,
    stages: true,
    enterprises: true,
    actions: true
  });

  if (!result) return null;

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const riskConfig = riskLevelConfig[result.risk_level];

  return (
    <div className="space-y-4">
      {/* Overall Risk Assessment */}
      <div className={`${riskConfig.bg} ${riskConfig.border} border rounded-xl p-6`}>
        <div className="flex items-start justify-between">
          <div>
            <h3 className={`text-lg font-bold ${riskConfig.text} mb-2`}>
              评估结论: {riskConfig.label}
            </h3>
            <p className="text-gray-600 text-sm">
              基于症状描述 &quot;{result.query}&quot; 的风险分析
            </p>
            <div className="mt-3 flex items-center space-x-4 text-sm">
              <span className="text-gray-600">
                置信度: <strong>{(result.confidence * 100).toFixed(1)}%</strong>
              </span>
              <span className="text-gray-600">
                识别症状: <strong>{result.symptoms_detected.length}</strong> 个
              </span>
              <span className="text-gray-600">
                风险因子: <strong>{result.risk_factors.length}</strong> 个
              </span>
            </div>
          </div>
          <div className={`w-16 h-16 rounded-full ${riskConfig.text} bg-white flex items-center justify-center text-2xl font-bold border-2 ${riskConfig.border}`}>
            {result.risk_level === 'high' ? '!' : result.risk_level === 'medium' ? '⚠' : '✓'}
          </div>
        </div>
      </div>

      {/* Detected Symptoms */}
      {result.symptoms_detected.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <button
            onClick={() => toggleSection('symptoms')}
            className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <ClipboardDocumentListIcon className="h-5 w-5 text-rose-500" />
              <h4 className="font-semibold text-gray-800">识别到的症状</h4>
              <span className="text-sm text-gray-500">({result.symptoms_detected.length})</span>
            </div>
            {expandedSections.symptoms ? <ChevronUpIcon className="h-5 w-5 text-gray-400" /> : <ChevronDownIcon className="h-5 w-5 text-gray-400" />}
          </button>
          {expandedSections.symptoms && (
            <div className="p-6">
              <div className="flex flex-wrap gap-2">
                {result.symptoms_detected.map((symptom, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1.5 bg-rose-100 text-rose-700 rounded-full text-sm font-medium"
                  >
                    {symptom.symptom}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Risk Factors */}
      {result.risk_factors.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <button
            onClick={() => toggleSection('risks')}
            className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <ExclamationTriangleIcon className="h-5 w-5 text-orange-500" />
              <h4 className="font-semibold text-gray-800">推断的风险因子</h4>
              <span className="text-sm text-gray-500">({result.risk_factors.length})</span>
            </div>
            {expandedSections.risks ? <ChevronUpIcon className="h-5 w-5 text-gray-400" /> : <ChevronDownIcon className="h-5 w-5 text-gray-400" />}
          </button>
          {expandedSections.risks && (
            <div className="p-6 space-y-4">
              {result.risk_factors.map((risk, idx) => (
                <div key={risk.risk_factor_id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg font-bold text-gray-400">#{idx + 1}</span>
                      <h5 className="font-semibold text-gray-800">{risk.name}</h5>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${categoryColors[risk.category] || categoryColors['未知']}`}>
                        {risk.category}
                      </span>
                    </div>
                    <span className="text-sm font-medium text-orange-600">
                      关联度: {risk.score.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-3">{risk.description}</p>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {risk.typical_sources?.map((source, i) => (
                      <span key={i} className="px-2 py-1 bg-gray-100 text-gray-600 rounded">
                        来源: {source}
                      </span>
                    ))}
                    {risk.linked_stages?.map((stage, i) => (
                      <span key={i} className="px-2 py-1 bg-blue-50 text-blue-600 rounded">
                        环节: {stage}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Stage Candidates */}
      {result.stage_candidates.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <button
            onClick={() => toggleSection('stages')}
            className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <ArrowTrendingUpIcon className="h-5 w-5 text-amber-500" />
              <h4 className="font-semibold text-gray-800">相关生产环节</h4>
              <span className="text-sm text-gray-500">({result.stage_candidates.length})</span>
            </div>
            {expandedSections.stages ? <ChevronUpIcon className="h-5 w-5 text-gray-400" /> : <ChevronDownIcon className="h-5 w-5 text-gray-400" />}
          </button>
          {expandedSections.stages && (
            <div className="p-6">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {result.stage_candidates.map((stage, idx) => (
                  <div key={idx} className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                    <div className="font-medium text-amber-800 mb-1">{stage.stage}</div>
                    <div className="text-xs text-amber-600">
                      关联风险: {stage.related_risks?.join(', ') || '无'}
                    </div>
                    <div className="mt-2 text-xs text-amber-500">
                      风险权重: {stage.score.toFixed(1)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Linked Enterprises */}
      {result.linked_enterprises.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <button
            onClick={() => toggleSection('enterprises')}
            className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <BuildingOfficeIcon className="h-5 w-5 text-blue-500" />
              <h4 className="font-semibold text-gray-800">关联供应链企业</h4>
              <span className="text-sm text-gray-500">({result.linked_enterprises.length})</span>
            </div>
            {expandedSections.enterprises ? <ChevronUpIcon className="h-5 w-5 text-gray-400" /> : <ChevronDownIcon className="h-5 w-5 text-gray-400" />}
          </button>
          {expandedSections.enterprises && (
            <div className="p-6 space-y-3">
              {result.linked_enterprises.map((ent, idx) => (
                <div key={ent.enterprise_id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-2xl">{nodeTypeIcons[ent.node_type] || '🏢'}</span>
                      <div>
                        <h5 className="font-semibold text-gray-800">{ent.enterprise_name}</h5>
                        <span className="text-xs text-gray-500">{ent.enterprise_id}</span>
                      </div>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      ent.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                      ent.risk_level === 'medium' ? 'bg-orange-100 text-orange-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {ent.risk_level === 'high' ? '高风险' : ent.risk_level === 'medium' ? '中风险' : '低风险'}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 mb-2">
                    <span className="font-medium">风险评分: {ent.risk_score.toFixed(1)}</span>
                    <span className="mx-2">|</span>
                    <span>信用等级: {ent.credit_rating}</span>
                    <span className="mx-2">|</span>
                    <span>历史违规: {ent.historical_violations}次</span>
                  </div>
                  <div className="text-xs text-gray-500">
                    <span className="font-medium">关联原因:</span>
                    <ul className="mt-1 space-y-0.5">
                      {ent.reasons.map((reason, i) => (
                        <li key={i}>• {reason}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Suggested Actions */}
      {result.suggested_actions.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <button
            onClick={() => toggleSection('actions')}
            className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <LightBulbIcon className="h-5 w-5 text-yellow-500" />
              <h4 className="font-semibold text-gray-800">监管建议</h4>
              <span className="text-sm text-gray-500">({result.suggested_actions.length})</span>
            </div>
            {expandedSections.actions ? <ChevronUpIcon className="h-5 w-5 text-gray-400" /> : <ChevronDownIcon className="h-5 w-5 text-gray-400" />}
          </button>
          {expandedSections.actions && (
            <div className="p-6">
              <ul className="space-y-3">
                {result.suggested_actions.map((action, idx) => (
                  <li key={idx} className="flex items-start space-x-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-100 text-yellow-700 flex items-center justify-center text-sm font-medium">
                      {idx + 1}
                    </span>
                    <span className="text-gray-700">{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
