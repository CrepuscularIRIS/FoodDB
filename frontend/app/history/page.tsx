'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { HistoryRecord, getHistory, removeHistory, clearHistory, groupHistoryByDate, formatTime } from '@/lib/history';
import { RiskAssessmentReport } from '@/types';
import ReportView from '@/components/ReportView';
import {
  ArrowLeftIcon,
  TrashIcon,
  ClockIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [selectedReport, setSelectedReport] = useState<RiskAssessmentReport | null>(null);
  const [showConfirmClear, setShowConfirmClear] = useState(false);

  useEffect(() => {
    setHistory(getHistory());
  }, []);

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    removeHistory(id);
    setHistory(getHistory());
  };

  const handleClearAll = () => {
    clearHistory();
    setHistory([]);
    setShowConfirmClear(false);
  };

  const handleSelect = (record: HistoryRecord) => {
    setSelectedReport(record.report);
  };

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

  const groupedHistory = groupHistoryByDate(history);

  if (selectedReport) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setSelectedReport(null)}
            className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeftIcon className="h-5 w-5 mr-1" />
            返回历史列表
          </button>
          <span className="text-sm text-gray-500">
            历史记录查看
          </span>
        </div>
        <ReportView report={selectedReport} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeftIcon className="h-5 w-5 mr-1" />
            返回首页
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">查询历史</h1>
        </div>
        {history.length > 0 && (
          <button
            onClick={() => setShowConfirmClear(true)}
            className="flex items-center text-red-600 hover:text-red-700 text-sm"
          >
            <TrashIcon className="h-4 w-4 mr-1" />
            清空历史
          </button>
        )}
      </div>

      {/* 确认清空对话框 */}
      {showConfirmClear && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-sm font-medium text-red-800">
                确认清空所有历史记录？
              </h3>
              <p className="text-sm text-red-600 mt-1">
                此操作不可恢复，共 {history.length} 条记录将被删除。
              </p>
              <div className="mt-3 flex gap-3">
                <button
                  onClick={handleClearAll}
                  className="bg-red-600 text-white px-3 py-1.5 rounded text-sm hover:bg-red-700"
                >
                  确认清空
                </button>
                <button
                  onClick={() => setShowConfirmClear(false)}
                  className="bg-white text-gray-700 border border-gray-300 px-3 py-1.5 rounded text-sm hover:bg-gray-50"
                >
                  取消
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 历史列表 */}
      {history.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <ClockIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无查询历史</h3>
          <p className="text-gray-500 mb-4">
            您进行的研判查询将自动保存在这里
          </p>
          <Link
            href="/"
            className="inline-flex items-center bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            <DocumentTextIcon className="h-5 w-5 mr-2" />
            开始新的研判
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedHistory).map(([date, records]) => (
            <div key={date}>
              <h2 className="text-sm font-medium text-gray-500 mb-3 sticky top-0 bg-gray-50 py-2">
                {date}
              </h2>
              <div className="space-y-2">
                {records.map((record) => (
                  <div
                    key={record.id}
                    onClick={() => handleSelect(record)}
                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <span className="font-medium text-gray-900">
                            {record.targetName}
                          </span>
                          <span className={`px-2 py-0.5 text-xs rounded border ${getRiskBadgeClass(record.riskLevel)}`}>
                            {record.riskLevel === 'high' ? '高风险' :
                             record.riskLevel === 'medium' ? '中风险' : '低风险'}
                          </span>
                          <span className="text-sm text-gray-500">
                            {record.riskScore}分
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-4 text-sm text-gray-500">
                          <span>查询: {record.query}</span>
                          <span>类型: {record.targetType === 'batch' ? '批次' : '企业'}</span>
                          <span>{formatTime(record.timestamp)}</span>
                        </div>
                      </div>
                      <button
                        onClick={(e) => handleDelete(record.id, e)}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除此记录"
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 底部提示 */}
      {history.length > 0 && (
        <p className="text-center text-sm text-gray-400">
          共 {history.length} 条历史记录，最多保存 {50} 条
        </p>
      )}
    </div>
  );
}
