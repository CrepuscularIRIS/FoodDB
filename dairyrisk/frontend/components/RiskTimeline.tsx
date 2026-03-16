'use client';

import { useEffect, useMemo, useState } from 'react';
import { riskApi } from '@/lib/api';
import {
  PlayIcon,
  PauseIcon,
  BackwardIcon,
  ForwardIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';

interface TimelineNode {
  node_id: string;
  risk: number;
  parent?: string;
  direction?: 'upstream' | 'downstream';
  path?: string[];
}

interface TimelineFrame {
  t: number;
  decay: number;
  nodes: TimelineNode[];
}

interface RiskTimelineProps {
  sourceNodeId: string;
  maxSteps?: number;
  autoplayIntervalMs?: number;
}

export default function RiskTimeline({
  sourceNodeId,
  maxSteps = 4,
  autoplayIntervalMs = 1400,
}: RiskTimelineProps) {
  const [timeline, setTimeline] = useState<TimelineFrame[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadTimeline = async () => {
      if (!sourceNodeId) return;
      setLoading(true);
      setError(null);
      setIsPlaying(false);
      setCurrentIndex(0);

      try {
        const result = await riskApi.propagateTimeline({
          node_id: sourceNodeId,
          max_steps: maxSteps,
        });

        if (result.success && result.data?.timeline) {
          setTimeline(result.data.timeline);
        } else {
          setError(result.error || '获取风险时间线失败');
        }
      } catch (err: any) {
        setError(err?.message || '加载风险时间线失败');
      } finally {
        setLoading(false);
      }
    };

    loadTimeline();
  }, [sourceNodeId, maxSteps]);

  useEffect(() => {
    if (!isPlaying || timeline.length <= 1) return;

    const timer = setInterval(() => {
      setCurrentIndex((prev) => {
        if (prev >= timeline.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, autoplayIntervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, timeline.length, autoplayIntervalMs]);

  const currentFrame = timeline[currentIndex];
  const sortedNodes = useMemo(
    () => [...(currentFrame?.nodes || [])].sort((a, b) => b.risk - a.risk),
    [currentFrame]
  );

  const totalNodes = useMemo(
    () => timeline.reduce((sum, frame) => sum + frame.nodes.length, 0),
    [timeline]
  );

  const resetPlayback = () => {
    setIsPlaying(false);
    setCurrentIndex(0);
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-3">风险演化时间线</h3>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/3" />
          <div className="h-2 bg-gray-100 rounded" />
          <div className="h-20 bg-gray-100 rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-2">风险演化时间线</h3>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  if (!timeline.length) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-2">风险演化时间线</h3>
        <p className="text-sm text-gray-500">暂无时间线数据</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">风险演化时间线</h3>
        <div className="text-xs text-gray-500">
          Step {currentFrame?.t ?? 0} / {Math.max(timeline.length - 1, 0)}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
          <div className="text-blue-600">总传播步数</div>
          <div className="text-lg font-semibold text-blue-900">{Math.max(timeline.length - 1, 0)}</div>
        </div>
        <div className="bg-orange-50 rounded-lg p-3 border border-orange-100">
          <div className="text-orange-600">当前衰减</div>
          <div className="text-lg font-semibold text-orange-900">{(currentFrame?.decay ?? 0).toFixed(3)}</div>
        </div>
        <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-100">
          <div className="text-emerald-600">累计影响节点</div>
          <div className="text-lg font-semibold text-emerald-900">{totalNodes}</div>
        </div>
      </div>

      <div className="space-y-2">
        <input
          type="range"
          min={0}
          max={Math.max(timeline.length - 1, 0)}
          value={currentIndex}
          onChange={(e) => {
            setIsPlaying(false);
            setCurrentIndex(Number(e.target.value));
          }}
          className="w-full"
        />

        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
            className="p-2 rounded border border-gray-200 hover:bg-gray-50"
            aria-label="上一帧"
          >
            <BackwardIcon className="h-4 w-4 text-gray-600" />
          </button>
          <button
            onClick={() => setIsPlaying((v) => !v)}
            className="p-2 rounded border border-gray-200 hover:bg-gray-50"
            aria-label={isPlaying ? '暂停' : '播放'}
          >
            {isPlaying ? (
              <PauseIcon className="h-4 w-4 text-gray-700" />
            ) : (
              <PlayIcon className="h-4 w-4 text-gray-700" />
            )}
          </button>
          <button
            onClick={() => setCurrentIndex((prev) => Math.min(timeline.length - 1, prev + 1))}
            className="p-2 rounded border border-gray-200 hover:bg-gray-50"
            aria-label="下一帧"
          >
            <ForwardIcon className="h-4 w-4 text-gray-600" />
          </button>
          <button
            onClick={resetPlayback}
            className="p-2 rounded border border-gray-200 hover:bg-gray-50"
            aria-label="重置"
          >
            <ArrowPathIcon className="h-4 w-4 text-gray-600" />
          </button>
        </div>
      </div>

      <div className="bg-gray-50 rounded-lg border border-gray-100 p-3">
        <div className="text-xs text-gray-500 mb-2">
          当前步新增节点: {sortedNodes.length}
        </div>
        <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
          {sortedNodes.length === 0 ? (
            <p className="text-xs text-gray-500">该时间步没有新增传播节点</p>
          ) : (
            sortedNodes.map((node) => (
              <div key={`${currentFrame.t}-${node.node_id}`}>
                <div className="flex justify-between text-xs text-gray-700 mb-1">
                  <span className="truncate pr-2">{node.node_id}</span>
                  <span>{(node.risk * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-orange-400 to-red-500"
                    style={{ width: `${Math.min(100, node.risk * 100)}%` }}
                  />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
