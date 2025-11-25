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
  };
  agent_used: string;
  status: string;
  timestamp: string;
}
