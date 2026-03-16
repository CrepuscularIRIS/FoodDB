'use client';

import { useState } from 'react';
import { MagnifyingGlassIcon, BeakerIcon } from '@heroicons/react/24/outline';

interface SearchPanelProps {
  onSearch: (query: string, withPropagation: boolean) => void;
  loading: boolean;
}

export default function SearchPanel({ onSearch, loading }: SearchPanelProps) {
  const [query, setQuery] = useState('');
  const [withPropagation, setWithPropagation] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim(), withPropagation);
    }
  };

  const exampleQueries = [
    'BATCH-000001',
    '光明乳业股份有限公司',
    '上海妙可蓝多食品',
  ];

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <form onSubmit={handleSubmit}>
        <div className="flex flex-col space-y-4">
          {/* 搜索输入 */}
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="block w-full pl-10 pr-24 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="输入企业名称、批次ID或批次号..."
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="absolute right-2 top-2 bottom-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '研判中...' : '开始研判'}
            </button>
          </div>

          {/* 选项 */}
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={withPropagation}
                onChange={(e) => setWithPropagation(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                disabled={loading}
              />
              <span className="text-sm text-gray-600">启用风险传播分析</span>
            </label>

            <div className="flex items-center text-sm text-gray-500">
              <BeakerIcon className="h-4 w-4 mr-1" />
              <span>支持企业名称、批次ID模糊匹配</span>
            </div>
          </div>
        </div>
      </form>

      {/* 示例查询 */}
      <div className="mt-4 pt-4 border-t border-gray-100">
        <p className="text-xs text-gray-500 mb-2">示例查询：</p>
        <div className="flex flex-wrap gap-2">
          {exampleQueries.map((q) => (
            <button
              key={q}
              onClick={() => setQuery(q)}
              className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
              disabled={loading}
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
