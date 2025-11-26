import { GoogleLogin } from '@react-oauth/google';
import { LogOut, User } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export function LoginButton() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();

  if (isLoading) {
    return (
      <div className="w-8 h-8 rounded-full bg-slate-700 animate-pulse" />
    );
  }

  if (isAuthenticated && user) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          {user.picture ? (
            <img
              src={user.picture}
              alt={user.name}
              className="w-8 h-8 rounded-full border border-slate-600"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center">
              <User className="w-4 h-4" />
            </div>
          )}
          <span className="text-sm text-slate-300 hidden md:block">
            {user.name || user.email}
          </span>
        </div>
        <button
          onClick={logout}
          className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
          title="Sign out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <GoogleLogin
      onSuccess={async (credentialResponse) => {
        if (credentialResponse.credential) {
          try {
            await login(credentialResponse.credential);
          } catch (error: any) {
            console.error('Login error:', error);
            alert(error.message || 'Login failed. Please try again.');
          }
        }
      }}
      onError={() => {
        console.error('Google Login Failed');
        alert('Google login failed. Please try again.');
      }}
      useOneTap
      theme="filled_black"
      shape="pill"
      text="signin_with"
    />
  );
}
