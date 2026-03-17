'use client';

import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { RiskStats } from '@/data/types';
import { theme, nodeTypeConfig } from '@/styles/theme';
import { 
  BuildingOfficeIcon, 
  LinkIcon, 
  ExclamationTriangleIcon,
  ChartBarIcon 
} from '@heroicons/react/24/outline';

interface RiskStatsPanelProps {
  stats: RiskStats;
}

export default function RiskStatsPanel({ stats }: RiskStatsPanelProps) {
  const trendRef = useRef<HTMLDivElement>(null);

  // 绘制趋势图
  useEffect(() => {
    if (!trendRef.current || !stats.riskTrend) return;

    const container = trendRef.current;
    const { width, height } = container.getBoundingClientRect();
    
    // 清空
    d3.select(container).selectAll('*').remove();
    
    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height);
    
    const margin = { top: 10, right: 10, bottom: 30, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    
    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);
    
    // 比例尺
    const xScale = d3.scaleBand()
      .domain(stats.riskTrend.map(d => d.date))
      .range([0, innerWidth])
      .padding(0.3);
    
    const yScale = d3.scaleLinear()
      .domain([0, 1])
      .range([innerHeight, 0]);
    
    // 网格线
    g.selectAll('.grid-line')
      .data(yScale.ticks(5))
      .enter()
      .append('line')
      .attr('class', 'grid-line')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', d => yScale(d))
      .attr('y2', d => yScale(d))
      .attr('stroke', theme.colors.border)
      .attr('stroke-dasharray', '2,2');
    
    // X轴
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).tickFormat(d => d.slice(5)))
      .selectAll('text')
      .attr('fill', theme.colors.textSecondary)
      .attr('font-size', '10px');
    
    // Y轴
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(5).tickFormat(d => `${(d as number) * 100}%`))
      .selectAll('text')
      .attr('fill', theme.colors.textSecondary)
      .attr('font-size', '10px');
    
    // 移除轴线
    g.selectAll('.domain').attr('stroke', theme.colors.border);
    g.selectAll('.tick line').attr('stroke', theme.colors.border);
    
    // 线条生成器
    const line = d3.line<{ date: string; value: number }>()
      .x(d => (xScale(d.date) || 0) + xScale.bandwidth() / 2)
      .y(d => yScale(d.value))
      .curve(d3.curveMonotoneX);
    
    // 绘制线条
    g.append('path')
      .datum(stats.riskTrend)
      .attr('fill', 'none')
      .attr('stroke', theme.colors.primary)
      .attr('stroke-width', 2)
      .attr('d', line);
    
    // 绘制点
    g.selectAll('.dot')
      .data(stats.riskTrend)
      .enter()
      .append('circle')
      .attr('class', 'dot')
      .attr('cx', d => (xScale(d.date) || 0) + xScale.bandwidth() / 2)
      .attr('cy', d => yScale(d.value))
      .attr('r', 4)
      .attr('fill', theme.colors.primary)
      .attr('stroke', theme.colors.bgSecondary)
      .attr('stroke-width', 2);
    
  }, [stats.riskTrend]);

  const highRiskPercent = ((stats.highRiskNodes / stats.totalNodes) * 100).toFixed(1);

  return (
    <div className="bg-gray-900/90 backdrop-blur-md rounded-xl border border-gray-700 p-4">
      <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
        <ChartBarIcon className="w-5 h-5 text-blue-400" />
        风险统计概览
      </h3>

      {/* 关键指标卡片 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-1">
            <BuildingOfficeIcon className="w-4 h-4" />
            <span className="text-xs">总节点数</span>
          </div>
          <p className="text-2xl font-bold text-white">{stats.totalNodes}</p>
        </div>

        <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-1">
            <LinkIcon className="w-4 h-4" />
            <span className="text-xs">连接数</span>
          </div>
          <p className="text-2xl font-bold text-white">{stats.totalEdges}</p>
        </div>

        <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-1">
            <ExclamationTriangleIcon className="w-4 h-4" />
            <span className="text-xs">高风险企业</span>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="text-2xl font-bold text-red-400">{stats.highRiskNodes}</p>
            <span className="text-xs text-gray-500">({highRiskPercent}%)</span>
          </div>
        </div>

        <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-1">
            <ExclamationTriangleIcon className="w-4 h-4 text-amber-400" />
            <span className="text-xs">活跃预警</span>
          </div>
          <p className="text-2xl font-bold text-amber-400">{stats.activeAlerts}</p>
        </div>
      </div>

      {/* 节点类型分布 */}
      <div className="mb-4">
        <p className="text-xs text-gray-500 mb-2">节点类型分布</p>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(stats.nodeTypeDistribution).map(([type, count]) => {
            const config = nodeTypeConfig[type as keyof typeof nodeTypeConfig];
            return (
              <div key={type} className="flex items-center gap-2">
                <span className="text-sm">{config?.icon}</span>
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-400">{config?.label}</span>
                    <span className="text-white">{count}</span>
                  </div>
                  <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(count / stats.totalNodes) * 100}%`,
                        backgroundColor: config?.color,
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 风险趋势图 */}
      <div>
        <p className="text-xs text-gray-500 mb-2">风险趋势（近6个月）</p>
        <div ref={trendRef} className="h-32"></div>
      </div>
    </div>
  );
}
