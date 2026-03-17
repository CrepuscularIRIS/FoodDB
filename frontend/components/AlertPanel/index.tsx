'use client';

import React, { useEffect, useState } from 'react';
import { AlertItem } from '@/data/types';
import { riskLevelConfig } from '@/styles/theme';
import { BellIcon, ExclamationTriangleIcon, InformationCircleIcon } from '@heroicons/react/24/outline';

interface AlertPanelProps {
  alerts: AlertItem[];
  maxDisplay?: number;
}

export default function AlertPanel({ alerts, maxDisplay = 10 }: AlertPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [displayAlerts, setDisplayAlerts] = useState<AlertItem[]>([]);
  const [newAlertIds, setNewAlertIds] = useState<Set<string>>(new Set());

  // 更新显示的预警
  useEffect(() => {
    const currentIds = new Set(displayAlerts.map(a => a.id));
    const newIds = new Set<string>();
    
    alerts.forEach(alert => {
      if (!currentIds.has(alert.id)) {
        newIds.add(alert.id);
      }
    });
    
    if (newIds.size > 0) {
      setNewAlertIds(newIds);
      setTimeout(() => setNewAlertIds(new Set()), 3000);
    }
    
    setDisplayAlerts(alerts.slice(0, isExpanded ? undefined : maxDisplay));
  }, [alerts, isExpanded, maxDisplay]);

  const highRiskCount = alerts.filter(a => a.level === 'high').length;
  const mediumRiskCount = alerts.filter(a => a.level === 'medium').length;

  const getTimeAgo = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    return `${days}天前`;
  };

  return (
    <div className="bg-gray-900/90 backdrop-blur-md rounded-xl border border-gray-700 overflow-hidden">
      {/* 头部 */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="relative">
              <BellIcon className="w-5 h-5 text-blue-400" />
              {alerts.length > 0 && (
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
              )}
            </div>
            <h3 className="text-white font-semibold">实时预警</h3>
          </div>
          
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full">
              {highRiskCount} 高
            </span>
            <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded-full">
              {mediumRiskCount} 中
            </span>
          </div>
        </div>

        {/* 统计条 */}
        <div className="flex h-1.5 rounded-full overflow-hidden bg-gray-800">
          <div
            className="bg-red-500 transition-all duration-500"
            style={{ width: `${(highRiskCount / alerts.length) * 100}%` }}
          />
          <div
            className="bg-amber-500 transition-all duration-500"
            style={{ width: `${(mediumRiskCount / alerts.length) * 100}%` }}
          />
        </div>
      </div>

      {/* 预警列表 */}
      <div className="max-h-96 overflow-y-auto">
        {displayAlerts.length === 0 ? (
          <div className="p-8 text-center">
            <InformationCircleIcon className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">暂无预警信息</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {displayAlerts.map((alert, index) => {
              const isNew = newAlertIds.has(alert.id);
              const riskConfig = riskLevelConfig[alert.level.toUpperCase() as keyof typeof riskLevelConfig];
              
              return (
                <div
                  key={alert.id}
                  className={`p-4 transition-all duration-300 ${
                    isNew ? 'bg-blue-900/20 animate-pulse' : 'hover:bg-gray-800/50'
                  }`}
                  style={{
                    animationDelay: `${index * 50}ms`,
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: riskConfig?.bgColor }}
                    >
                      {alert.level === 'high' ? (
                        <ExclamationTriangleIcon className="w-4 h-4" style={{ color: riskConfig?.color }} />
                      ) : (
                        <InformationCircleIcon className="w-4 h-4" style={{ color: riskConfig?.color }} />
                      )}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-white text-sm font-medium truncate">{alert.title}</p>
                        <span className="text-xs text-gray-500 flex-shrink-0">{getTimeAgo(alert.timestamp)}</span>
                      </div>
                      
                      <p className="text-gray-400 text-xs mb-2">{alert.message}</p>
                      
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${alert.intensity * 100}%`,
                              backgroundColor: riskConfig?.color,
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-500 flex-shrink-0">
                          {(alert.intensity * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 底部展开按钮 */}
      {alerts.length > maxDisplay && (
        <div className="p-3 border-t border-gray-700">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full py-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            {isExpanded ? '收起' : `查看全部 ${alerts.length} 条预警`}
          </button>
        </div>
      )}
    </div>
  );
}
