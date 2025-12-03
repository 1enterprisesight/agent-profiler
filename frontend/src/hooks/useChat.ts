/**
 * useChat Hook
 *
 * Manages chat state, API calls, and WebSocket connection
 * for real-time agent communication.
 */

import { useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agentActivities?: AgentActivity[];
  data?: any;
  visualization?: any;
  isLoading?: boolean;
}

export interface AgentActivity {
  agent: string;
  task: string;
  result?: any;
  status?: 'running' | 'completed' | 'error';
}

export interface ChatState {
  sessionId: string | null;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  agentActivities: AgentActivity[];
}

export function useChat() {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<ChatState>({
    sessionId: null,
    messages: [],
    isLoading: false,
    error: null,
    agentActivities: [],
  });

  // Generate a session ID if none exists
  const getOrCreateSessionId = useCallback(() => {
    if (state.sessionId) return state.sessionId;
    const newSessionId = crypto.randomUUID();
    setState(prev => ({ ...prev, sessionId: newSessionId }));
    return newSessionId;
  }, [state.sessionId]);

  // Send a message via REST API
  const sendMessage = useCallback(async (content: string, dataSourceId?: string) => {
    if (!isAuthenticated || !content.trim()) return;

    const sessionId = getOrCreateSessionId();

    // Add user message immediately
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    // Add loading assistant message
    const loadingMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    };

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage, loadingMessage],
      isLoading: true,
      error: null,
      agentActivities: [],
    }));

    try {
      const response = await api.post('/chat/message', {
        message: content.trim(),
        session_id: sessionId,
        data_source_id: dataSourceId,
      });

      const data = response.data;

      // Replace loading message with actual response
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
        agentActivities: data.agent_activities,
        data: data.data,
        visualization: data.visualization,
      };

      setState(prev => ({
        ...prev,
        sessionId: data.session_id,
        messages: prev.messages.slice(0, -1).concat(assistantMessage),
        isLoading: false,
        agentActivities: data.agent_activities || [],
      }));

    } catch (error: any) {
      console.error('Chat error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to send message';

      // Replace loading message with error
      const errorResponse: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Error: ${errorMessage}`,
        timestamp: new Date(),
      };

      setState(prev => ({
        ...prev,
        messages: prev.messages.slice(0, -1).concat(errorResponse),
        isLoading: false,
        error: errorMessage,
      }));
    }
  }, [isAuthenticated, getOrCreateSessionId]);

  // Clear chat history
  const clearChat = useCallback(() => {
    setState({
      sessionId: null,
      messages: [],
      isLoading: false,
      error: null,
      agentActivities: [],
    });
  }, []);

  // Load session history
  const loadSession = useCallback(async (sessionId: string) => {
    if (!isAuthenticated) return;

    try {
      const response = await api.get(`/chat/sessions/${sessionId}/messages`);
      const messages: Message[] = response.data.map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: new Date(m.created_at),
        agentActivities: m.metadata?.agent_activities,
      }));

      setState(prev => ({
        ...prev,
        sessionId,
        messages,
        error: null,
      }));
    } catch (error: any) {
      console.error('Failed to load session:', error);
      setState(prev => ({
        ...prev,
        error: 'Failed to load chat history',
      }));
    }
  }, [isAuthenticated]);

  // Get list of sessions
  const getSessions = useCallback(async () => {
    if (!isAuthenticated) return [];

    try {
      const response = await api.get('/chat/sessions');
      return response.data;
    } catch (error) {
      console.error('Failed to get sessions:', error);
      return [];
    }
  }, [isAuthenticated]);

  return {
    ...state,
    sendMessage,
    clearChat,
    loadSession,
    getSessions,
  };
}
