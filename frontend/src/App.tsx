import { useState } from 'react';
import { Wifi, WifiOff, Radio } from 'lucide-react';
import { AgentNetwork } from './components/AgentNetwork';
import { ChatInterface } from './components/ChatInterface';
import { WorkflowDisplay } from './components/WorkflowDisplay';
import { DataSourceList } from './components/DataSourceList';
import { DataSourceManager } from './components/DataSourceManager';
import { LoginButton } from './components/LoginButton';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useAuth } from './contexts/AuthContext';
import type { TransparencyEvent } from './types';

function App() {
  const [activeAgents, setActiveAgents] = useState<string[]>([]);
  const [currentWorkflow, setCurrentWorkflow] = useState<any>(null);
  const [transparencyEvents, setTransparencyEvents] = useState<TransparencyEvent[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
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
                <div className="flex items-center gap-3">
                  {/* Streaming status indicator */}
                  {isStreaming ? (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-full">
                      <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
                      <span className="text-sm text-emerald-400 font-medium">Live</span>
                    </div>
                  ) : isProcessing ? (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-full">
                      <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                      <span className="text-sm text-amber-400">Processing</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-full">
                      <Wifi className="w-4 h-4 text-emerald-500" />
                      <span className="text-sm text-slate-400">Ready</span>
                    </div>
                  )}
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
          <ErrorBoundary>
            <div className="grid grid-cols-12 gap-4 h-[calc(100vh-120px)]">
              {/* LEFT COLUMN: Chat + Agent Network - 8 cols */}
              <div className="col-span-8 flex flex-col gap-4 min-h-0">
                {/* Chat Interface - takes 60% of left column */}
                <div className="flex-[3] min-h-0">
                  <ErrorBoundary>
                    <ChatInterface
                      onAgentsActive={setActiveAgents}
                      onWorkflowUpdate={setCurrentWorkflow}
                      onTransparencyEvents={setTransparencyEvents}
                      onProcessingChange={setIsProcessing}
                      onStreamingChange={setIsStreaming}
                      onNewChat={() => {
                        setTransparencyEvents([]);
                        setCurrentWorkflow(null);
                        setActiveAgents([]);
                        setIsStreaming(false);
                      }}
                    />
                  </ErrorBoundary>
                </div>

                {/* Agent Network - takes 40% of left column */}
                <div className="flex-[2] min-h-0">
                  <ErrorBoundary>
                    <AgentNetwork
                      activeAgents={activeAgents}
                      transparencyEvents={transparencyEvents}
                      isProcessing={isProcessing}
                      isStreaming={isStreaming}
                    />
                  </ErrorBoundary>
                </div>
              </div>

              {/* RIGHT COLUMN: Data Sources + Workflow - 4 cols */}
              <div className="col-span-4 flex flex-col gap-4 min-h-0">
                {/* Data Sources - takes 35% of right column */}
                <div className="flex-[1] min-h-0 overflow-y-auto">
                  <ErrorBoundary>
                    <DataSourceList onManageClick={() => setShowDataManager(true)} />
                  </ErrorBoundary>
                </div>

                {/* Workflow Details - takes 65% of right column */}
                <div className="flex-[2] min-h-0 overflow-y-auto">
                  <ErrorBoundary>
                    <WorkflowDisplay
                      workflow={currentWorkflow}
                      transparencyEvents={transparencyEvents}
                    />
                  </ErrorBoundary>
                </div>
              </div>
            </div>
          </ErrorBoundary>
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
