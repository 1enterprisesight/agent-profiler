import { CheckCircle2, XCircle, Clock } from 'lucide-react';
import type { WorkflowStep } from '@/types';

interface WorkflowDisplayProps {
  workflow: any;
}

export function WorkflowDisplay({ workflow }: WorkflowDisplayProps) {
  if (!workflow || !workflow.workflow_results) {
    return (
      <div className="w-full h-full bg-slate-800 rounded-lg p-6 flex items-center justify-center">
        <p className="text-slate-400">No active workflow</p>
      </div>
    );
  }

  const steps = workflow.workflow_results || [];
  const totalSteps = steps.length;
  const successfulSteps = steps.filter((s: WorkflowStep) => s.success).length;

  return (
    <div className="w-full h-full bg-slate-800 rounded-lg p-6">
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

      {workflow.execution_plan && (
        <div className="mt-6 pt-6 border-t border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-2">Execution Plan</h3>
          <p className="text-sm text-slate-400">{workflow.execution_plan.rationale}</p>
        </div>
      )}
    </div>
  );
}

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
