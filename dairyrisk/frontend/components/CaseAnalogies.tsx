'use client';

import { useState } from 'react';
import { BookOpenIcon, ChevronDownIcon, ChevronUpIcon, LightBulbIcon } from '@heroicons/react/24/outline';
import { CaseAnalogy } from '@/types';

interface CaseAnalogiesProps {
  analogies: CaseAnalogy[];
}

export default function CaseAnalogies({ analogies }: CaseAnalogiesProps) {
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  if (!analogies || analogies.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-6 text-center">
        <BookOpenIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">暂无历史案例类比</p>
      </div>
    );
  }

  const getSimilarityBadges = (similarity: string) => {
    const parts = similarity.split('、');
    return parts.map((part, idx) => (
      <span
        key={idx}
        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 mr-1"
      >
        {part}
      </span>
    ));
  };

  return (
    <div className="space-y-4">
      {analogies.map((analogy, index) => {
        const isExpanded = expandedCase === analogy.case_id;

        return (
          <div
            key={analogy.case_id}
            className={`bg-white rounded-lg border transition-all duration-200 ${
              isExpanded
                ? 'border-blue-300 shadow-md'
                : 'border-gray-200 hover:border-blue-200 hover:shadow-sm'
            }`}
          >
            {/* Header */}
            <div
              className="p-4 cursor-pointer"
              onClick={() => setExpandedCase(isExpanded ? null : analogy.case_id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-lg font-semibold text-gray-900">
                      {analogy.case_name}
                    </span>
                    <span className="text-xs text-gray-400 font-mono">
                      {analogy.case_id}
                    </span>
                  </div>

                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-gray-500">相似度:</span>
                    {getSimilarityBadges(analogy.similarity)}
                  </div>
                </div>

                <button className="ml-4 text-gray-400 hover:text-gray-600">
                  {isExpanded ? (
                    <ChevronUpIcon className="h-5 w-5" />
                  ) : (
                    <ChevronDownIcon className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>

            {/* Expanded Content */}
            {isExpanded && (
              <div className="px-4 pb-4 border-t border-gray-100">
                <div className="pt-4">
                  <div className="flex items-start">
                    <LightBulbIcon className="h-5 w-5 text-yellow-500 mt-0.5 mr-2 flex-shrink-0" />
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 mb-2">
                        关键教训
                      </h4>
                      <p className="text-sm text-gray-600 leading-relaxed">
                        {analogy.key_lesson}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Preview when collapsed */}
            {!isExpanded && (
              <div className="px-4 pb-3">
                <p className="text-sm text-gray-500 line-clamp-2">
                  {analogy.key_lesson}
                </p>
              </div>
            )}
          </div>
        );
      })}

      {/* Summary footer */}
      <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
        <div className="flex items-start">
          <BookOpenIcon className="h-5 w-5 text-blue-600 mt-0.5 mr-2" />
          <div>
            <h4 className="text-sm font-medium text-blue-900">
              案例库说明
            </h4>
            <p className="text-sm text-blue-700 mt-1">
              基于6个真实历史案例进行相似度匹配，为当前研判提供参考依据。
              案例涵盖微生物污染、冷链异常、添加剂违规等风险类型。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
