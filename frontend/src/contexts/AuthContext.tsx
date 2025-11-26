import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { googleLogout } from '@react-oauth/google';
import api from '../services/api';

interface User {
  email: string;
  name: string;
  picture: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credential: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    const storedUser = localStorage.getItem('auth_user');

    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(JSON.parse(storedUser));
      // Set default auth header
      api.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
    }
    setIsLoading(false);
  }, []);

  const login = async (credential: string) => {
    try {
      // Exchange Google credential for our JWT
      const response = await api.post('/auth/google', { token: credential });
      const { access_token, user: userData } = response.data;

      // Store token and user
      setToken(access_token);
      setUser(userData);
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('auth_user', JSON.stringify(userData));

      // Set default auth header
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    } catch (error: any) {
      console.error('Login failed:', error);
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  };

  const logout = () => {
    googleLogout();
    setUser(null);
    setToken(null);
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    delete api.defaults.headers.common['Authorization'];
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
