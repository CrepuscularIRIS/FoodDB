'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';

// 中国地图 GeoJSON 数据 URL (使用阿里云 DataV 地图数据)
const CHINA_GEOJSON_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';

interface ChinaMapProps {
  children?: React.ReactNode;
}

export default function ChinaMap({ children }: ChinaMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!mapRef.current) return;

    // 初始化 ECharts 实例
    const chart = echarts.init(mapRef.current, 'dark', {
      renderer: 'canvas',
    });
    chartRef.current = chart;

    // 加载中国地图 GeoJSON
    fetch(CHINA_GEOJSON_URL)
      .then((res) => res.json())
      .then((geoJson) => {
        // 注册中国地图
        echarts.registerMap('china', geoJson);

        // 配置地图选项 - DataV 深色科技风格
        const option: echarts.EChartsOption = {
          backgroundColor: 'transparent',
          geo: {
            map: 'china',
            roam: true, // 允许缩放和平移
            zoom: 1.2,
            center: [105, 36],
            label: {
              show: true,
              color: 'rgba(255, 255, 255, 0.7)',
              fontSize: 10,
            },
            itemStyle: {
              areaColor: 'rgba(20, 40, 80, 0.6)',
              borderColor: '#1e3a5f',
              borderWidth: 1.5,
              shadowColor: 'rgba(0, 242, 255, 0.2)',
              shadowBlur: 10,
            },
            emphasis: {
              label: {
                show: true,
                color: '#fff',
                fontSize: 12,
                fontWeight: 'bold',
              },
              itemStyle: {
                areaColor: 'rgba(30, 80, 150, 0.8)',
                borderColor: '#00f2ff',
                borderWidth: 2,
                shadowColor: 'rgba(0, 242, 255, 0.5)',
                shadowBlur: 20,
              },
            },
            select: {
              itemStyle: {
                areaColor: 'rgba(40, 100, 180, 0.9)',
              },
            },
            // 深色科技风格渐变
            regions: [
              {
                name: '南海诸岛',
                itemStyle: {
                  areaColor: 'rgba(15, 35, 70, 0.4)',
                },
                label: {
                  show: false,
                },
              },
            ],
          },
          // 添加网格线效果
          series: [
            {
              type: 'effectScatter',
              coordinateSystem: 'geo',
              data: [],
              symbolSize: 0,
              rippleEffect: {
                brushType: 'stroke',
              },
            },
          ],
        };

        chart.setOption(option);
        setLoadError(null);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load China map:', err);
        setLoadError('地图底图加载失败，已切换到简化展示');
        setLoading(false);
      });

    // 响应式调整
    const handleResize = () => {
      chart.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.dispose();
    };
  }, []);

  return (
    <div className="absolute inset-0 z-0">
      {/* 地图容器 */}
      <div
        ref={mapRef}
        className="w-full h-full"
        style={{
          background: 'radial-gradient(ellipse at center, #0a1628 0%, #050a10 100%)',
        }}
      />

      {/* 加载状态 */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-cyan-400 text-sm">加载中国地图数据...</p>
          </div>
        </div>
      )}

      {!loading && loadError && (
        <div className="absolute top-4 right-4 z-20 bg-yellow-900/70 border border-yellow-500/50 text-yellow-200 text-xs px-3 py-2 rounded">
          {loadError}
        </div>
      )}

      {/* 科技风格网格背景 */}
      <div
        className="absolute inset-0 pointer-events-none z-[1]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0, 242, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 242, 255, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
        }}
      />

      {/* 边缘发光效果 */}
      <div
        className="absolute inset-0 pointer-events-none z-[2]"
        style={{
          boxShadow: 'inset 0 0 100px rgba(0, 0, 0, 0.5)',
        }}
      />

      {/* 子组件渲染区域 */}
      {children}
    </div>
  );
}
