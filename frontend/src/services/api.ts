import axios from 'axios';

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
