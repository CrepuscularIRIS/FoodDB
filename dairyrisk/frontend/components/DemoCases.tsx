'use client';

import { useState, useEffect } from 'react';
import { PlayIcon, BookOpenIcon } from '@heroicons/react/24/solid';
import { assessmentApi } from '@/lib/api';
import { DemoCase, TargetHint } from '@/types';

interface DemoCasesProps {
  onSelect: (query: string, targetHint?: TargetHint) => void;
}

export default function DemoCases({ onSelect }: DemoCasesProps) {
  const [cases, setCases] = useState<DemoCase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCases = async () => {
      const response = await assessmentApi.getDemoCases();
      // The API returns data directly in response.data (not response.data.data)
      if (response.success && response.data) {
        setCases(response.data);
      }
      setLoading(false);
    };
    fetchCases();
  }, []);

  const getRiskBadgeClass = (level?: string) => {
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

  const getRiskLabel = (level?: string) => {
    switch (level) {
      case 'high':
        return '高风险';
      case 'medium':
        return '中风险';
      case 'low':
        return '低风险';
      default:
        return '未知';
    }
  };

  const getRiskTypeBadgeClass = (type?: string) => {
    switch (type) {
      case '微生物污染':
        return 'bg-purple-100 text-purple-800';
      case '冷链中断':
        return 'bg-blue-100 text-blue-800';
      case '恶意倒卖':
        return 'bg-red-100 text-red-800';
      case '违规添加':
        return 'bg-yellow-100 text-yellow-800';
      case '非法添加':
        return 'bg-rose-100 text-rose-800';
      case '微生物超标':
        return 'bg-indigo-100 text-indigo-800';
      case '产品变质':
        return 'bg-amber-100 text-amber-800';
      case '毒素污染':
        return 'bg-pink-100 text-pink-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center">
            <BookOpenIcon className="h-5 w-5 text-blue-600 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">历史案例库</h2>
          </div>
          <span className="text-sm text-gray-500">基于真实事件构建</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="border border-gray-200 rounded-lg p-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
              <div className="h-3 bg-gray-200 rounded w-full mb-2"></div>
              <div className="h-3 bg-gray-200 rounded w-2/3"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <BookOpenIcon className="h-5 w-5 text-blue-600 mr-2" />
          <h2 className="text-lg font-semibold text-gray-900">历史案例库</h2>
        </div>
        <span className="text-sm text-gray-500">基于真实事件构建</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {cases.map((caseItem) => (
          <div
            key={caseItem.id}
            className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-all cursor-pointer hover:border-blue-300 group"
            onClick={() => onSelect(caseItem.query, caseItem.target_hint)}
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-medium text-gray-900 group-hover:text-blue-700 transition-colors">
                {caseItem.name}
              </h3>
              <span
                className={`px-2 py-0.5 text-xs rounded-full border ${getRiskBadgeClass(
                  caseItem.risk_level
                )}`}
              >
                {getRiskLabel(caseItem.risk_level)}
              </span>
            </div>

            {caseItem.risk_type && (
              <span className={`inline-block px-2 py-0.5 text-xs rounded mb-2 ${getRiskTypeBadgeClass(caseItem.risk_type)}`}>
                {caseItem.risk_type}
              </span>
            )}

            <p className="text-sm text-gray-600 mb-3 line-clamp-2">{caseItem.description}</p>

            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2">
                {caseItem.year && (
                  <span className="text-gray-400">{caseItem.year}年</span>
                )}
                {caseItem.product_type && (
                  <span className="text-gray-400">· {caseItem.product_type}</span>
                )}
              </div>
              <button className="flex items-center text-sm text-blue-600 hover:text-blue-800 font-medium">
                <PlayIcon className="h-4 w-4 mr-1" />
                运行研判
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
