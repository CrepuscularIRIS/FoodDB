'use client';

import { useEffect, useState } from 'react';
import { Batch } from '@/types';
import { dataApi } from '@/lib/api';
import {
  XMarkIcon,
  CubeIcon,
  BuildingOfficeIcon,
  CalendarIcon,
  ClockIcon,
  TruckIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';

interface BatchModalProps {
  batchId: string;
  onClose: () => void;
}

export default function BatchModal({ batchId, onClose }: BatchModalProps) {
  const [batch, setBatch] = useState<Batch | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setBatch(null);

    const fetchBatch = async () => {
      try {
        const result = await dataApi.getBatch(batchId);
        if (cancelled) return;
        if (result.success && result.data) {
          setBatch(result.data);
        } else {
          setError(result.error || '获取批次信息失败');
        }
      } catch (err: any) {
        if (!cancelled) setError(err.message || '请求失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchBatch();
    return () => { cancelled = true; };
  }, [batchId]);

  // ESC键关闭
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  // 点击背景关闭
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  if (loading) {
    return (
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={handleBackdropClick}
      >
        <div className="bg-white rounded-xl shadow-xl p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-center text-gray-600 mt-4">加载中...</p>
        </div>
      </div>
    );
  }

  if (error || !batch) {
    return (
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={handleBackdropClick}
      >
        <div className="bg-white rounded-xl shadow-xl p-8 max-w-md w-full mx-4">
          <div className="flex items-center gap-3 text-red-600">
            <ExclamationTriangleIcon className="h-6 w-6" />
            <span>{error || '批次信息不存在'}</span>
          </div>
          <button
            onClick={onClose}
            className="mt-4 w-full bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 rounded-lg"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  const getProductTypeLabel = (type: string) => {
    const types: Record<string, string> = {
      'pasteurized': '巴氏杀菌乳',
      'UHT': '灭菌乳',
      'yogurt': '发酵乳',
      'powder': '乳粉',
      'raw_milk': '生乳',
    };
    return types[type] || type;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const calculateExpiryDate = (productionDate: string, shelfLife: number) => {
    const date = new Date(productionDate);
    date.setDate(date.getDate() + shelfLife);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* 头部 */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <CubeIcon className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{batch.product_name}</h2>
              <p className="text-sm text-gray-500">{batch.batch_no}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* 内容 */}
        <div className="p-6 space-y-6">
          {/* 基本信息 */}
          <section>
            <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <CubeIcon className="h-4 w-4 text-gray-400" />
              基本信息
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">产品类型</p>
                <p className="text-sm font-medium text-gray-900">
                  {getProductTypeLabel(batch.product_type)}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">批次号</p>
                <p className="text-sm font-medium text-gray-900">{batch.batch_no}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">企业ID</p>
                <p className="text-sm font-medium text-gray-900">{batch.enterprise_id}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">批次ID</p>
                <p className="text-sm font-medium text-gray-900">{batch.batch_id}</p>
              </div>
            </div>
          </section>

          {/* 日期信息 */}
          <section>
            <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <CalendarIcon className="h-4 w-4 text-gray-400" />
              日期信息
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">生产日期</p>
                <p className="text-sm font-medium text-gray-900">
                  {formatDate(batch.production_date)}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">保质期</p>
                <p className="text-sm font-medium text-gray-900">{batch.shelf_life} 天</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 col-span-2">
                <p className="text-xs text-gray-500">到期日期</p>
                <p className="text-sm font-medium text-gray-900">
                  {calculateExpiryDate(batch.production_date, batch.shelf_life)}
                </p>
              </div>
            </div>
          </section>

          {/* 冷链信息 */}
          <section>
            <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              冷链监控
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">存储平均温度</p>
                <p className={`text-sm font-medium ${
                  batch.storage_temp_avg !== undefined && batch.storage_temp_avg > 4
                    ? 'text-red-600'
                    : 'text-gray-900'
                }`}>
                  {batch.storage_temp_avg !== undefined ? `${batch.storage_temp_avg}°C` : '未记录'}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">运输平均温度</p>
                <p className={`text-sm font-medium ${
                  batch.transport_temp_avg !== undefined && batch.transport_temp_avg > 4
                    ? 'text-red-600'
                    : 'text-gray-900'
                }`}>
                  {batch.transport_temp_avg !== undefined ? `${batch.transport_temp_avg}°C` : '未记录'}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 col-span-2">
                <p className="text-xs text-gray-500 flex items-center gap-1">
                  <TruckIcon className="h-3 w-3" />
                  运输时长
                </p>
                <p className="text-sm font-medium text-gray-900">
                  {batch.transport_duration_hours !== undefined
                    ? `${batch.transport_duration_hours} 小时`
                    : '未记录'}
                </p>
              </div>
            </div>
          </section>

          {/* 风险提示 */}
          {(batch.storage_temp_avg !== undefined && batch.storage_temp_avg > 4) ||
           (batch.transport_temp_avg !== undefined && batch.transport_temp_avg > 4) ? (
            <section className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="text-sm font-medium text-red-800">温度异常警告</h4>
                  <p className="text-sm text-red-600 mt-1">
                    {(batch.storage_temp_avg !== undefined && batch.storage_temp_avg > 4) &&
                     (batch.transport_temp_avg !== undefined && batch.transport_temp_avg > 4)
                      ? '存储和运输温度均超过4°C，可能影响产品质量安全'
                      : (batch.storage_temp_avg !== undefined && batch.storage_temp_avg > 4)
                      ? '存储温度超过4°C，可能影响产品质量安全'
                      : '运输温度超过4°C，可能影响产品质量安全'}
                  </p>
                </div>
              </div>
            </section>
          ) : null}
        </div>

        {/* 底部 */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
