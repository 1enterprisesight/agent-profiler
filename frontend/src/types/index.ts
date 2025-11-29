export interface Agent {
  id: string;
  name: string;
  type: 'orchestrator' | 'data_ingestion' | 'sql_analytics' | 'semantic_search' |
        'pattern_recognition' | 'segmentation' | 'benchmark' | 'recommendation';
  description: string;
  status: 'idle' | 'active' | 'processing' | 'completed' | 'error';
  color: string;
}

export interface WorkflowStep {
  step_number: number;
  agent: string;
  action: string;
  success: boolean;
  result?: any;
  error?: string;
  duration_ms?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  metadata?: {
    agents_used?: string[];
    execution_plan?: any;
    workflow_results?: WorkflowStep[];
  };
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  response: {
    text: string;
    agents_used: string[];
    execution_plan: any;
    workflow_summary: {
      total_steps: number;
      successful_steps: number;
    };
    transparency_events?: TransparencyEvent[];
  };
  agent_used: string;
  status: string;
  timestamp: string;
}

// Phase D: Transparency Event Types
export type EventType = 'received' | 'thinking' | 'decision' | 'action' | 'result' | 'error';

export interface TransparencyEvent {
  id: string;
  session_id: string;
  agent_name: string;
  event_type: EventType;
  title: string;
  details: Record<string, any>;
  parent_event_id?: string;
  step_number?: number;
  created_at: string;
  duration_ms?: number;
}

// Agent visual states for animations
export type AgentVisualState = 'idle' | 'receiving' | 'thinking' | 'acting' | 'complete' | 'error';

export interface AgentState extends Agent {
  visualState: AgentVisualState;
  currentEvent?: TransparencyEvent;
}

// Data source types for D12
export type DataSourceType = 'csv' | 'salesforce' | 'wealthbox' | 'hubspot' | 'custom';

export interface DataSourceInfo {
  type: DataSourceType;
  name: string;
  clientCount: number;
  icon: string;
  color: string;
}
