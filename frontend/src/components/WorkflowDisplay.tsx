import { useState, useMemo } from 'react';
import { CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import type { WorkflowStep, TransparencyEvent, EventType } from '@/types';

// Event type configuration
const eventConfig: Record<EventType, { icon: string; color: string; label: string }> = {
  received: { icon: '📥', color: 'text-blue-400', label: 'Received' },
  thinking: { icon: '🤔', color: 'text-amber-400', label: 'Thinking' },
  decision: { icon: '📋', color: 'text-purple-400', label: 'Decision' },
  action: { icon: '🚀', color: 'text-cyan-400', label: 'Action' },
  result: { icon: '✅', color: 'text-green-400', label: 'Result' },
  error: { icon: '❌', color: 'text-red-400', label: 'Error' },
};

// Agent color mapping
const agentColors: Record<string, string> = {
  orchestrator: '#8b5cf6',
  data_ingestion: '#10b981',
  sql_analytics: '#3b82f6',
  semantic_search: '#84cc16',
  pattern_recognition: '#f59e0b',
  segmentation: '#10b981',
  benchmark: '#ec4899',
  recommendation: '#06b6d4',
};

interface WorkflowDisplayProps {
  workflow: any;
  transparencyEvents?: TransparencyEvent[];
}

export function WorkflowDisplay({ workflow, transparencyEvents = [] }: WorkflowDisplayProps) {
  // Group events by agent
  const eventsByAgent = useMemo(() => {
    const grouped: Record<string, TransparencyEvent[]> = {};

    transparencyEvents.forEach(event => {
      if (!grouped[event.agent_name]) {
        grouped[event.agent_name] = [];
      }
      grouped[event.agent_name].push(event);
    });

    // Sort events within each agent by step_number and created_at
    Object.keys(grouped).forEach(agent => {
      grouped[agent].sort((a, b) => {
        if (a.step_number !== b.step_number) {
          return (a.step_number || 0) - (b.step_number || 0);
        }
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      });
    });

    return grouped;
  }, [transparencyEvents]);

  // Calculate total duration and per-agent durations
  const { totalDuration, agentDurations } = useMemo(() => {
    if (transparencyEvents.length === 0) return { totalDuration: 0, agentDurations: {} };

    const durations: Record<string, number> = {};
    let total = 0;

    transparencyEvents.forEach(event => {
      if (event.duration_ms) {
        total += event.duration_ms;
        durations[event.agent_name] = (durations[event.agent_name] || 0) + event.duration_ms;
      }
    });

    // If no explicit durations, estimate from timestamps
    if (total === 0 && transparencyEvents.length > 1) {
      const sorted = [...transparencyEvents].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
      const start = new Date(sorted[0].created_at).getTime();
      const end = new Date(sorted[sorted.length - 1].created_at).getTime();
      total = end - start;
    }

    return { totalDuration: total, agentDurations: durations };
  }, [transparencyEvents]);


  // Order agents by first event timestamp
  const orderedAgents = useMemo(() => {
    const agentFirstEvent: Record<string, Date> = {};
    transparencyEvents.forEach(event => {
      const eventTime = new Date(event.created_at);
      if (!agentFirstEvent[event.agent_name] || eventTime < agentFirstEvent[event.agent_name]) {
        agentFirstEvent[event.agent_name] = eventTime;
      }
    });
    return Object.keys(eventsByAgent).sort((a, b) =>
      (agentFirstEvent[a]?.getTime() || 0) - (agentFirstEvent[b]?.getTime() || 0)
    );
  }, [eventsByAgent, transparencyEvents]);

  if (transparencyEvents.length === 0 && (!workflow || !workflow.workflow_results)) {
    return (
      <div className="w-full h-full bg-slate-800 rounded-lg p-6 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-400 mb-2">No active workflow</p>
          <p className="text-slate-500 text-sm">Transparency events will appear here</p>
        </div>
      </div>
    );
  }

  // If we have transparency events, show the new UI
  if (transparencyEvents.length > 0) {
    return (
      <div className="w-full h-full bg-slate-800 rounded-lg flex flex-col overflow-hidden">
        {/* Header with total time */}
        <div className="p-4 border-b border-slate-700 flex-shrink-0">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Workflow Details</h2>
            {totalDuration > 0 && (
              <div className="flex items-center gap-2 px-3 py-1 bg-slate-700 rounded-full">
                <Clock className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-medium text-white">
                  {totalDuration >= 1000
                    ? `${(totalDuration / 1000).toFixed(1)}s`
                    : `${totalDuration}ms`}
                </span>
              </div>
            )}
          </div>
          {/* Summary stats */}
          <div className="flex gap-4 mt-3 text-xs text-slate-400">
            <span>{orderedAgents.length} agents</span>
            <span>{transparencyEvents.length} events</span>
          </div>
        </div>

        {/* Agent events list */}
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {orderedAgents.map((agentName) => (
            <AgentEventGroup
              key={agentName}
              agentName={agentName}
              events={eventsByAgent[agentName]}
              color={agentColors[agentName] || '#6b7280'}
              duration={agentDurations[agentName]}
            />
          ))}
        </div>

        {/* Footer with timing breakdown */}
        {orderedAgents.length > 1 && totalDuration > 0 && (
          <div className="p-4 border-t border-slate-700 flex-shrink-0 bg-slate-900/50">
            <div className="text-xs text-slate-400 mb-2">Time by Agent</div>
            <div className="flex flex-wrap gap-2">
              {orderedAgents.map((agentName) => {
                const duration = agentDurations[agentName] || 0;
                return (
                  <div
                    key={agentName}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs"
                    style={{ backgroundColor: `${agentColors[agentName]}20` }}
                  >
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: agentColors[agentName] }}
                    />
                    <span className="text-slate-300">
                      {agentName.split('_').map(w => w[0].toUpperCase()).join('')}
                    </span>
                    <span className="text-slate-500">
                      {duration >= 1000 ? `${(duration / 1000).toFixed(1)}s` : `${duration}ms`}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Fallback to legacy workflow display
  const steps = workflow?.workflow_results || [];
  const totalSteps = steps.length;
  const successfulSteps = steps.filter((s: WorkflowStep) => s.success).length;

  return (
    <div className="w-full h-full bg-slate-800 rounded-lg p-6 overflow-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-white">Workflow Execution</h2>
        <div className="text-sm text-slate-400">
          {successfulSteps} / {totalSteps} steps completed
        </div>
      </div>

      <div className="space-y-3">
        {steps.map((step: WorkflowStep, index: number) => (
          <WorkflowStepCard key={index} step={step} />
        ))}
      </div>

      {workflow?.execution_plan?.rationale && (
        <div className="mt-6 pt-6 border-t border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-2">Execution Plan</h3>
          <p className="text-sm text-slate-400">{workflow.execution_plan.rationale}</p>
        </div>
      )}
    </div>
  );
}

interface AgentEventGroupProps {
  agentName: string;
  events: TransparencyEvent[];
  color: string;
  duration?: number;
}

function AgentEventGroup({ agentName, events, color, duration }: AgentEventGroupProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Get last event for summary
  const lastEvent = events[events.length - 1];
  const hasError = events.some(e => e.event_type === 'error');
  const isComplete = lastEvent?.event_type === 'result';

  // Use provided duration or calculate from events
  const agentDuration = duration ?? events
    .filter(e => e.duration_ms)
    .reduce((sum, e) => sum + (e.duration_ms || 0), 0);

  // Format agent name for display
  const displayName = agentName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

  return (
    <div
      className="rounded-lg border-2 overflow-hidden transition-all duration-200"
      style={{
        borderColor: hasError ? '#ef4444' : isComplete ? '#22c55e' : `${color}60`,
        backgroundColor: `${color}10`,
      }}
    >
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          {/* Status indicator */}
          <div
            className="w-3 h-3 rounded-full"
            style={{
              backgroundColor: hasError ? '#ef4444' : isComplete ? '#22c55e' : color
            }}
          />

          {/* Agent name */}
          <span className="font-semibold text-white">{displayName}</span>

          {/* Event count badge */}
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
            {events.length} events
          </span>
        </div>

        <div className="flex items-center gap-4">
          {/* Duration */}
          {agentDuration > 0 && (
            <span className="text-xs text-slate-400">
              {agentDuration}ms
            </span>
          )}

          {/* Status icons */}
          {hasError && <XCircle className="w-5 h-5 text-red-500" />}
          {isComplete && !hasError && <CheckCircle2 className="w-5 h-5 text-green-500" />}

          {/* Expand/collapse icon */}
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-slate-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-slate-400" />
          )}
        </div>
      </button>

      {/* Summary view - shown when collapsed */}
      {!isExpanded && (
        <div className="px-4 pb-4 space-y-1">
          {events.map((event, idx) => (
            <EventSummary key={event.id || idx} event={event} />
          ))}
        </div>
      )}

      {/* Expanded view - detailed events */}
      {isExpanded && (
        <div className="border-t border-slate-700">
          {events.map((event, idx) => (
            <EventDetail key={event.id || idx} event={event} isLast={idx === events.length - 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function EventSummary({ event }: { event: TransparencyEvent }) {
  const config = eventConfig[event.event_type];

  return (
    <div className="flex items-center gap-2 text-sm">
      <span>{config.icon}</span>
      <span className={`${config.color} truncate`}>{event.title}</span>
    </div>
  );
}

function EventDetail({ event, isLast }: { event: TransparencyEvent; isLast: boolean }) {
  const [showDetails, setShowDetails] = useState(false);
  const config = eventConfig[event.event_type];
  const hasDetails = event.details && Object.keys(event.details).length > 0;

  return (
    <div className={`p-4 ${!isLast ? 'border-b border-slate-700' : ''}`}>
      {/* Event header */}
      <div className="flex items-start gap-3">
        <span className="text-lg">{config.icon}</span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-sm font-medium ${config.color}`}>
              {config.label}
            </span>
            {event.duration_ms && (
              <span className="text-xs text-slate-500">
                ({event.duration_ms}ms)
              </span>
            )}
          </div>

          <p className="text-sm text-slate-200">{event.title}</p>

          {/* Timestamp */}
          <p className="text-xs text-slate-500 mt-1">
            {new Date(event.created_at).toLocaleTimeString()}
          </p>
        </div>

        {/* Show details button */}
        {hasDetails && (
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            {showDetails ? 'Hide' : 'Details'}
          </button>
        )}
      </div>

      {/* Expandable details */}
      {showDetails && hasDetails && (
        <div className="mt-3 ml-8 p-3 bg-slate-900 rounded-lg">
          <pre className="text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(event.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// Legacy component for backward compatibility
function WorkflowStepCard({ step }: { step: WorkflowStep }) {
  return (
    <div className={`p-4 rounded-lg border-2 ${
      step.success
        ? 'bg-emerald-900/20 border-emerald-500'
        : 'bg-red-900/20 border-red-500'
    }`}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {step.success ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          ) : (
            <XCircle className="w-5 h-5 text-red-500" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-slate-400">
              Step {step.step_number}
            </span>
            <span className="text-sm font-medium text-white">{step.agent}</span>
          </div>

          <p className="text-sm text-slate-300 mb-2">{step.action}</p>

          {step.error && (
            <p className="text-sm text-red-400 mt-2">{step.error}</p>
          )}

          {step.duration_ms && (
            <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
              <Clock className="w-3 h-3" />
              <span>{step.duration_ms}ms</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
