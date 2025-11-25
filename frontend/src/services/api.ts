import axios from 'axios';
import type { ChatResponse, Conversation } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const chatApi = {
  sendMessage: async (message: string, conversationId?: string, context?: any): Promise<ChatResponse> => {
    const response = await api.post('/conversations/chat', {
      message,
      conversation_id: conversationId,
      context,
    });
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

export default api;
