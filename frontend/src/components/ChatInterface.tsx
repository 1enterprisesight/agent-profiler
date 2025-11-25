import { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import type { ChatMessage } from '@/types';
import { chatApi } from '@/services/api';

interface ChatInterfaceProps {
  onAgentsActive: (agents: string[]) => void;
  onWorkflowUpdate: (workflow: any) => void;
}

export function ChatInterface({ onAgentsActive, onWorkflowUpdate }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await chatApi.sendMessage(input, conversationId);

      setConversationId(response.conversation_id);

      // Update active agents
      if (response.response.agents_used) {
        onAgentsActive(response.response.agents_used);
      }

      // Update workflow
      onWorkflowUpdate(response.response.execution_plan);

      const assistantMessage: ChatMessage = {
        id: response.message_id,
        role: 'assistant',
        content: response.response.text,
        timestamp: response.timestamp,
        metadata: {
          agents_used: response.response.agents_used,
          execution_plan: response.response.execution_plan,
          workflow_results: response.response.execution_plan?.workflow_results,
        },
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Clear active agents after a delay
      setTimeout(() => {
        onAgentsActive([]);
      }, 3000);
    } catch (error) {
      console.error('Failed to send message:', error);

      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
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
        <h2 className="text-xl font-bold text-white">Multi-Agent Chat</h2>
        <p className="text-sm text-slate-400">Ask questions about your client data</p>
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
          <div className="flex items-center gap-2 text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Agents are thinking...</span>
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

        {message.metadata?.agents_used && (
          <div className="mt-3 pt-3 border-t border-slate-600">
            <p className="text-xs text-slate-400 mb-2">Agents used:</p>
            <div className="flex flex-wrap gap-1">
              {message.metadata.agents_used.map((agent) => (
                <span
                  key={agent}
                  className="px-2 py-1 text-xs bg-slate-800 rounded"
                >
                  {agent}
                </span>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs text-slate-400 mt-2">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
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
