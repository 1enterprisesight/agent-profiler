import axios from 'axios';
import type { ChatResponse, Conversation, TransparencyEvent } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token to all requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear it and redirect to login
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_info');
      // Dispatch custom event for auth context to handle
      window.dispatchEvent(new CustomEvent('auth:logout'));
    }
    return Promise.reject(error);
  }
);

// Chat start response type
export interface ChatStartResponse {
  conversation_id: string;
  message_id: string;
  status: string;
  stream_url: string;
  timestamp: string;
}

// SSE event types
export interface StreamEvent {
  type: 'event' | 'complete' | 'error';
  data: TransparencyEvent | CompleteEvent | ErrorEvent;
}

export interface CompleteEvent {
  type: 'complete' | 'timeout';
  conversation_id: string;
  total_events?: number;
  response?: {
    complete: boolean;
    message_id?: string;
    content?: string;
    metadata?: any;
  };
}

export interface ErrorEvent {
  type: 'error';
  message: string;
}

export const chatApi = {
  // Synchronous chat (waits for completion)
  sendMessage: async (message: string, conversationId?: string, context?: any): Promise<ChatResponse> => {
    const response = await api.post('/conversations/chat', {
      message,
      conversation_id: conversationId,
      context,
    });
    return response.data;
  },

  // Async chat start (returns immediately, use SSE for events)
  startChat: async (message: string, conversationId?: string, context?: any): Promise<ChatStartResponse> => {
    const response = await api.post('/conversations/chat/start', {
      message,
      conversation_id: conversationId,
      context,
    });
    return response.data;
  },

  // Create SSE connection for streaming events
  streamEvents: (
    conversationId: string,
    onEvent: (event: TransparencyEvent) => void,
    onComplete: (data: CompleteEvent) => void,
    onError: (error: string) => void,
    messageId?: string
  ): EventSource => {
    const token = localStorage.getItem('auth_token');
    const url = `${API_BASE_URL}/stream/events/${conversationId}`;

    // Note: EventSource doesn't support custom headers, so we pass token as query param
    // Backend should support both header and query param auth for SSE
    // Pass message_id to track specific query in multi-query conversations
    const params = new URLSearchParams({ token: token || '' });
    if (messageId) {
      params.append('message_id', messageId);
    }
    const eventSource = new EventSource(`${url}?${params.toString()}`);

    eventSource.addEventListener('event', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as TransparencyEvent;
        onEvent(data);
      } catch (err) {
        console.error('Failed to parse event:', err);
      }
    });

    eventSource.addEventListener('complete', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as CompleteEvent;
        onComplete(data);
        eventSource.close();
      } catch (err) {
        console.error('Failed to parse complete event:', err);
      }
    });

    eventSource.addEventListener('error', (e: MessageEvent) => {
      if (e.data) {
        try {
          const data = JSON.parse(e.data) as ErrorEvent;
          onError(data.message);
        } catch {
          onError('Stream error');
        }
      }
      eventSource.close();
    });

    eventSource.onerror = () => {
      onError('Connection lost');
      eventSource.close();
    };

    return eventSource;
  },

  // Polling fallback for SSE-incompatible clients
  pollEvents: async (conversationId: string, lastEventId?: string) => {
    const params = lastEventId ? { last_event_id: lastEventId } : {};
    const response = await api.get(`/stream/events/${conversationId}/poll`, { params });
    return response.data;
  },

  getConversations: async (): Promise<Conversation[]> => {
    const response = await api.get('/conversations/');
    return response.data;
  },

  getConversationMessages: async (conversationId: string) => {
    const response = await api.get(`/conversations/${conversationId}/messages`);
    return response.data;
  },
};

export const healthApi = {
  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },
};

export const dataApi = {
  uploadCSV: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    // Use 'api' instance to include auth token from interceptors
    const response = await api.post('/uploads/csv', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getDataSources: async () => {
    const response = await api.get('/uploads/history');
    return response.data;
  },

  deleteDataSource: async (dataSourceId: string) => {
    const response = await api.delete(`/uploads/${dataSourceId}`);
    return response.data;
  },
};

export default api;
