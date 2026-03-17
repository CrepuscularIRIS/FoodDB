'use client';

import dynamic from 'next/dynamic';
import { SupplyChainNode } from '@/types';

// 动态导入 ECharts，禁用 SSR
const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });

interface SupplyChainGraphProps {
  supplyChainPath: SupplyChainNode[];
}

export default function SupplyChainGraph({ supplyChainPath }: SupplyChainGraphProps) {
  if (!supplyChainPath || supplyChainPath.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-8 text-center">
        <p className="text-gray-500">暂无供应链数据</p>
      </div>
    );
  }

  // 构建节点和边
  const nodes: any[] = [];
  const links: any[] = [];

  supplyChainPath.forEach((node, index) => {
    const nodeId = `node_${index}`;
    const color = node.direction === 'upstream'
      ? '#3b82f6' // 蓝色 - 上游
      : node.direction === 'downstream'
        ? '#10b981' // 绿色 - 下游
        : '#f59e0b'; // 橙色 - 当前

    const symbolSize = node.direction === 'current' ? 60 : 40;

    nodes.push({
      id: nodeId,
      name: node.name,
      nodeType: node.node_type,
      direction: node.direction,
      relation: node.relation,
      symbolSize: symbolSize,
      itemStyle: {
        color: color,
        borderColor: '#fff',
        borderWidth: 2,
      },
      label: {
        show: true,
        formatter: `{b}\n{nodeType}`,
        fontSize: 11,
        position: 'bottom',
      },
      x: index * 150 - (supplyChainPath.length - 1) * 75,
      y: 0,
      fixed: true,
    });

    if (index > 0) {
      links.push({
        source: `node_${index - 1}`,
        target: nodeId,
        label: {
          show: true,
          formatter: node.relation || '关联',
          fontSize: 9,
        },
        lineStyle: {
          curveness: 0.1,
        },
      });
    }
  });

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const directionMap: Record<string, string> = {
            upstream: '上游供应商',
            current: '当前节点',
            downstream: '下游销售',
          };
          return `
            <strong>${params.data.name}</strong><br/>
            类型: ${params.data.nodeType}<br/>
            方向: ${directionMap[params.data.direction] || params.data.direction}<br/>
            关系: ${params.data.relation || '无'}
          `;
        }
        return params.name;
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: nodes,
        links: links,
        roam: true,
        draggable: true,
        force: {
          repulsion: 300,
          edgeLength: 150,
          gravity: 0.1,
        },
        edgeSymbol: ['circle', 'arrow'],
        edgeSymbolSize: [4, 10],
        lineStyle: {
          opacity: 0.9,
          width: 2,
          curveness: 0.1,
          color: '#94a3b8',
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: {
            width: 4,
          },
        },
      },
    ],
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-700">供应链网络图</h3>
        <div className="flex gap-3 text-xs">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            上游
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
            当前
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            下游
          </span>
        </div>
      </div>
      <ReactECharts
        option={option}
        style={{ height: '300px', width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
      <p className="text-xs text-gray-400 text-center mt-1">
        可拖拽节点调整布局，滚轮缩放
      </p>
    </div>
  );
}
