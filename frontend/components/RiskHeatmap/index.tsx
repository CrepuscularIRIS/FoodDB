'use client';

import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { GraphNode } from '@/data/types';
import { theme } from '@/styles/theme';

interface RiskHeatmapProps {
  nodes: GraphNode[];
}

export default function RiskHeatmap({ nodes }: RiskHeatmapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!containerRef.current || !canvasRef.current) return;
    
    const container = containerRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const { width, height } = container.getBoundingClientRect();
    
    // 设置canvas尺寸（考虑设备像素比）
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);
    
    // 清除画布
    ctx.clearRect(0, 0, width, height);
    
    // 坐标范围
    const lngExtent = d3.extent(nodes, d => d.x) as [number, number];
    const latExtent = d3.extent(nodes, d => d.y) as [number, number];
    
    const xScale = d3.scaleLinear()
      .domain(lngExtent)
      .range([20, width - 20]);
    
    const yScale = d3.scaleLinear()
      .domain(latExtent)
      .range([height - 20, 20]);
    
    // 绘制热力图
    // 只绘制高风险节点
    const highRiskNodes = nodes.filter(n => n.riskLevel === 'high');
    
    highRiskNodes.forEach(node => {
      const x = xScale(node.x);
      const y = yScale(node.y);
      const radius = 30 + node.riskScore * 40; // 根据风险分数调整半径
      
      // 创建径向渐变
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
      const alpha = node.riskScore * 0.6;
      
      gradient.addColorStop(0, `rgba(239, 68, 68, ${alpha})`); // 红色中心
      gradient.addColorStop(0.5, `rgba(239, 68, 68, ${alpha * 0.5})`);
      gradient.addColorStop(1, 'rgba(239, 68, 68, 0)');
      
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();
    });
    
    // 绘制中等风险节点
    const mediumRiskNodes = nodes.filter(n => n.riskLevel === 'medium');
    
    mediumRiskNodes.forEach(node => {
      const x = xScale(node.x);
      const y = yScale(node.y);
      const radius = 20 + node.riskScore * 25;
      
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
      const alpha = node.riskScore * 0.5;
      
      gradient.addColorStop(0, `rgba(245, 158, 11, ${alpha})`); // 橙色中心
      gradient.addColorStop(0.5, `rgba(245, 158, 11, ${alpha * 0.5})`);
      gradient.addColorStop(1, 'rgba(245, 158, 11, 0)');
      
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();
    });
    
  }, [nodes]);

  return (
    <div ref={containerRef} className="w-full h-full relative">
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ 
          background: 'transparent',
          mixBlendMode: 'screen'
        }}
      />
      
      {/* 图例 */}
      <div className="absolute bottom-4 left-4 bg-gray-900/80 p-3 rounded-lg border border-gray-700">
        <p className="text-xs text-gray-400 mb-2">风险热力图</p>
        <div className="flex items-center gap-2 mb-1">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <span className="text-xs text-gray-300">高风险</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-amber-500"></div>
          <span className="text-xs text-gray-300">中风险</span>
        </div>
      </div>
    </div>
  );
}
