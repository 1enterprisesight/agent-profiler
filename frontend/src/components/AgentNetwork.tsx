import { useEffect, useState } from 'react';
import type { Agent } from '@/types';

const agents: Agent[] = [
  {
    id: 'orchestrator',
    name: 'Orchestrator',
    type: 'orchestrator',
    description: 'Coordinates multi-agent workflows',
    status: 'idle',
    color: '#8b5cf6',
  },
  {
    id: 'data_ingestion',
    name: 'Data Ingestion',
    type: 'data_ingestion',
    description: 'CSV uploads and CRM sync',
    status: 'idle',
    color: '#10b981',
  },
  {
    id: 'sql_analytics',
    name: 'SQL Analytics',
    type: 'sql_analytics',
    description: 'Quantitative analysis',
    status: 'idle',
    color: '#3b82f6',
  },
  {
    id: 'semantic_search',
    name: 'Semantic Search',
    type: 'semantic_search',
    description: 'Text queries',
    status: 'idle',
    color: '#f59e0b',
  },
  {
    id: 'pattern_recognition',
    name: 'Pattern Recognition',
    type: 'pattern_recognition',
    description: 'Trends and anomalies',
    status: 'idle',
    color: '#ec4899',
  },
  {
    id: 'segmentation',
    name: 'Segmentation',
    type: 'segmentation',
    description: 'Client clustering',
    status: 'idle',
    color: '#14b8a6',
  },
  {
    id: 'benchmark',
    name: 'Benchmark',
    type: 'benchmark',
    description: 'Quality assessment',
    status: 'idle',
    color: '#f97316',
  },
  {
    id: 'recommendation',
    name: 'Recommendation',
    type: 'recommendation',
    description: 'Actionable insights',
    status: 'idle',
    color: '#06b6d4',
  },
];

interface AgentNetworkProps {
  activeAgents?: string[];
}

export function AgentNetwork({ activeAgents = [] }: AgentNetworkProps) {
  const [agentStates, setAgentStates] = useState(agents);

  useEffect(() => {
    setAgentStates(
      agents.map((agent) => ({
        ...agent,
        status: activeAgents.includes(agent.type) ? 'active' : 'idle',
      }))
    );
  }, [activeAgents]);

  return (
    <div className="w-full h-full bg-slate-900 rounded-lg p-6">
      <h2 className="text-xl font-bold text-white mb-6">Agent Network</h2>

      <div className="grid grid-cols-3 gap-6">
        {/* Orchestrator in center top */}
        <div className="col-span-3 flex justify-center">
          <AgentNode agent={agentStates[0]} />
        </div>

        {/* Specialized agents in grid */}
        {agentStates.slice(1).map((agent) => (
          <AgentNode key={agent.id} agent={agent} />
        ))}
      </div>

      {/* Connection lines (simplified) */}
      <svg className="absolute inset-0 pointer-events-none" style={{ zIndex: 0 }}>
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#64748b" />
          </marker>
        </defs>
      </svg>
    </div>
  );
}

function AgentNode({ agent }: { agent: Agent }) {
  const isActive = agent.status === 'active';

  return (
    <div
      className={`
        relative p-4 rounded-lg border-2 transition-all duration-300
        ${isActive ? 'scale-105 shadow-lg' : 'scale-100'}
      `}
      style={{
        backgroundColor: `${agent.color}20`,
        borderColor: agent.color,
        boxShadow: isActive ? `0 0 20px ${agent.color}60` : 'none',
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-3 h-3 rounded-full ${isActive ? 'animate-pulse' : ''}`}
          style={{ backgroundColor: agent.color }}
        />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-white">{agent.name}</h3>
          <p className="text-xs text-slate-400">{agent.description}</p>
        </div>
      </div>

      {isActive && (
        <div className="absolute -top-1 -right-1">
          <span className="flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: agent.color }} />
            <span className="relative inline-flex rounded-full h-3 w-3" style={{ backgroundColor: agent.color }} />
          </span>
        </div>
      )}
    </div>
  );
}
