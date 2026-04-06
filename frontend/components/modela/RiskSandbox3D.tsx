'use client';

import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, Html } from '@react-three/drei';
import { useMemo } from 'react';
import type { ModelAV2Node } from '@/types';

interface Props {
  nodes: ModelAV2Node[];
  onPickNode?: (node: ModelAV2Node) => void;
}

function scoreOf(n: ModelAV2Node): number {
  return Number(n.priority_score ?? n.risk_proxy ?? n.view_risk_score ?? n.risk_score ?? 0);
}

function nodeColor(score: number): string {
  if (score >= 0.82) return '#ef4444';
  if (score >= 0.66) return '#f97316';
  if (score >= 0.50) return '#eab308';
  if (score >= 0.38) return '#84cc16';
  return '#10b981';
}

function Pillar({
  node,
  x,
  y,
  onPick,
}: {
  node: ModelAV2Node;
  x: number;
  y: number;
  onPick?: (n: ModelAV2Node) => void;
}) {
  const score = scoreOf(node);
  const h = Math.max(0.25, score * 5.5 + 0.15);
  const color = nodeColor(score);

  return (
    <group position={[x, h / 2, y]}>
      <mesh
        castShadow
        receiveShadow
        onClick={(e) => {
          e.stopPropagation();
          onPick?.(node);
        }}
      >
        <cylinderGeometry args={[0.15, 0.15, h, 18]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={score >= 0.72 ? 0.9 : 0.2} roughness={0.25} metalness={0.7} />
      </mesh>
      {score >= 0.78 && (
        <Html distanceFactor={16} position={[0, h / 2 + 0.22, 0]}>
          <div className="rounded bg-rose-600/90 px-1.5 py-0.5 text-[10px] text-white shadow">{node.name}</div>
        </Html>
      )}
    </group>
  );
}

export default function RiskSandbox3D({ nodes, onPickNode }: Props) {
  const topNodes = useMemo(() => {
    const arr = [...nodes];
    arr.sort((a, b) => scoreOf(b) - scoreOf(a));
    return arr.slice(0, 160);
  }, [nodes]);

  const layout = useMemo(() => {
    const cols = Math.max(8, Math.ceil(Math.sqrt(topNodes.length)));
    const gap = 0.55;
    const half = ((cols - 1) * gap) / 2;
    return topNodes.map((n, i) => {
      const row = Math.floor(i / cols);
      const col = i % cols;
      return {
        node: n,
        x: col * gap - half,
        y: row * gap - half,
      };
    });
  }, [topNodes]);

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-950/80 overflow-hidden">
      <div className="px-3 py-2 border-b border-slate-700 text-xs text-slate-300">
        3D 风险沙盘（实验）: Z轴高度 = 风险强度，颜色 = 风险等级，点击柱体可下钻节点解释
      </div>
      <div className="h-[420px] w-full">
        <Canvas shadows camera={{ position: [5.5, 7.5, 8.5], fov: 44 }}>
          <ambientLight intensity={0.45} />
          <directionalLight position={[7, 10, 5]} intensity={1.15} castShadow />
          <Grid args={[18, 18]} cellSize={0.45} cellThickness={0.4} sectionSize={2} sectionThickness={0.6} fadeDistance={25} fadeStrength={1.1} />
          {layout.map((it) => (
            <Pillar key={it.node.node_id} node={it.node} x={it.x} y={it.y} onPick={onPickNode} />
          ))}
          <OrbitControls makeDefault enableDamping dampingFactor={0.1} minDistance={5} maxDistance={22} maxPolarAngle={Math.PI / 2.12} />
        </Canvas>
      </div>
    </div>
  );
}
