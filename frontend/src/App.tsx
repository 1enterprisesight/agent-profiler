import { useState } from 'react';
import { Wifi, Radio } from 'lucide-react';
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
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* HEADER - Sticky at top */}
      <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
        <div className="max-w-[1800px] mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
                Agent Profiler
              </h1>
              <p className="text-xs text-slate-400">Multi-Agent AI System</p>
            </div>
            <div className="flex items-center gap-4">
              {isAuthenticated && (
                <div className="flex items-center gap-3">
                  {isStreaming ? (
                    <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-full">
                      <Radio className="w-3 h-3 text-emerald-400 animate-pulse" />
                      <span className="text-xs text-emerald-400 font-medium">Live</span>
                    </div>
                  ) : isProcessing ? (
                    <div className="flex items-center gap-2 px-3 py-1 bg-amber-500/10 border border-amber-500/30 rounded-full">
                      <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                      <span className="text-xs text-amber-400">Processing</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 px-3 py-1 bg-slate-800 border border-slate-700 rounded-full">
                      <Wifi className="w-3 h-3 text-emerald-500" />
                      <span className="text-xs text-slate-400">Ready</span>
                    </div>
                  )}
                </div>
              )}
              <LoginButton />
            </div>
          </div>
        </div>
      </header>

      {/* MAIN CONTENT - Scrollable */}
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
            {/* HERO: Agent Network - Full width, prominent at top */}
            <section className="border-b border-slate-800 bg-slate-900/30">
              <div className="max-w-[1800px] mx-auto p-4">
                <div className="h-[350px] lg:h-[400px]">
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
            </section>

            {/* CONTENT: Chat + Sidebar - Natural heights, page scrolls */}
            <section className="max-w-[1800px] mx-auto p-4">
              <div className="flex flex-col lg:flex-row gap-4">
                {/* Chat Interface - Main column */}
                <div className="flex-1 min-w-0">
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

                {/* Sidebar: Data Sources + Workflow */}
                <aside className="lg:w-[380px] flex-shrink-0 flex flex-col gap-4">
                  {/* Data Sources - Collapsible */}
                  <ErrorBoundary>
                    <DataSourceList onManageClick={() => setShowDataManager(true)} />
                  </ErrorBoundary>

                  {/* Workflow Display - Scrollable */}
                  <div className="flex-1 min-h-[400px] max-h-[600px] overflow-y-auto">
                    <ErrorBoundary>
                      <WorkflowDisplay
                        workflow={currentWorkflow}
                        transparencyEvents={transparencyEvents}
                      />
                    </ErrorBoundary>
                  </div>
                </aside>
              </div>
            </section>
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
