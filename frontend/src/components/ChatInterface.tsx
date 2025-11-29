import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, RotateCcw, Wifi } from 'lucide-react';
import type { ChatMessage, TransparencyEvent } from '@/types';
import { chatApi, type CompleteEvent } from '@/services/api';

interface ChatInterfaceProps {
  onAgentsActive: (agents: string[]) => void;
  onWorkflowUpdate: (workflow: any) => void;
  onTransparencyEvents: (events: TransparencyEvent[]) => void;
  onProcessingChange: (isProcessing: boolean) => void;
  onStreamingChange?: (isStreaming: boolean) => void;
  onNewChat?: () => void;
}

export function ChatInterface({
  onAgentsActive,
  onWorkflowUpdate: _onWorkflowUpdate,
  onTransparencyEvents,
  onProcessingChange,
  onStreamingChange,
  onNewChat
}: ChatInterfaceProps) {
  // Note: _onWorkflowUpdate reserved for future workflow state management
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [isStreaming, setIsStreaming] = useState(false);
  const [_streamStatus, setStreamStatus] = useState<'idle' | 'connected' | 'error'>('idle');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const streamEventsRef = useRef<TransparencyEvent[]>([]);

  // Cleanup event source on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Handle new chat - reset all state
  const handleNewChat = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setMessages([]);
    setConversationId(undefined);
    setInput('');
    setIsStreaming(false);
    onStreamingChange?.(false);
    setStreamStatus('idle');
    streamEventsRef.current = [];
    onNewChat?.();
  }, [onNewChat, onStreamingChange]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle incoming streaming event
  const handleStreamEvent = useCallback((event: TransparencyEvent) => {
    // Add event to our collection
    streamEventsRef.current = [...streamEventsRef.current, event];

    // Update transparency events display
    onTransparencyEvents([...streamEventsRef.current]);

    // Track active agents
    const activeAgents = new Set<string>();
    streamEventsRef.current.forEach(e => {
      // Consider agent active if it has recent activity (not result/error)
      if (e.event_type !== 'result' && e.event_type !== 'error') {
        activeAgents.add(e.agent_name);
      }
    });
    onAgentsActive(Array.from(activeAgents));
  }, [onAgentsActive, onTransparencyEvents]);

  // Handle stream completion
  const handleStreamComplete = useCallback((data: CompleteEvent) => {
    setIsStreaming(false);
    onStreamingChange?.(false);
    setStreamStatus('idle');
    setIsLoading(false);
    onProcessingChange(false);

    // Create assistant message from response
    if (data.response?.complete && data.response.content) {
      const assistantMessage: ChatMessage = {
        id: data.response.message_id || Date.now().toString(),
        role: 'assistant',
        content: data.response.content,
        timestamp: new Date().toISOString(),
        metadata: data.response.metadata,
      };
      setMessages(prev => [...prev, assistantMessage]);
    }

    // Clear active agents after a delay
    setTimeout(() => {
      onAgentsActive([]);
    }, 2000);
  }, [onAgentsActive, onProcessingChange, onStreamingChange]);

  // Handle stream error
  const handleStreamError = useCallback((error: string) => {
    console.error('Stream error:', error);
    setIsStreaming(false);
    onStreamingChange?.(false);
    setStreamStatus('error');
    setIsLoading(false);
    onProcessingChange(false);

    const errorMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'assistant',
      content: `Sorry, I encountered an error: ${error}. Please try again.`,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, errorMessage]);
    onAgentsActive([]);
  }, [onAgentsActive, onProcessingChange, onStreamingChange]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageText = input;
    setInput('');
    setIsLoading(true);
    setIsStreaming(true);
    onStreamingChange?.(true);
    setStreamStatus('connected');
    onProcessingChange(true);

    // Clear previous events and reset stream events
    streamEventsRef.current = [];
    onTransparencyEvents([]);
    onAgentsActive(['orchestrator']); // Start with orchestrator active

    try {
      // Start chat asynchronously
      const startResponse = await chatApi.startChat(messageText, conversationId);
      setConversationId(startResponse.conversation_id);

      // Connect to SSE stream for real-time events
      eventSourceRef.current = chatApi.streamEvents(
        startResponse.conversation_id,
        handleStreamEvent,
        handleStreamComplete,
        handleStreamError
      );

    } catch (error) {
      console.error('Failed to start chat:', error);
      handleStreamError('Failed to start chat');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-800 rounded-lg">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Multi-Agent Chat</h2>
            <p className="text-sm text-slate-400">Ask questions about your client data</p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={handleNewChat}
              disabled={isLoading}
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Start a new conversation"
            >
              <RotateCcw className="w-4 h-4" />
              New Chat
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 mt-8">
            <p className="text-lg mb-2">Welcome to Agent Profiler!</p>
            <p className="text-sm">Start a conversation with the multi-agent system</p>
            <div className="mt-6 grid grid-cols-2 gap-3 max-w-2xl mx-auto">
              <SampleQuestion onClick={setInput} text="How many clients do I have?" />
              <SampleQuestion onClick={setInput} text="Show me high-value clients" />
              <SampleQuestion onClick={setInput} text="Find patterns in client data" />
              <SampleQuestion onClick={setInput} text="Segment clients by engagement" />
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex items-center gap-3 text-slate-400">
            <div className="relative">
              <Loader2 className="w-5 h-5 animate-spin" />
              {isStreaming && (
                <div className="absolute inset-0 animate-ping opacity-30">
                  <Loader2 className="w-5 h-5" />
                </div>
              )}
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {isStreaming ? 'Agents are working...' : 'Starting...'}
                </span>
                {isStreaming && (
                  <span className="flex items-center gap-1 text-xs text-emerald-400">
                    <Wifi className="w-3 h-3" />
                    Live
                  </span>
                )}
              </div>
              <span className="text-xs text-slate-500">
                {isStreaming
                  ? 'Watch real-time updates in the Agent Network'
                  : 'Connecting to agent network...'}
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question..."
            className="flex-1 px-4 py-2 bg-slate-700 text-white rounded-lg border border-slate-600 focus:outline-none focus:border-primary-500"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg p-4 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-slate-700 text-slate-100'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {message.metadata?.agents_used && message.metadata.agents_used.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-600">
            <p className="text-xs text-slate-400 mb-2">Agents used:</p>
            <div className="flex flex-wrap gap-1">
              {message.metadata.agents_used.map((agent) => (
                <AgentBadge key={agent} agent={agent} />
              ))}
            </div>
          </div>
        )}

        {message.metadata?.workflow_results && (
          <div className="mt-2 text-xs text-slate-400">
            {message.metadata.workflow_results.length} workflow steps executed
          </div>
        )}

        <p className="text-xs text-slate-400 mt-2">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}

// Agent badge with color coding
const agentColors: Record<string, string> = {
  orchestrator: 'bg-violet-500/20 text-violet-300 border-violet-500/50',
  data_ingestion: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50',
  sql_analytics: 'bg-blue-500/20 text-blue-300 border-blue-500/50',
  semantic_search: 'bg-lime-500/20 text-lime-300 border-lime-500/50',
  pattern_recognition: 'bg-amber-500/20 text-amber-300 border-amber-500/50',
  segmentation: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50',
  benchmark: 'bg-pink-500/20 text-pink-300 border-pink-500/50',
  recommendation: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50',
};

function AgentBadge({ agent }: { agent: string }) {
  const colorClass = agentColors[agent] || 'bg-slate-500/20 text-slate-300 border-slate-500/50';
  const displayName = agent
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

  return (
    <span className={`px-2 py-1 text-xs rounded border ${colorClass}`}>
      {displayName}
    </span>
  );
}

function SampleQuestion({ onClick, text }: { onClick: (text: string) => void; text: string }) {
  return (
    <button
      onClick={() => onClick(text)}
      className="p-3 text-sm text-left bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors text-slate-300"
    >
      {text}
    </button>
  );
}
