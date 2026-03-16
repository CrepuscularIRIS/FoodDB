'use client';

import dynamic from 'next/dynamic';
import { RiskScore } from '@/types';

// 动态导入 ECharts，禁用 SSR
const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });

interface RiskRadarChartProps {
  riskScore: RiskScore;
}

export default function RiskRadarChart({ riskScore }: RiskRadarChartProps) {
  // 9维度风险因子
  const dimensions = [
    { name: '产品类别\n敏感度', key: 'product_risk', max: 100 },
    { name: '供应链\n复杂度', key: 'supply_chain_risk', max: 100 },
    { name: '供应商\n历史风险', key: 'supplier_risk', max: 100 },
    { name: '追溯\n完整性', key: 'traceability_risk', max: 100 },
    { name: '标签\n一致性', key: 'label_risk', max: 100 },
    { name: '历史抽检\n异常', key: 'inspection_risk', max: 100 },
    { name: '行政处罚', key: 'regulatory_risk', max: 100 },
    { name: '冷链\n敏感度', key: 'cold_chain_risk', max: 100 },
    { name: '扩散度', key: 'diffusion_risk', max: 100 },
  ];

  const values = dimensions.map(d => riskScore[d.key as keyof RiskScore] as number || 0);

  const option = {
    color: ['#5470c6', '#91cc75', '#fac858', '#ee6666'],
    radar: {
      indicator: dimensions.map(d => ({ name: d.name, max: d.max })),
      shape: 'polygon',
      splitNumber: 5,
      axisName: {
        color: '#666',
        fontSize: 10,
        lineHeight: 14,
      },
      splitLine: {
        lineStyle: {
          color: [
            'rgba(238, 242, 255, 0.1)',
            'rgba(238, 242, 255, 0.2)',
            'rgba(238, 242, 255, 0.4)',
            'rgba(238, 242, 255, 0.6)',
            'rgba(238, 242, 255, 0.8)',
          ].reverse(),
        },
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(59, 130, 246, 0.05)', 'rgba(59, 130, 246, 0.1)'],
        },
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(59, 130, 246, 0.3)',
        },
      },
    },
    series: [
      {
        name: '风险评分',
        type: 'radar',
        data: [
          {
            value: values,
            name: '当前评估',
            areaStyle: {
              color: 'rgba(59, 130, 246, 0.3)',
            },
            lineStyle: {
              color: '#3b82f6',
              width: 2,
            },
            itemStyle: {
              color: '#3b82f6',
            },
          },
        ],
      },
    ],
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        let result = `<strong>${params.name}</strong><br/>`;
        dimensions.forEach((dim, idx) => {
          result += `${dim.name.replace('\n', '')}: ${values[idx]}分<br/>`;
        });
        return result;
      },
    },
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-2">9维度风险雷达图</h3>
      <ReactECharts
        option={option}
        style={{ height: '280px', width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
      <div className="mt-2 text-xs text-gray-500 text-center">
        总分: <span className="font-semibold text-blue-600">{riskScore.total_score}</span> 分 |
        等级: <span className={`font-semibold ${
          riskScore.risk_level === 'high' ? 'text-red-600' :
          riskScore.risk_level === 'medium' ? 'text-orange-600' : 'text-green-600'
        }`}>
          {riskScore.risk_level === 'high' ? '高风险' :
           riskScore.risk_level === 'medium' ? '中风险' : '低风险'}
        </span>
      </div>
    </div>
  );
}
