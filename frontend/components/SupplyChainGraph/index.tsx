'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import * as echarts from 'echarts';
import { GraphNode, GraphEdge, FilterCriteria } from '@/data/types';
import { theme, nodeTypeConfig, riskLevelConfig } from '@/styles/theme';

interface SupplyChainGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  filters: FilterCriteria;
  selectedNode: GraphNode | null;
  onNodeSelect: (node: GraphNode) => void;
  onNodeHover: (node: GraphNode | null) => void;
  highlightedPath: string[];
}

// 中国地图坐标范围
const CHINA_BOUNDS = {
  lngMin: 73,
  lngMax: 135,
  latMin: 18,
  latMax: 54,
};

export default function SupplyChainGraph({
  nodes,
  edges,
  filters,
  selectedNode,
  onNodeSelect,
  onNodeHover,
  highlightedPath,
}: SupplyChainGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [viewMode, setViewMode] = useState<'echarts' | 'd3'>('echarts');
  
  // 过滤节点
  const filteredNodes = React.useMemo(() => {
    return nodes.filter(node => {
      if (filters.nodeTypes.length > 0 && !filters.nodeTypes.includes(node.type)) return false;
      if (filters.riskLevels.length > 0 && !filters.riskLevels.includes(node.riskLevel)) return false;
      if (node.scale < filters.minScale || node.scale > filters.maxScale) return false;
      if (filters.districts.length > 0 && !filters.districts.includes(node.district)) return false;
      return true;
    });
  }, [nodes, filters]);
  
  // 过滤边
  const filteredEdges = React.useMemo(() => {
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    return edges.filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  }, [edges, filteredNodes]);

  // ECharts 模式渲染
  useEffect(() => {
    if (viewMode !== 'echarts' || !containerRef.current) return;

    // 清理之前的图表
    if (chartRef.current) {
      chartRef.current.dispose();
    }

    const chart = echarts.init(containerRef.current, 'dark', {
      renderer: 'canvas',
    });
    chartRef.current = chart;

    // 转换节点为 ECharts 散点数据
    const nodeData = filteredNodes.map(node => ({
      name: node.name,
      value: [node.x, node.y, node.scale, node.riskScore, node.type, node.id, node.riskLevel],
      itemStyle: {
        color: nodeTypeConfig[node.type]?.color || theme.colors.textSecondary,
        borderColor: selectedNode?.id === node.id 
          ? theme.colors.primary 
          : riskLevelConfig[node.riskLevel.toUpperCase() as keyof typeof riskLevelConfig]?.color || theme.colors.risk.unknown,
        borderWidth: selectedNode?.id === node.id ? 3 : 2,
        shadowBlur: node.riskLevel === 'high' ? 15 : 0,
        shadowColor: theme.colors.risk.high,
      },
      symbolSize: Math.sqrt(node.scale) * 1.5 + 5,
    }));

    // 转换边为 ECharts 线数据
    const edgeData = filteredEdges.map(edge => {
      const source = filteredNodes.find(n => n.id === edge.source);
      const target = filteredNodes.find(n => n.id === edge.target);
      if (!source || !target) return null;
      
      const isHighlighted = highlightedPath.length > 0 && 
        highlightedPath.includes(edge.source) && 
        highlightedPath.includes(edge.target);
      
      return {
        coords: [[source.x, source.y], [target.x, target.y]],
        lineStyle: {
          color: isHighlighted ? theme.colors.primary : theme.colors.border,
          width: isHighlighted ? 2 : 0.5,
          opacity: isHighlighted ? 1 : 0.3,
          curveness: 0.1,
        },
      };
    }).filter(Boolean);

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(15, 25, 45, 0.95)',
        borderColor: '#1e3a5f',
        borderWidth: 1,
        textStyle: { color: '#fff' },
        formatter: (params: any) => {
          if (params.seriesType === 'effectScatter') {
            const [lng, lat, scale, riskScore, type, id, riskLevel] = params.value;
            const typeName = ({
              RAW_MILK: '原奶供应商',
              PROCESSOR: '加工厂',
              LOGISTICS: '物流',
              WAREHOUSE: '仓储',
              DISTRIBUTOR: '经销商',
              RETAILER: '零售商',
            } as Record<string, string>)[type as string] || type;
            return `
              <div style="padding: 8px;">
                <div style="font-weight: bold; margin-bottom: 4px; color: #00f2ff;">${params.name}</div>
                <div style="font-size: 12px; color: #aaa;">类型: ${typeName}</div>
                <div style="font-size: 12px; color: #aaa;">坐标: ${lat.toFixed(2)}°N, ${lng.toFixed(2)}°E</div>
                <div style="font-size: 12px; color: #aaa;">规模: ${scale.toFixed(0)}</div>
                <div style="font-size: 12px; color: ${riskLevel === 'high' ? '#ff4d4f' : riskLevel === 'medium' ? '#faad14' : '#52c41a'};"
                >风险等级: ${riskLevel === 'high' ? '高风险' : riskLevel === 'medium' ? '中风险' : '低风险'}</div>
              </div>
            `;
          }
          return '';
        },
      },
      geo: {
        map: 'china',
        roam: true,
        zoom: 1.2,
        center: [105, 36],
        label: {
          show: true,
          color: 'rgba(255, 255, 255, 0.6)',
          fontSize: 9,
        },
        itemStyle: {
          areaColor: 'rgba(20, 40, 80, 0.3)',
          borderColor: '#1e3a5f',
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: {
            areaColor: 'rgba(30, 80, 150, 0.5)',
          },
        },
      },
      series: [
        // 连线
        {
          type: 'lines',
          coordinateSystem: 'geo',
          data: edgeData as any,
          silent: true,
          zlevel: 1,
        },
        // 节点
        {
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: nodeData,
          rippleEffect: {
            brushType: 'stroke',
            scale: 2.5,
          },
          zlevel: 2,
        },
      ],
    };

    chart.setOption(option);

    // 点击事件
    chart.on('click', (params: any) => {
      if (params.componentType === 'series' && params.seriesType === 'effectScatter') {
        const nodeId = params.value[5];
        const node = filteredNodes.find(n => n.id === nodeId);
        if (node) {
          onNodeSelect(node);
        }
      }
    });

    // 鼠标悬停
    chart.on('mouseover', (params: any) => {
      if (params.componentType === 'series' && params.seriesType === 'effectScatter') {
        const nodeId = params.value[5];
        const node = filteredNodes.find(n => n.id === nodeId);
        if (node) {
          onNodeHover(node);
        }
      }
    });

    chart.on('mouseout', () => {
      onNodeHover(null);
    });

    // 响应式
    const handleResize = () => {
      chart.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.dispose();
    };
  }, [filteredNodes, filteredEdges, selectedNode, highlightedPath, onNodeSelect, onNodeHover, viewMode]);

  // D3 模式渲染 (备用)
  useEffect(() => {
    if (viewMode !== 'd3' || !containerRef.current || !svgRef.current) return;
    
    const container = containerRef.current;
    const svg = d3.select(svgRef.current);
    
    const { width, height } = container.getBoundingClientRect();
    setDimensions({ width, height });
    
    svg.selectAll('*').remove();
    
    svg.attr('width', width).attr('height', height);
    
    const g = svg.append('g');
    
    // 中国地图经纬度范围到像素坐标
    const xScale = d3.scaleLinear()
      .domain([CHINA_BOUNDS.lngMin, CHINA_BOUNDS.lngMax])
      .range([50, width - 50]);
    
    const yScale = d3.scaleLinear()
      .domain([CHINA_BOUNDS.latMin, CHINA_BOUNDS.latMax])
      .range([height - 50, 50]);
    
    const sizeScale = d3.scaleSqrt()
      .domain(d3.extent(filteredNodes, d => d.scale) as [number, number])
      .range([4, 20]);
    
    // 创建连线
    const linkGroup = g.append('g').attr('class', 'links');
    const links = linkGroup.selectAll('line')
      .data(filteredEdges)
      .enter()
      .append('line')
      .attr('stroke', theme.colors.border)
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.4)
      .attr('x1', d => xScale(filteredNodes.find(n => n.id === d.source)?.x || 0))
      .attr('y1', d => yScale(filteredNodes.find(n => n.id === d.source)?.y || 0))
      .attr('x2', d => xScale(filteredNodes.find(n => n.id === d.target)?.x || 0))
      .attr('y2', d => yScale(filteredNodes.find(n => n.id === d.target)?.y || 0));
    
    // 高亮路径
    if (highlightedPath.length > 0) {
      links.attr('stroke', d => {
        const isHighlighted = highlightedPath.includes(d.source) && highlightedPath.includes(d.target);
        return isHighlighted ? theme.colors.primary : theme.colors.border;
      })
      .attr('stroke-width', d => {
        const isHighlighted = highlightedPath.includes(d.source) && highlightedPath.includes(d.target);
        return isHighlighted ? 3 : 1;
      })
      .attr('stroke-opacity', d => {
        const isHighlighted = highlightedPath.includes(d.source) && highlightedPath.includes(d.target);
        return isHighlighted ? 1 : 0.2;
      });
    }
    
    // 创建节点组
    const nodeGroup = g.append('g').attr('class', 'nodes');
    const nodeSelection = nodeGroup.selectAll('g')
      .data(filteredNodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${xScale(d.x)}, ${yScale(d.y)})`)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation();
        onNodeSelect(d);
      })
      .on('mouseenter', (event, d) => {
        onNodeHover(d);
      })
      .on('mouseleave', () => {
        onNodeHover(null);
      });
    
    // 节点外圈
    nodeSelection.append('circle')
      .attr('r', d => sizeScale(d.scale) + 3)
      .attr('fill', 'none')
      .attr('stroke', d => {
        if (selectedNode?.id === d.id) return theme.colors.primary;
        if (highlightedPath.includes(d.id)) return theme.colors.primary;
        return riskLevelConfig[d.riskLevel.toUpperCase() as keyof typeof riskLevelConfig]?.color || theme.colors.risk.unknown;
      })
      .attr('stroke-width', d => selectedNode?.id === d.id ? 3 : 2)
      .attr('stroke-opacity', 0.8);
    
    // 节点主体
    nodeSelection.append('circle')
      .attr('r', d => sizeScale(d.scale))
      .attr('fill', d => nodeTypeConfig[d.type]?.color || theme.colors.textSecondary)
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .attr('fill-opacity', 0.85);
    
    // 高风险节点发光效果
    nodeSelection.filter(d => d.riskLevel === 'high')
      .append('circle')
      .attr('r', d => sizeScale(d.scale) + 6)
      .attr('fill', 'none')
      .attr('stroke', theme.colors.risk.high)
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.3)
      .attr('class', 'pulse-ring');
    
    // 节点标签
    nodeSelection.append('text')
      .attr('dy', d => sizeScale(d.scale) + 15)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.colors.textPrimary)
      .attr('font-size', '10px')
      .attr('font-weight', '500')
      .text(d => d.name.split('-')[2] || d.name)
      .style('pointer-events', 'none')
      .style('text-shadow', '0 1px 2px rgba(0,0,0,0.8)');
    
    // 缩放行为
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString());
        setTransform(event.transform);
      });
    
    svg.call(zoom as any);
    
    svg.on('click', () => {
      onNodeSelect(null as any);
    });
    
    // CSS 动画
    const style = document.createElement('style');
    style.textContent = `
      @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 0.3; }
        50% { transform: scale(1.2); opacity: 0.6; }
      }
      .pulse-ring {
        animation: pulse 2s ease-in-out infinite;
        transform-origin: center;
      }
    `;
    document.head.appendChild(style);
    
    return () => {
      style.remove();
    };
  }, [filteredNodes, filteredEdges, selectedNode, highlightedPath, onNodeSelect, onNodeHover, viewMode]);

  // 窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        setDimensions({ width, height });
      }
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div ref={containerRef} className="w-full h-full relative">
      {viewMode === 'd3' && (
        <svg
          ref={svgRef}
          className="w-full h-full"
          style={{ background: 'transparent' }}
        />
      )}
      
      {/* 视图模式切换 */}
      <div className="absolute top-4 right-4 flex gap-2 z-30">
        <button
          onClick={() => setViewMode('echarts')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            viewMode === 'echarts' 
              ? 'bg-cyan-600 text-white' 
              : 'bg-gray-800/80 text-gray-400 hover:text-white'
          }`}
        >
          ECharts
        </button>
        <button
          onClick={() => setViewMode('d3')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            viewMode === 'd3' 
              ? 'bg-cyan-600 text-white' 
              : 'bg-gray-800/80 text-gray-400 hover:text-white'
          }`}
        >
          D3.js
        </button>
      </div>
      
      {/* 缩放控制 (仅D3模式) */}
      {viewMode === 'd3' && (
        <div className="absolute bottom-4 right-4 flex flex-col gap-2 z-30">
          <button
            className="w-8 h-8 rounded-lg bg-gray-800/80 hover:bg-gray-700/80 text-white flex items-center justify-center transition-colors border border-gray-600"
            onClick={() => {
              const svg = d3.select(svgRef.current);
              svg.transition().call(d3.zoom().transform as any, transform.scale(1.2));
            }}
          >
            +
          </button>
          <button
            className="w-8 h-8 rounded-lg bg-gray-800/80 hover:bg-gray-700/80 text-white flex items-center justify-center transition-colors border border-gray-600"
            onClick={() => {
              const svg = d3.select(svgRef.current);
              svg.transition().call(d3.zoom().transform as any, transform.scale(0.8));
            }}
          >
            -
          </button>
          <button
            className="w-8 h-8 rounded-lg bg-gray-800/80 hover:bg-gray-700/80 text-white flex items-center justify-center transition-colors border border-gray-600"
            onClick={() => {
              const svg = d3.select(svgRef.current);
              svg.transition().call(d3.zoom().transform as any, d3.zoomIdentity);
            }}
          >
            ⌂
          </button>
        </div>
      )}
      
      {/* 节点计数 */}
      <div className="absolute bottom-4 left-4 px-3 py-1.5 rounded-lg bg-gray-900/80 text-xs text-gray-300 border border-gray-700 z-30">
        显示: {filteredNodes.length} / {nodes.length} 节点 | {filteredEdges.length} / {edges.length} 连接
      </div>
    </div>
  );
}
