/**
 * Agent Network Diagram Component
 *
 * Visualizes the agent workflow and data flow:
 * - Shows Conversation Manager -> Orchestrator -> Agents -> Results
 * - Displays real-time status of each agent
 * - Highlights active agents and data flow with animations
 * - Dynamically shows agents based on orchestrator decisions
 */

import { Brain, Search, BarChart3, Lightbulb, MessageSquare, CheckCircle2, AlertCircle, Clock, Zap } from 'lucide-react';
import { clsx } from 'clsx';
import type { AgentActivity } from '../hooks/useChat';

// Internal status type for visualization
type AgentStatus = 'IDLE' | 'THINKING' | 'WORKING' | 'COMPLETED' | 'FAILED';

interface AgentNetworkDiagramProps {
  isProcessing: boolean;
  agentActivities: AgentActivity[];
  currentStep?: string;
}

interface AgentNode {
  id: string;
  name: string;
  displayName: string;
  icon: typeof Brain;
  color: string;
  description: string;
  position: { x: number; y: number };
}

// Core agent nodes - horizontal flow layout
const CORE_NODES: AgentNode[] = [
  {
    id: 'conversation',
    name: 'conversation_manager',
    displayName: 'Conversation',
    icon: MessageSquare,
    color: 'from-purple-500 to-purple-600',
    description: 'User Query',
    position: { x: 12, y: 50 },
  },
  {
    id: 'orchestrator',
    name: 'orchestrator',
    displayName: 'Orchestrator',
    icon: Brain,
    color: 'from-blue-500 to-blue-600',
    description: 'Query Routing',
    position: { x: 35, y: 50 },
  },
  {
    id: 'results',
    name: 'results',
    displayName: 'Results',
    icon: Lightbulb,
    color: 'from-yellow-500 to-yellow-600',
    description: 'Final Output',
    position: { x: 88, y: 50 },
  },
];

// Dynamic agent nodes - shown when invoked
const AGENT_NODES: Record<string, Omit<AgentNode, 'position'>> = {
  sql_analytics: {
    id: 'quantitative',
    name: 'sql_analytics',
    displayName: 'Quantitative',
    icon: BarChart3,
    color: 'from-green-500 to-green-600',
    description: 'SQL Analytics',
  },
  semantic_search: {
    id: 'semantic',
    name: 'semantic_search',
    displayName: 'Semantic',
    icon: Search,
    color: 'from-orange-500 to-orange-600',
    description: 'Text Search',
  },
};

export function AgentNetworkDiagram({
  isProcessing,
  agentActivities,
  currentStep
}: AgentNetworkDiagramProps) {

  // Determine which agents were invoked
  const invokedAgents = agentActivities.map(a => a.agent);

  // Build the dynamic node list
  const getAgentNodes = (): AgentNode[] => {
    const nodes: AgentNode[] = [...CORE_NODES];

    // Add invoked agents with dynamic positioning between orchestrator and results
    const agentCount = invokedAgents.length;
    invokedAgents.forEach((agentName, index) => {
      const agentConfig = AGENT_NODES[agentName];
      if (agentConfig) {
        // Position agents vertically spread between orchestrator (x=35) and results (x=88)
        // Single agent at center (y=50), multiple agents spread vertically
        const yOffset = agentCount === 1 ? 50 : 25 + (index * 50 / Math.max(agentCount - 1, 1));
        nodes.push({
          ...agentConfig,
          position: { x: 60, y: yOffset },
        });
      }
    });

    return nodes;
  };

  const allNodes = getAgentNodes();

  // Get status for an agent
  const getAgentStatus = (agentName: string): AgentStatus => {
    if (agentName === 'conversation_manager') {
      return agentActivities.length > 0 || isProcessing ? 'COMPLETED' : 'IDLE';
    }
    if (agentName === 'orchestrator') {
      if (!isProcessing && agentActivities.length > 0) return 'COMPLETED';
      if (isProcessing && currentStep?.includes('interpret')) return 'THINKING';
      if (isProcessing && currentStep?.includes('route')) return 'WORKING';
      if (isProcessing) return 'WORKING';
      return 'IDLE';
    }
    if (agentName === 'results') {
      if (!isProcessing && agentActivities.length > 0) return 'COMPLETED';
      if (isProcessing && currentStep?.includes('synth')) return 'WORKING';
      return 'IDLE';
    }

    const activity = agentActivities.find(a => a.agent === agentName);
    if (activity) {
      if (activity.result?.error) return 'FAILED';
      if (activity.result) return 'COMPLETED';
      return 'WORKING';
    }
    return 'IDLE';
  };

  // Get status badge icon
  const getStatusBadge = (status: AgentStatus) => {
    switch (status) {
      case 'THINKING':
        return <Clock className="h-3 w-3 text-blue-400 animate-pulse" />;
      case 'WORKING':
        return <Zap className="h-3 w-3 text-yellow-400 animate-bounce" />;
      case 'COMPLETED':
        return <CheckCircle2 className="h-3 w-3 text-green-400" />;
      case 'FAILED':
        return <AlertCircle className="h-3 w-3 text-red-400" />;
      default:
        return null;
    }
  };

  // Check if connection should be animated
  const isConnectionActive = (fromId: string, toId: string): boolean => {
    const fromStatus = getAgentStatus(
      allNodes.find(n => n.id === fromId)?.name || ''
    );
    const toStatus = getAgentStatus(
      allNodes.find(n => n.id === toId)?.name || ''
    );

    return (
      (fromStatus === 'COMPLETED' || fromStatus === 'WORKING') &&
      (toStatus === 'WORKING' || toStatus === 'THINKING' || toStatus === 'COMPLETED')
    );
  };

  // Build connections dynamically
  const getConnections = () => {
    const connections: { from: string; to: string }[] = [
      { from: 'conversation', to: 'orchestrator' },
    ];

    // Connect orchestrator to each invoked agent
    invokedAgents.forEach(agentName => {
      const agentConfig = AGENT_NODES[agentName];
      if (agentConfig) {
        connections.push({ from: 'orchestrator', to: agentConfig.id });
        connections.push({ from: agentConfig.id, to: 'results' });
      }
    });

    // If no agents invoked but completed, connect directly
    if (invokedAgents.length === 0 && !isProcessing && agentActivities.length === 0) {
      // Show idle state - no connections highlighted
    } else if (invokedAgents.length === 0) {
      connections.push({ from: 'orchestrator', to: 'results' });
    }

    return connections;
  };

  const connections = getConnections();

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary-400" />
          Agent Network
        </h3>
        <p className="text-xs text-slate-400">
          {isProcessing ? 'Processing your request...' : 'Real-time agent coordination'}
        </p>
      </div>

      <div
        className="relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-lg"
        style={{ minHeight: '160px' }}
      >
        {/* SVG for connections */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 1 }}
        >
          <defs>
            <linearGradient id="activeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="1" />
            </linearGradient>
            <marker
              id="arrowActive"
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="3"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path d="M0,0 L0,6 L8,3 z" fill="#3b82f6" />
            </marker>
            <marker
              id="arrowInactive"
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="3"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path d="M0,0 L0,6 L8,3 z" fill="#475569" />
            </marker>
          </defs>

          {connections.map((conn, idx) => {
            const fromNode = allNodes.find(n => n.id === conn.from);
            const toNode = allNodes.find(n => n.id === conn.to);
            if (!fromNode || !toNode) return null;

            const isActive = isConnectionActive(conn.from, conn.to);
            // Horizontal flow - adjust x for arrow spacing
            const x1 = `${fromNode.position.x + 5}%`;
            const y1 = `${fromNode.position.y}%`;
            const x2 = `${toNode.position.x - 5}%`;
            const y2 = `${toNode.position.y}%`;

            return (
              <line
                key={idx}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={isActive ? '#3b82f6' : '#475569'}
                strokeWidth={isActive ? '2' : '1'}
                strokeDasharray={isActive ? '' : '4 4'}
                markerEnd={isActive ? 'url(#arrowActive)' : 'url(#arrowInactive)'}
                className={isActive ? 'animate-pulse' : ''}
              />
            );
          })}
        </svg>

        {/* Agent nodes */}
        {allNodes.map((node) => {
          const status = getAgentStatus(node.name);
          const Icon = node.icon;
          const isActive = status === 'WORKING' || status === 'THINKING';
          const isCompleted = status === 'COMPLETED';
          const isFailed = status === 'FAILED';
          const activity = agentActivities.find(a => a.agent === node.name);

          return (
            <div
              key={node.id}
              className="absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-300"
              style={{
                left: `${node.position.x}%`,
                top: `${node.position.y}%`,
                zIndex: 10,
              }}
            >
              <div className={clsx(
                'flex flex-col items-center',
                isActive && 'scale-110'
              )}>
                {/* Icon circle */}
                <div className={clsx(
                  'relative w-12 h-12 rounded-full shadow-lg flex items-center justify-center bg-gradient-to-br transition-all duration-300',
                  node.color,
                  isActive && 'ring-2 ring-blue-400 ring-opacity-50 animate-pulse',
                  isCompleted && 'ring-2 ring-green-400 ring-opacity-50',
                  isFailed && 'ring-2 ring-red-400 ring-opacity-50',
                  status === 'IDLE' && 'opacity-40 grayscale'
                )}>
                  <Icon className="h-6 w-6 text-white" />

                  {/* Status badge */}
                  {status !== 'IDLE' && (
                    <div className="absolute -top-1 -right-1 bg-slate-800 rounded-full p-1 shadow border border-slate-600">
                      {getStatusBadge(status)}
                    </div>
                  )}
                </div>

                {/* Label */}
                <div className="mt-1 text-center max-w-[100px]">
                  <div className="text-xs font-medium text-white truncate">
                    {node.displayName}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">
                    {node.description}
                  </div>

                  {/* Task preview for active agents */}
                  {activity && status !== 'IDLE' && (
                    <div className="mt-1 text-[9px] text-slate-500 bg-slate-800/80 rounded px-1.5 py-0.5 max-w-[120px] truncate">
                      {activity.task.slice(0, 30)}...
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-3 flex items-center justify-center gap-4 text-[10px] text-slate-400">
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3 text-blue-400" />
          <span>Thinking</span>
        </div>
        <div className="flex items-center gap-1">
          <Zap className="h-3 w-3 text-yellow-400" />
          <span>Working</span>
        </div>
        <div className="flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3 text-green-400" />
          <span>Done</span>
        </div>
        <div className="flex items-center gap-1">
          <AlertCircle className="h-3 w-3 text-red-400" />
          <span>Error</span>
        </div>
      </div>
    </div>
  );
}
