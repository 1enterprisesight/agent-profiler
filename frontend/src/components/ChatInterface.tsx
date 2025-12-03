/**
 * ChatInterface Component
 *
 * Main chat interface with message input, history,
 * and agent activity visualization.
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Trash2, ChevronDown, ChevronUp, Bot, User } from 'lucide-react';
import { useChat, Message, AgentActivity } from '../hooks/useChat';
import { clsx } from 'clsx';

interface ChatInterfaceProps {
  dataSourceId?: string;
}

export function ChatInterface({ dataSourceId }: ChatInterfaceProps) {
  const {
    messages,
    isLoading,
    error,
    agentActivities,
    sendMessage,
    clearChat,
  } = useChat();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      sendMessage(input.trim(), dataSourceId);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 rounded-lg border border-slate-700">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary-400" />
          <h2 className="text-sm font-semibold text-white">Data Analysis Chat</h2>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
            title="Clear chat"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[300px] max-h-[500px]">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="w-12 h-12 text-slate-600 mb-4" />
            <p className="text-slate-400 text-sm">
              Ask me anything about your data.
            </p>
            <p className="text-slate-500 text-xs mt-2">
              I'll analyze it and provide detailed insights.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Agent Activities */}
      {agentActivities.length > 0 && (
        <AgentActivitiesPanel activities={agentActivities} />
      )}

      {/* Error */}
      {error && (
        <div className="px-4 py-2 bg-red-900/50 border-t border-red-700">
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-slate-700">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your data..."
            className="flex-1 bg-slate-800 text-white placeholder-slate-500 rounded-lg px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm min-h-[48px] max-h-[200px]"
            rows={1}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={clsx(
              'px-4 rounded-lg transition-colors flex items-center justify-center',
              input.trim() && !isLoading
                ? 'bg-primary-500 hover:bg-primary-600 text-white'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
            )}
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

// Message bubble component
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={clsx('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      <div
        className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          isUser ? 'bg-primary-600' : 'bg-slate-700'
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-primary-400" />
        )}
      </div>

      <div
        className={clsx(
          'max-w-[80%] rounded-lg px-4 py-3',
          isUser ? 'bg-primary-600 text-white' : 'bg-slate-800 text-slate-200'
        )}
      >
        {message.isLoading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Analyzing...</span>
          </div>
        ) : (
          <div className="text-sm whitespace-pre-wrap prose prose-invert prose-sm max-w-none">
            <MessageContent content={message.content} />
          </div>
        )}

        {/* Visualization placeholder */}
        {message.visualization && (
          <div className="mt-3 p-3 bg-slate-900 rounded border border-slate-700">
            <p className="text-xs text-slate-400 mb-2">
              Visualization: {message.visualization.type}
            </p>
            <p className="text-xs text-slate-500">
              {message.visualization.data?.length || 0} data points
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// Simple markdown-like content renderer
function MessageContent({ content }: { content: string }) {
  // Basic markdown processing
  const lines = content.split('\n');

  return (
    <>
      {lines.map((line, i) => {
        // Headers
        if (line.startsWith('### ')) {
          return <h3 key={i} className="font-bold text-white mt-3 mb-1">{line.slice(4)}</h3>;
        }
        if (line.startsWith('## ')) {
          return <h2 key={i} className="font-bold text-white text-lg mt-3 mb-1">{line.slice(3)}</h2>;
        }
        if (line.startsWith('# ')) {
          return <h1 key={i} className="font-bold text-white text-xl mt-3 mb-1">{line.slice(2)}</h1>;
        }

        // Bullet points
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span className="text-primary-400">•</span>
              <span>{formatInlineMarkdown(line.slice(2))}</span>
            </div>
          );
        }

        // Numbered lists
        const numberedMatch = line.match(/^(\d+)\.\s/);
        if (numberedMatch) {
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span className="text-primary-400">{numberedMatch[1]}.</span>
              <span>{formatInlineMarkdown(line.slice(numberedMatch[0].length))}</span>
            </div>
          );
        }

        // Empty lines
        if (!line.trim()) {
          return <div key={i} className="h-2" />;
        }

        // Regular paragraphs
        return <p key={i}>{formatInlineMarkdown(line)}</p>;
      })}
    </>
  );
}

// Format inline markdown (bold, code)
function formatInlineMarkdown(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining) {
    // Bold
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    if (boldMatch && boldMatch.index !== undefined) {
      if (boldMatch.index > 0) {
        parts.push(remaining.slice(0, boldMatch.index));
      }
      parts.push(<strong key={key++} className="text-white font-semibold">{boldMatch[1]}</strong>);
      remaining = remaining.slice(boldMatch.index + boldMatch[0].length);
      continue;
    }

    // Code
    const codeMatch = remaining.match(/`(.+?)`/);
    if (codeMatch && codeMatch.index !== undefined) {
      if (codeMatch.index > 0) {
        parts.push(remaining.slice(0, codeMatch.index));
      }
      parts.push(
        <code key={key++} className="bg-slate-700 px-1 py-0.5 rounded text-primary-300">
          {codeMatch[1]}
        </code>
      );
      remaining = remaining.slice(codeMatch.index + codeMatch[0].length);
      continue;
    }

    parts.push(remaining);
    break;
  }

  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

// Agent activities panel
function AgentActivitiesPanel({ activities }: { activities: AgentActivity[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-t border-slate-700">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-2 flex items-center justify-between text-sm text-slate-400 hover:bg-slate-800 transition-colors"
      >
        <span className="flex items-center gap-2">
          <Bot className="w-4 h-4" />
          {activities.length} agent{activities.length !== 1 ? 's' : ''} involved
        </span>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-2">
          {activities.map((activity, i) => (
            <div key={i} className="bg-slate-800 rounded p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono text-primary-400">{activity.agent}</span>
              </div>
              <p className="text-xs text-slate-400">{activity.task}</p>
              {activity.result?.insights?.summary && (
                <p className="text-xs text-slate-300 mt-2 border-t border-slate-700 pt-2">
                  {activity.result.insights.summary}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
