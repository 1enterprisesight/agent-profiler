import { useEffect, useState, useMemo, useRef } from 'react';
import {
  Inbox,
  Brain,
  ClipboardList,
  Rocket,
  CheckCircle,
  AlertCircle,
  Bot,
} from 'lucide-react';
import type { Agent, AgentVisualState, TransparencyEvent } from '@/types';

// Agent definitions with positions for network layout
// Orchestrator at center, others arranged in a circle around it
const agents: Agent[] = [
  {
    id: 'orchestrator',
    name: 'Orchestrator',
    type: 'orchestrator',
    description: 'Coordinates workflows',
    status: 'idle',
    color: '#8b5cf6', // violet
  },
  {
    id: 'sql_analytics',
    name: 'SQL Analytics',
    type: 'sql_analytics',
    description: 'Quantitative analysis',
    status: 'idle',
    color: '#3b82f6', // blue
  },
  {
    id: 'semantic_search',
    name: 'Search',
    type: 'semantic_search',
    description: 'Text queries',
    status: 'idle',
    color: '#84cc16', // lime
  },
  {
    id: 'data_discovery',
    name: 'Discovery',
    type: 'data_discovery' as any,
    description: 'Schema & metadata',
    status: 'idle',
    color: '#a855f7', // purple
  },
  {
    id: 'segmentation',
    name: 'Segmentation',
    type: 'segmentation',
    description: 'Client clustering',
    status: 'idle',
    color: '#10b981', // emerald
  },
  {
    id: 'pattern_recognition',
    name: 'Pattern',
    type: 'pattern_recognition',
    description: 'Trends & anomalies',
    status: 'idle',
    color: '#f59e0b', // amber
  },
  {
    id: 'benchmark',
    name: 'Benchmark',
    type: 'benchmark',
    description: 'Quality scoring',
    status: 'idle',
    color: '#ec4899', // pink
  },
  {
    id: 'recommendation',
    name: 'Recommend',
    type: 'recommendation',
    description: 'Action insights',
    status: 'idle',
    color: '#06b6d4', // cyan
  },
  {
    id: 'data_ingestion',
    name: 'Ingestion',
    type: 'data_ingestion',
    description: 'Data import',
    status: 'idle',
    color: '#f97316', // orange
  },
];

// Map event types to visual states
function eventTypeToVisualState(eventType: string): AgentVisualState {
  switch (eventType) {
    case 'received':
      return 'receiving';
    case 'thinking':
      return 'thinking';
    case 'decision':
    case 'action':
      return 'acting';
    case 'result':
      return 'complete';
    case 'error':
      return 'error';
    default:
      return 'idle';
  }
}

// Event type icons - returns lucide-react icon components
const EventIcon = ({ type, color }: { type: string; color: string }) => {
  const iconProps = { className: 'w-5 h-5', style: { color } };
  switch (type) {
    case 'received':
      return <Inbox {...iconProps} />;
    case 'thinking':
      return <Brain {...iconProps} />;
    case 'decision':
      return <ClipboardList {...iconProps} />;
    case 'action':
      return <Rocket {...iconProps} />;
    case 'result':
      return <CheckCircle {...iconProps} />;
    case 'error':
      return <AlertCircle {...iconProps} />;
    default:
      return null;
  }
};

interface AgentNetworkProps {
  activeAgents?: string[];
  transparencyEvents?: TransparencyEvent[];
  isProcessing?: boolean;
  isStreaming?: boolean;
}

export function AgentNetwork({
  activeAgents = [],
  transparencyEvents = [],
  isProcessing = false,
  isStreaming: _isStreaming = false,
}: AgentNetworkProps) {
  // Note: _isStreaming reserved for enhanced streaming animations
  const [agentStates, setAgentStates] = useState<(Agent & { visualState: AgentVisualState; currentEvent?: TransparencyEvent })[]>(
    agents.map(a => ({ ...a, visualState: 'idle' as AgentVisualState }))
  );

  // Compute active connections for data flow visualization
  const activeConnections = useMemo(() => {
    const connections: { from: string; to: string }[] = [];
    if (activeAgents.includes('orchestrator')) {
      activeAgents.forEach(agent => {
        if (agent !== 'orchestrator') {
          connections.push({ from: 'orchestrator', to: agent });
        }
      });
    }
    return connections;
  }, [activeAgents]);

  // Update agent states based on transparency events
  useEffect(() => {
    const latestEventByAgent: Record<string, TransparencyEvent> = {};

    // Get the latest event for each agent
    transparencyEvents.forEach(event => {
      const existing = latestEventByAgent[event.agent_name];
      if (!existing || new Date(event.created_at) > new Date(existing.created_at)) {
        latestEventByAgent[event.agent_name] = event;
      }
    });

    setAgentStates(
      agents.map((agent) => {
        const latestEvent = latestEventByAgent[agent.type];
        let visualState: AgentVisualState = 'idle';

        if (isProcessing && activeAgents.includes(agent.type)) {
          // If currently processing and this agent is active
          visualState = latestEvent ? eventTypeToVisualState(latestEvent.event_type) : 'receiving';
        } else if (latestEvent && activeAgents.includes(agent.type)) {
          visualState = eventTypeToVisualState(latestEvent.event_type);
        }

        return {
          ...agent,
          visualState,
          currentEvent: latestEvent,
        };
      })
    );
  }, [activeAgents, transparencyEvents, isProcessing]);

  // Calculate positions for circular layout
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 300 });

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width, height: rect.height - 60 }); // Account for header
      }
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Calculate node positions - orchestrator in center, others in a circle
  const nodePositions = useMemo(() => {
    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;
    const radius = Math.min(dimensions.width, dimensions.height) * 0.35;

    const positions: Record<string, { x: number; y: number }> = {
      orchestrator: { x: centerX, y: centerY }
    };

    // Position other agents in a circle around orchestrator
    const otherAgents = agents.filter(a => a.id !== 'orchestrator');
    otherAgents.forEach((agent, idx) => {
      const angle = (idx / otherAgents.length) * 2 * Math.PI - Math.PI / 2;
      positions[agent.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      };
    });

    return positions;
  }, [dimensions]);

  return (
    <div ref={containerRef} className="w-full h-full bg-slate-900 rounded-lg relative overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white">Agent Network</h2>
          {isProcessing && (
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
              <span className="text-sm text-slate-400">Processing...</span>
            </div>
          )}
        </div>
      </div>

      {/* Network Visualization */}
      <div className="relative" style={{ height: dimensions.height }}>
        {/* SVG for connection lines */}
        <svg className="absolute inset-0 pointer-events-none" width="100%" height="100%">
          <defs>
            {/* Gradient for active flow */}
            <linearGradient id="activeFlow" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.2" />
              <stop offset="50%" stopColor="#8b5cf6" stopOpacity="1" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.2" />
            </linearGradient>
            {/* Glow filter */}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
            {/* Animated dash pattern */}
            <pattern id="flowPattern" width="20" height="1" patternUnits="userSpaceOnUse">
              <rect width="10" height="1" fill="#8b5cf6" />
            </pattern>
          </defs>

          {/* Draw all connection lines from orchestrator to each agent */}
          {agents.filter(a => a.id !== 'orchestrator').map((agent) => {
            const isActive = activeConnections.some(c => c.to === agent.id);
            const startPos = nodePositions['orchestrator'];
            const endPos = nodePositions[agent.id];

            if (!startPos || !endPos) return null;

            return (
              <g key={`line-${agent.id}`}>
                {/* Base line (always visible, dimmed) */}
                <line
                  x1={startPos.x}
                  y1={startPos.y}
                  x2={endPos.x}
                  y2={endPos.y}
                  stroke={agent.color}
                  strokeWidth="1"
                  strokeOpacity="0.15"
                />
                {/* Active line with animation */}
                {isActive && (
                  <>
                    <line
                      x1={startPos.x}
                      y1={startPos.y}
                      x2={endPos.x}
                      y2={endPos.y}
                      stroke={agent.color}
                      strokeWidth="2"
                      strokeOpacity="0.8"
                      filter="url(#glow)"
                    />
                    {/* Animated particle along line */}
                    <circle r="4" fill={agent.color} filter="url(#glow)">
                      <animateMotion
                        dur="1s"
                        repeatCount="indefinite"
                        path={`M${startPos.x},${startPos.y} L${endPos.x},${endPos.y}`}
                      />
                    </circle>
                  </>
                )}
              </g>
            );
          })}
        </svg>

        {/* Agent Nodes */}
        {agentStates.map((agent) => {
          const pos = nodePositions[agent.id];
          if (!pos) return null;

          const isOrchestrator = agent.id === 'orchestrator';
          const nodeSize = isOrchestrator ? 80 : 60;

          return (
            <div
              key={agent.id}
              className="absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-300"
              style={{ left: pos.x, top: pos.y }}
            >
              <NetworkNode
                agent={agent}
                size={nodeSize}
                isOrchestrator={isOrchestrator}
              />
            </div>
          );
        })}
      </div>

      {/* CSS Animations */}
      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 1; }
          100% { transform: scale(1.5); opacity: 0; }
        }
        @keyframes thinking-pulse {
          0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 var(--agent-color); }
          50% { transform: scale(1.05); box-shadow: 0 0 20px var(--agent-color); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// Compact circular node for network visualization
function NetworkNode({
  agent,
  size,
  isOrchestrator
}: {
  agent: Agent & { visualState: AgentVisualState; currentEvent?: TransparencyEvent };
  size: number;
  isOrchestrator: boolean;
}) {
  const { visualState, currentEvent } = agent;
  const isActive = visualState !== 'idle';

  // Get status color
  const getStatusColor = () => {
    switch (visualState) {
      case 'error': return '#ef4444';
      case 'complete': return '#22c55e';
      default: return agent.color;
    }
  };

  return (
    <div
      className="relative flex flex-col items-center"
      style={{ '--agent-color': agent.color } as React.CSSProperties}
    >
      {/* Outer glow ring for active state */}
      {isActive && (
        <div
          className="absolute rounded-full"
          style={{
            width: size + 16,
            height: size + 16,
            top: -8,
            left: '50%',
            transform: 'translateX(-50%)',
            background: `radial-gradient(circle, ${agent.color}40 0%, transparent 70%)`,
            animation: visualState === 'thinking' ? 'thinking-pulse 1.5s ease-in-out infinite' : undefined,
          }}
        />
      )}

      {/* Spinning ring for acting state */}
      {visualState === 'acting' && (
        <div
          className="absolute rounded-full border-2 border-transparent"
          style={{
            width: size + 8,
            height: size + 8,
            top: -4,
            left: '50%',
            transform: 'translateX(-50%)',
            borderTopColor: agent.color,
            borderRightColor: agent.color,
            animation: 'spin 1s linear infinite',
          }}
        />
      )}

      {/* Main node circle */}
      <div
        className={`
          rounded-full flex items-center justify-center
          transition-all duration-300 cursor-pointer
          ${isActive ? 'scale-110' : 'scale-100 hover:scale-105'}
        `}
        style={{
          width: size,
          height: size,
          backgroundColor: isActive ? `${agent.color}40` : `${agent.color}20`,
          border: `2px solid ${isActive ? agent.color : `${agent.color}60`}`,
          boxShadow: isActive ? `0 0 20px ${agent.color}60` : 'none',
        }}
      >
        {/* Event icon or agent initial */}
        <span className="flex items-center justify-center">
          {currentEvent && isActive ? (
            <EventIcon type={currentEvent.event_type} color={agent.color} />
          ) : isOrchestrator ? (
            <Bot className="w-6 h-6" style={{ color: agent.color }} />
          ) : (
            <span
              className="font-bold"
              style={{ color: agent.color, fontSize: '1rem' }}
            >
              {agent.name.charAt(0)}
            </span>
          )}
        </span>
      </div>

      {/* Status indicator dot */}
      <div
        className={`absolute rounded-full ${isActive && visualState !== 'complete' && visualState !== 'error' ? 'animate-pulse' : ''}`}
        style={{
          width: 10,
          height: 10,
          top: 0,
          right: isOrchestrator ? '25%' : '15%',
          backgroundColor: getStatusColor(),
          border: '2px solid #1e293b',
        }}
      />

      {/* Agent name label */}
      <div
        className="mt-2 text-center"
        style={{ maxWidth: size + 20 }}
      >
        <p
          className={`text-xs font-medium truncate ${isActive ? 'text-white' : 'text-slate-400'}`}
        >
          {agent.name}
        </p>
        {/* Show current action when active */}
        {currentEvent && isActive && (
          <p className="text-xs text-slate-500 truncate mt-0.5" style={{ maxWidth: size + 40 }}>
            {currentEvent.title.length > 20 ? currentEvent.title.slice(0, 20) + '...' : currentEvent.title}
          </p>
        )}
      </div>

      {/* Complete checkmark */}
      {visualState === 'complete' && (
        <div
          className="absolute flex items-center justify-center rounded-full bg-green-500 text-white text-xs font-bold"
          style={{
            width: 18,
            height: 18,
            top: -4,
            right: isOrchestrator ? '20%' : '10%',
          }}
        >
          ✓
        </div>
      )}

      {/* Error indicator */}
      {visualState === 'error' && (
        <div
          className="absolute flex items-center justify-center rounded-full bg-red-500 text-white text-xs font-bold"
          style={{
            width: 18,
            height: 18,
            top: -4,
            right: isOrchestrator ? '20%' : '10%',
          }}
        >
          !
        </div>
      )}
    </div>
  );
}
