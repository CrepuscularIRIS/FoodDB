'use client';

import { useEffect, useState } from 'react';
import { Enterprise } from '@/types';
import { dataApi } from '@/lib/api';
import {
  XMarkIcon,
  BuildingOfficeIcon,
  MapPinIcon,
  IdentificationIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';

interface EnterpriseModalProps {
  enterpriseId: string;
  onClose: () => void;
}

export default function EnterpriseModal({ enterpriseId, onClose }: EnterpriseModalProps) {
  const [enterprise, setEnterprise] = useState<Enterprise | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setEnterprise(null);

    const fetchEnterprise = async () => {
      try {
        const result = await dataApi.getEnterprise(enterpriseId);
        if (cancelled) return;
        if (result.success && result.data) {
          setEnterprise(result.data);
        } else {
          setError(result.error || '获取企业信息失败');
        }
      } catch (err: any) {
        if (!cancelled) setError(err.message || '请求失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchEnterprise();
    return () => { cancelled = true; };
  }, [enterpriseId]);

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

  if (error || !enterprise) {
    return (
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={handleBackdropClick}
      >
        <div className="bg-white rounded-xl shadow-xl p-8 max-w-md w-full mx-4">
          <div className="flex items-center gap-3 text-red-600">
            <ExclamationTriangleIcon className="h-6 w-6" />
            <span>{error || '企业信息不存在'}</span>
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

  const getCreditBadge = (rating: string) => {
    const colors: Record<string, string> = {
      'A': 'bg-green-100 text-green-800',
      'B': 'bg-blue-100 text-blue-800',
      'C': 'bg-yellow-100 text-yellow-800',
      'D': 'bg-red-100 text-red-800',
    };
    return colors[rating] || 'bg-gray-100 text-gray-800';
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
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <BuildingOfficeIcon className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{enterprise.enterprise_name}</h2>
              <p className="text-sm text-gray-500">{enterprise.enterprise_id}</p>
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
              <IdentificationIcon className="h-4 w-4 text-gray-400" />
              基本信息
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">企业类型</p>
                <p className="text-sm font-medium text-gray-900">
                  {enterprise.enterprise_type === 'large' ? '大型企业' :
                   enterprise.enterprise_type === 'medium' ? '中型企业' :
                   enterprise.enterprise_type === 'small' ? '小型企业' : '微型企业'}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">节点类型</p>
                <p className="text-sm font-medium text-gray-900">{enterprise.node_type}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 col-span-2">
                <p className="text-xs text-gray-500 flex items-center gap-1">
                  <MapPinIcon className="h-3 w-3" />
                  地址
                </p>
                <p className="text-sm font-medium text-gray-900">{enterprise.address}</p>
              </div>
            </div>
          </section>

          {/* 许可信息 */}
          <section>
            <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <ShieldCheckIcon className="h-4 w-4 text-gray-400" />
              许可信息
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">许可证号</p>
                <p className="text-sm font-medium text-gray-900">{enterprise.license_no}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">信用等级</p>
                <span className={`inline-block px-2 py-0.5 text-xs rounded ${getCreditBadge(enterprise.credit_rating)}`}>
                  {enterprise.credit_rating}级
                </span>
              </div>
            </div>
          </section>

          {/* 合规情况 */}
          <section>
            <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <CheckCircleIcon className="h-4 w-4 text-gray-400" />
              合规情况
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">历史违规次数</p>
                <p className={`text-sm font-medium ${
                  enterprise.historical_violation_count > 0 ? 'text-red-600' : 'text-green-600'
                }`}>
                  {enterprise.historical_violation_count} 次
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">监管频次</p>
                <p className="text-sm font-medium text-gray-900">
                  {enterprise.supervision_freq} 次/年
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">HACCP认证</p>
                <p className="text-sm font-medium">
                  {enterprise.haccp_certified ? (
                    <span className="text-green-600">✓ 已认证</span>
                  ) : (
                    <span className="text-gray-400">未认证</span>
                  )}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">ISO22000认证</p>
                <p className="text-sm font-medium">
                  {enterprise.iso22000_certified ? (
                    <span className="text-green-600">✓ 已认证</span>
                  ) : (
                    <span className="text-gray-400">未认证</span>
                  )}
                </p>
              </div>
            </div>
          </section>

          {/* 数据来源 */}
          {'data_source' in enterprise && (
            <section className="pt-4 border-t border-gray-100">
              <p className="text-xs text-gray-400">
                数据来源: {(enterprise as any).data_source === 'public_record' ? '公开数据' : '模拟数据'}
              </p>
            </section>
          )}
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
