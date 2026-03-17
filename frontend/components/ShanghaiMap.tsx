'use client';

import React from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// 修复默认图标问题
if (typeof window !== 'undefined') {
  delete (L.Icon.Default.prototype as any)._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  });
}

// 上海中心坐标
const SHANGHAI_CENTER: [number, number] = [31.2304, 121.4737];

interface ShanghaiMapProps {
  children?: React.ReactNode;
}

// 地图控制组件
function MapController() {
  const map = useMap();
  
  React.useEffect(() => {
    // 设置地图样式为深色
    const tiles = document.querySelectorAll('.leaflet-tile');
    tiles.forEach(tile => {
      (tile as HTMLElement).style.filter = 'brightness(0.6) contrast(1.1) saturate(0.8)';
    });
  }, []);
  
  return null;
}

export default function ShanghaiMap({ children }: ShanghaiMapProps) {
  return (
    <div className="absolute inset-0 z-0">
      <MapContainer
        center={SHANGHAI_CENTER}
        zoom={10}
        minZoom={9}
        maxZoom={13}
        scrollWheelZoom={true}
        style={{ 
          width: '100%', 
          height: '100%',
          background: '#0a0f1a',
        }}
        className="shanghaimap"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapController />
        
        {children}
      </MapContainer>
      
      {/* 深色遮罩层 */}
      <div 
        className="absolute inset-0 pointer-events-none z-[400]"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 0%, rgba(10, 15, 26, 0.3) 100%)',
        }}
      />
    </div>
  );
}
