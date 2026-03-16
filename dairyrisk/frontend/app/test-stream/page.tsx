'use client';

import { useState } from 'react';

export default function TestStreamPage() {
  const [logs, setLogs] = useState<string[]>([]);
  const [content, setContent] = useState('');
  const [isRunning, setIsRunning] = useState(false);

  const startStream = async () => {
    setLogs([]);
    setContent('');
    setIsRunning(true);

    try {
      const response = await fetch('http://localhost:8000/assess_stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'ENT-0005', with_propagation: false }),
      });

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              const log = `[${data.step}] ${data.status}: ${data.message}`;
              setLogs(prev => [...prev, log]);

              if (data.step === 'llm_analysis' && data.status === 'stream_chunk') {
                setContent(prev => prev + (data.chunk_content || ''));
              }
            } catch (e) {
              // ignore
            }
          }
        }
      }
    } catch (err) {
      setLogs(prev => [...prev, `Error: ${err}`]);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">流式输出测试</h1>

      <button
        onClick={startStream}
        disabled={isRunning}
        className="px-4 py-2 bg-blue-600 text-white rounded mb-4 disabled:opacity-50"
      >
        {isRunning ? '运行中...' : '开始测试'}
      </button>

      <div className="grid grid-cols-2 gap-4">
        <div className="border rounded p-4">
          <h2 className="font-medium mb-2">事件日志</h2>
          <div className="h-96 overflow-y-auto text-sm font-mono bg-gray-50 p-2">
            {logs.map((log, i) => (
              <div key={i} className="mb-1">{log}</div>
            ))}
          </div>
        </div>

        <div className="border rounded p-4">
          <h2 className="font-medium mb-2">LLM 流式内容</h2>
          <div className="h-96 overflow-y-auto text-sm font-mono bg-gray-50 p-2 whitespace-pre-wrap">
            {content || '等待流式输出...'}
          </div>
        </div>
      </div>
    </div>
  );
}
