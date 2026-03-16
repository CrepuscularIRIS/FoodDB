'use client';

import { useState, useEffect } from 'react';
import { SparklesIcon } from '@heroicons/react/24/outline';

interface LLMStreamDisplayProps {
  streamContent: string;
  isActive: boolean;
  onComplete?: () => void;
}

export default function LLMStreamDisplay({
  streamContent,
  isActive,
  onComplete,
}: LLMStreamDisplayProps) {
  const [displayContent, setDisplayContent] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  // Typewriter effect for new content
  useEffect(() => {
    if (!streamContent || streamContent.length === 0) {
      setDisplayContent('');
      return;
    }

    // If content is shorter than what we've displayed, reset
    if (streamContent.length < displayContent.length) {
      setDisplayContent(streamContent);
      return;
    }

    // Get the new content to add
    const newContent = streamContent.slice(displayContent.length);

    if (newContent.length > 0) {
      setIsTyping(true);

      // Add characters one by one with a small delay for visual effect
      let index = 0;
      const typeNextChar = () => {
        if (index < newContent.length) {
          setDisplayContent(prev => prev + newContent[index]);
          index++;
          // Faster typing for longer chunks
          const delay = newContent.length > 50 ? 5 : 15;
          setTimeout(typeNextChar, delay);
        } else {
          setIsTyping(false);
        }
      };

      typeNextChar();
    }
  }, [streamContent]);

  // Call onComplete when stream ends
  useEffect(() => {
    if (!isActive && displayContent.length > 0 && !isTyping) {
      onComplete?.();
    }
  }, [isActive, isTyping, displayContent, onComplete]);

  if (!isActive && displayContent.length === 0) {
    return null;
  }

  // Format the content for display (handle JSON-like content)
  const formatContent = (content: string) => {
    // Try to extract readable text from JSON if present
    try {
      // Look for JSON in the content
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const jsonObj = JSON.parse(jsonMatch[0]);

        // Extract key fields
        const sections = [];
        if (jsonObj.executive_summary) {
          sections.push({ title: '执行摘要', content: jsonObj.executive_summary });
        }
        if (jsonObj.deep_analysis) {
          sections.push({ title: '深度分析', content: jsonObj.deep_analysis });
        }
        if (jsonObj.root_cause) {
          sections.push({ title: '根因分析', content: jsonObj.root_cause });
        }
        if (jsonObj.immediate_actions) {
          sections.push({ title: '立即行动', content: jsonObj.immediate_actions.join('\n') });
        }

        if (sections.length > 0) {
          return sections;
        }
      }
    } catch (e) {
      // Not valid JSON or parsing failed, show raw content
    }

    // Return raw content split into lines
    return [{ title: 'AI 深度分析', content }];
  };

  const sections = formatContent(displayContent);

  return (
    <div className="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <SparklesIcon className="h-5 w-5 text-indigo-600 animate-pulse" />
        <span className="font-medium text-indigo-900">Minimax M2.5 深度分析</span>
        {isActive && (
          <span className="text-xs text-indigo-500">
            生成中... ({streamContent.length} 字符)
          </span>
        )}
        {isTyping && (
          <span className="inline-block w-2 h-4 bg-indigo-600 animate-pulse ml-1" />
        )}
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {sections.map((section, idx) => (
          <div key={idx} className="bg-white/60 rounded p-3">
            <h4 className="text-sm font-medium text-indigo-800 mb-1">
              {section.title}
            </h4>
            <div className="text-sm text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
              {section.content}
            </div>
          </div>
        ))}
      </div>

      {isActive && (
        <div className="mt-3 flex items-center space-x-2 text-xs text-indigo-500">
          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-indigo-600" />
          <span>Minimax M2.5 正在实时生成分析...</span>
        </div>
      )}
    </div>
  );
}
