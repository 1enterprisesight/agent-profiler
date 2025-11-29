import { useMemo } from 'react';
import type { DataSourceType } from '@/types';

// Source configuration
const sourceConfig: Record<DataSourceType, { icon: string; color: string; label: string }> = {
  csv: { icon: '📁', color: '#64748b', label: 'CSV' },
  salesforce: { icon: '☁️', color: '#3b82f6', label: 'Salesforce' },
  wealthbox: { icon: '📊', color: '#22c55e', label: 'Wealthbox' },
  hubspot: { icon: '🔶', color: '#f97316', label: 'HubSpot' },
  custom: { icon: '🔌', color: '#a855f7', label: 'Custom' },
};

interface CrossSourceData {
  sourceA: {
    type: DataSourceType;
    total: number;
    uniqueCount: number;
  };
  sourceB: {
    type: DataSourceType;
    total: number;
    uniqueCount: number;
  };
  overlapCount: number;
  matchField: string;
}

interface CrossSourceViewProps {
  data: CrossSourceData;
  onViewSource?: (source: DataSourceType, filter: 'all' | 'unique' | 'overlap') => void;
}

export function CrossSourceView({ data, onViewSource }: CrossSourceViewProps) {
  const configA = sourceConfig[data.sourceA.type] || sourceConfig.custom;
  const configB = sourceConfig[data.sourceB.type] || sourceConfig.custom;

  // Calculate percentages for visualization
  const totalA = data.sourceA.total;
  const totalB = data.sourceB.total;
  const overlap = data.overlapCount;

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-4">
        Cross-Source Analysis: {configA.label} vs {configB.label}
      </h3>

      {/* Venn-style visualization */}
      <div className="flex items-center justify-center gap-4 my-8">
        {/* Source A circle */}
        <div className="relative">
          <div
            className="w-32 h-32 rounded-full flex flex-col items-center justify-center border-4"
            style={{
              backgroundColor: `${configA.color}20`,
              borderColor: configA.color,
            }}
          >
            <span className="text-2xl">{configA.icon}</span>
            <span className="text-xl font-bold text-white">{totalA.toLocaleString()}</span>
            <span className="text-xs text-slate-400">clients</span>
          </div>
          <div className="text-center mt-2">
            <span className="text-sm font-medium text-white">{configA.label}</span>
          </div>
        </div>

        {/* Overlap indicator */}
        <div className="flex flex-col items-center -mx-8 z-10">
          <div
            className="w-20 h-20 rounded-full flex flex-col items-center justify-center border-4 border-dashed bg-slate-900"
            style={{ borderColor: '#8b5cf6' }}
          >
            <span className="text-lg font-bold text-violet-400">{overlap.toLocaleString()}</span>
            <span className="text-xs text-slate-400">overlap</span>
          </div>
          <div className="text-xs text-slate-500 mt-2">
            matched on {data.matchField}
          </div>
        </div>

        {/* Source B circle */}
        <div className="relative">
          <div
            className="w-32 h-32 rounded-full flex flex-col items-center justify-center border-4"
            style={{
              backgroundColor: `${configB.color}20`,
              borderColor: configB.color,
            }}
          >
            <span className="text-2xl">{configB.icon}</span>
            <span className="text-xl font-bold text-white">{totalB.toLocaleString()}</span>
            <span className="text-xs text-slate-400">clients</span>
          </div>
          <div className="text-center mt-2">
            <span className="text-sm font-medium text-white">{configB.label}</span>
          </div>
        </div>
      </div>

      {/* Summary stats */}
      <div className="bg-slate-900 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>{configA.icon}</span>
            <span className="text-sm text-slate-300">Only in {configA.label}</span>
          </div>
          <span className="font-semibold text-white">
            {data.sourceA.uniqueCount.toLocaleString()}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>{configB.icon}</span>
            <span className="text-sm text-slate-300">Only in {configB.label}</span>
          </div>
          <span className="font-semibold text-white">
            {data.sourceB.uniqueCount.toLocaleString()}
          </span>
        </div>

        <div className="flex items-center justify-between border-t border-slate-700 pt-3">
          <div className="flex items-center gap-2">
            <span>🔗</span>
            <span className="text-sm text-slate-300">In both sources</span>
          </div>
          <span className="font-semibold text-violet-400">
            {overlap.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Action buttons */}
      {onViewSource && (
        <div className="flex gap-2 mt-4">
          <button
            onClick={() => onViewSource(data.sourceA.type, 'unique')}
            className="flex-1 px-3 py-2 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
            style={{ borderLeft: `3px solid ${configA.color}` }}
          >
            View {configA.label} Only
          </button>
          <button
            onClick={() => onViewSource(data.sourceB.type, 'unique')}
            className="flex-1 px-3 py-2 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
            style={{ borderLeft: `3px solid ${configB.color}` }}
          >
            View {configB.label} Only
          </button>
          <button
            onClick={() => onViewSource(data.sourceA.type, 'overlap')}
            className="flex-1 px-3 py-2 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors border-l-4 border-violet-500"
          >
            View Matches
          </button>
        </div>
      )}
    </div>
  );
}

// Data Quality Dashboard showing all sources
interface DataQualityDashboardProps {
  sources: Array<{
    type: DataSourceType;
    clientCount: number;
    emailPercent: number;
    phonePercent: number;
    aumPercent: number;
  }>;
}

export function DataQualityDashboard({ sources }: DataQualityDashboardProps) {
  const sortedSources = useMemo(() => {
    return [...sources].sort((a, b) => b.clientCount - a.clientCount);
  }, [sources]);

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-400';
    if (score >= 70) return 'text-yellow-400';
    if (score >= 50) return 'text-orange-400';
    return 'text-red-400';
  };

  const renderBar = (percent: number) => {
    const getBarColor = (p: number) => {
      if (p >= 90) return 'bg-green-500';
      if (p >= 70) return 'bg-emerald-500';
      if (p >= 50) return 'bg-yellow-500';
      return 'bg-red-500';
    };

    return (
      <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${getBarColor(percent)}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    );
  };

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-4">Data Source Quality</h3>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-700">
              <th className="pb-3 font-medium">Source</th>
              <th className="pb-3 font-medium text-right">Clients</th>
              <th className="pb-3 font-medium">Email %</th>
              <th className="pb-3 font-medium">Phone %</th>
              <th className="pb-3 font-medium">AUM %</th>
              <th className="pb-3 font-medium text-right">Score</th>
            </tr>
          </thead>
          <tbody>
            {sortedSources.map((source) => {
              const config = sourceConfig[source.type] || sourceConfig.custom;
              const avgScore = Math.round(
                (source.emailPercent + source.phonePercent + source.aumPercent) / 3
              );

              return (
                <tr key={source.type} className="border-b border-slate-700/50">
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{config.icon}</span>
                      <span className="text-sm text-white">{config.label}</span>
                    </div>
                  </td>
                  <td className="py-3 text-right">
                    <span className="text-sm text-white font-medium">
                      {source.clientCount.toLocaleString()}
                    </span>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      {renderBar(source.emailPercent)}
                      <span className="text-xs text-slate-400 w-8">
                        {source.emailPercent}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      {renderBar(source.phonePercent)}
                      <span className="text-xs text-slate-400 w-8">
                        {source.phonePercent}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      {renderBar(source.aumPercent)}
                      <span className="text-xs text-slate-400 w-8">
                        {source.aumPercent}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3 text-right">
                    <span className={`text-sm font-bold ${getScoreColor(avgScore)}`}>
                      {avgScore}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-slate-700">
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span>Completeness:</span>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-green-500" />
            <span>90-100%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-emerald-500" />
            <span>70-89%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-yellow-500" />
            <span>50-69%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-red-500" />
            <span>&lt;50%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
