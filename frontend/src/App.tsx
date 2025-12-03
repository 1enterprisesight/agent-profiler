import { useState, useEffect } from 'react';
import { DataSourceList } from './components/DataSourceList';
import { DataUpload } from './components/DataUpload';
import { ChatInterface } from './components/ChatInterface';
import { LoginButton } from './components/LoginButton';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useAuth } from './contexts/AuthContext';
import { MessageSquare, Database, Bot } from 'lucide-react';
import { clsx } from 'clsx';
import api from './services/api';

type Tab = 'chat' | 'data';

interface DataSource {
  id: string;
  file_name: string;
  records_ingested?: number;
}

function App() {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [selectedDataSourceId, setSelectedDataSourceId] = useState<string | undefined>();

  // Load data sources on auth
  useEffect(() => {
    if (isAuthenticated) {
      loadDataSources();
    }
  }, [isAuthenticated]);

  const loadDataSources = async () => {
    try {
      const response = await api.get('/api/uploads/history');
      const sources = response.data.uploads || [];
      setDataSources(sources);

      // Auto-select first data source if none selected
      if (sources.length > 0 && !selectedDataSourceId) {
        setSelectedDataSourceId(sources[0].id);
      }
    } catch (error) {
      console.error('Failed to load data sources:', error);
    }
  };

  const handleUploadComplete = () => {
    loadDataSources();
    window.dispatchEvent(new CustomEvent('datasource:refresh'));
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* HEADER */}
      <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
                  Agent Profiler
                </h1>
                <p className="text-xs text-slate-400">AI-Powered Data Analysis</p>
              </div>
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
            <div className="max-w-4xl mx-auto p-4">
              {/* Tabs */}
              <div className="flex gap-1 mb-4 bg-slate-800 p-1 rounded-lg w-fit">
                <button
                  onClick={() => setActiveTab('chat')}
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                    activeTab === 'chat'
                      ? 'bg-primary-600 text-white'
                      : 'text-slate-400 hover:text-white hover:bg-slate-700'
                  )}
                >
                  <MessageSquare className="w-4 h-4" />
                  Chat
                </button>
                <button
                  onClick={() => setActiveTab('data')}
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                    activeTab === 'data'
                      ? 'bg-primary-600 text-white'
                      : 'text-slate-400 hover:text-white hover:bg-slate-700'
                  )}
                >
                  <Database className="w-4 h-4" />
                  Data
                </button>
              </div>

              {/* Data Source Selector (shown on Chat tab) */}
              {activeTab === 'chat' && dataSources.length > 0 && (
                <div className="mb-4 flex items-center gap-2">
                  <span className="text-xs text-slate-400">Analyzing:</span>
                  <select
                    value={selectedDataSourceId || ''}
                    onChange={(e) => setSelectedDataSourceId(e.target.value)}
                    className="bg-slate-800 text-sm text-white border border-slate-700 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    {dataSources.map((ds) => (
                      <option key={ds.id} value={ds.id}>
                        {ds.file_name} ({ds.records_ingested?.toLocaleString() || 0} records)
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Tab Content */}
              {activeTab === 'chat' ? (
                <div className="space-y-4">
                  {dataSources.length === 0 ? (
                    <div className="bg-slate-900 rounded-lg border border-slate-700 p-8 text-center">
                      <Database className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                      <h3 className="text-lg font-semibold text-white mb-2">No Data Sources</h3>
                      <p className="text-slate-400 text-sm mb-4">
                        Upload a CSV file to start analyzing your data.
                      </p>
                      <button
                        onClick={() => setActiveTab('data')}
                        className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm transition-colors"
                      >
                        Go to Data Tab
                      </button>
                    </div>
                  ) : (
                    <ChatInterface dataSourceId={selectedDataSourceId} />
                  )}
                </div>
              ) : (
                <div className="space-y-6">
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
              )}
            </div>
          </ErrorBoundary>
        )}
      </main>
    </div>
  );
}

export default App;
