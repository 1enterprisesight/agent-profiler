import { DataSourceList } from './components/DataSourceList';
import { DataUpload } from './components/DataUpload';
import { LoginButton } from './components/LoginButton';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useAuth } from './contexts/AuthContext';

function App() {
  const { isAuthenticated, isLoading } = useAuth();

  const handleUploadComplete = () => {
    // Trigger refresh of data source list
    window.dispatchEvent(new CustomEvent('datasource:refresh'));
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* HEADER */}
      <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
                Agent Profiler
              </h1>
              <p className="text-xs text-slate-400">Data Management</p>
            </div>
            <LoginButton />
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="flex-1">
        {isLoading ? (
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-slate-400">Loading...</p>
            </div>
          </div>
        ) : !isAuthenticated ? (
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="text-center max-w-md px-4">
              <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Sign in Required</h2>
              <p className="text-slate-400 text-sm mb-4">
                Sign in with your Enterprise Sight Google account
              </p>
              <LoginButton />
            </div>
          </div>
        ) : (
          <ErrorBoundary>
            <div className="max-w-4xl mx-auto p-4 space-y-6">
              {/* Upload Section */}
              <section>
                <DataUpload onUploadComplete={handleUploadComplete} />
              </section>

              {/* Data Sources List */}
              <section>
                <ErrorBoundary>
                  <DataSourceList />
                </ErrorBoundary>
              </section>
            </div>
          </ErrorBoundary>
        )}
      </main>
    </div>
  );
}

export default App;
