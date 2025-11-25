import { useState } from 'react';
import { AgentNetwork } from './components/AgentNetwork';
import { ChatInterface } from './components/ChatInterface';
import { WorkflowDisplay } from './components/WorkflowDisplay';
import { DataSourceList } from './components/DataSourceList';
import { DataSourceManager } from './components/DataSourceManager';

function App() {
  const [activeAgents, setActiveAgents] = useState<string[]>([]);
  const [currentWorkflow, setCurrentWorkflow] = useState<any>(null);
  const [showDataManager, setShowDataManager] = useState(false);

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
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-sm text-slate-400">System Online</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
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
