import { useState } from 'react';
import { AgentNetwork } from './components/AgentNetwork';
import { ChatInterface } from './components/ChatInterface';
import { WorkflowDisplay } from './components/WorkflowDisplay';
import { DataSourceList } from './components/DataSourceList';
import { DataSourceManager } from './components/DataSourceManager';
import { LoginButton } from './components/LoginButton';
import { useAuth } from './contexts/AuthContext';

function App() {
  const [activeAgents, setActiveAgents] = useState<string[]>([]);
  const [currentWorkflow, setCurrentWorkflow] = useState<any>(null);
  const [showDataManager, setShowDataManager] = useState(false);
  const { isAuthenticated, isLoading } = useAuth();

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
                Agent Profiler
              </h1>
              <p className="text-sm text-slate-400">Multi-Agent AI System for Client Analysis</p>
            </div>
            <div className="flex items-center gap-4">
              {isAuthenticated && (
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                  <span className="text-sm text-slate-400">System Online</span>
                </div>
              )}
              <LoginButton />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-[calc(100vh-120px)]">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-slate-400">Loading...</p>
            </div>
          </div>
        ) : !isAuthenticated ? (
          <div className="flex items-center justify-center h-[calc(100vh-120px)]">
            <div className="text-center max-w-md">
              <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-10 h-10 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Sign in Required</h2>
              <p className="text-slate-400 mb-6">
                Please sign in with your Enterprise Sight Google Workspace account to access the Agent Profiler.
              </p>
              <div className="flex justify-center">
                <LoginButton />
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-12 gap-6 h-[calc(100vh-120px)]">
            {/* Left Panel - Data Sources & Agent Network */}
            <div className="col-span-4 h-full flex flex-col gap-6 overflow-y-auto">
              <DataSourceList onManageClick={() => setShowDataManager(true)} />
              <AgentNetwork activeAgents={activeAgents} />
            </div>

            {/* Center Panel - Chat Interface */}
            <div className="col-span-5 h-full">
              <ChatInterface
                onAgentsActive={setActiveAgents}
                onWorkflowUpdate={setCurrentWorkflow}
              />
            </div>

            {/* Right Panel - Workflow Display */}
            <div className="col-span-3 h-full">
              <WorkflowDisplay workflow={currentWorkflow} />
            </div>
          </div>
        )}
      </main>

      {/* Data Source Manager Modal */}
      <DataSourceManager
        isOpen={showDataManager}
        onClose={() => setShowDataManager(false)}
      />
    </div>
  );
}

export default App;
