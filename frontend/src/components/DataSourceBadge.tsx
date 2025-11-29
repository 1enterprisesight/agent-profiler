import type { DataSourceType } from '@/types';

// Data source icons and colors
const sourceConfig: Record<DataSourceType, { icon: string; color: string; bgColor: string; label: string }> = {
  csv: {
    icon: '📁',
    color: 'text-slate-300',
    bgColor: 'bg-slate-500/20 border-slate-500/50',
    label: 'CSV',
  },
  salesforce: {
    icon: '☁️',
    color: 'text-blue-300',
    bgColor: 'bg-blue-500/20 border-blue-500/50',
    label: 'Salesforce',
  },
  wealthbox: {
    icon: '📊',
    color: 'text-green-300',
    bgColor: 'bg-green-500/20 border-green-500/50',
    label: 'Wealthbox',
  },
  hubspot: {
    icon: '🔶',
    color: 'text-orange-300',
    bgColor: 'bg-orange-500/20 border-orange-500/50',
    label: 'HubSpot',
  },
  custom: {
    icon: '🔌',
    color: 'text-purple-300',
    bgColor: 'bg-purple-500/20 border-purple-500/50',
    label: 'Custom',
  },
};

interface DataSourceBadgeProps {
  source: DataSourceType;
  count?: number;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function DataSourceBadge({
  source,
  count,
  showLabel = true,
  size = 'md'
}: DataSourceBadgeProps) {
  const config = sourceConfig[source] || sourceConfig.custom;

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded border
        ${config.bgColor} ${config.color} ${sizeClasses[size]}
      `}
    >
      <span>{config.icon}</span>
      {showLabel && <span>{config.label}</span>}
      {count !== undefined && (
        <span className="font-semibold">{count.toLocaleString()}</span>
      )}
    </span>
  );
}

interface DataSourceSummaryProps {
  sources: Array<{ type: DataSourceType; count: number }>;
}

export function DataSourceSummary({ sources }: DataSourceSummaryProps) {
  const totalCount = sources.reduce((sum, s) => sum + s.count, 0);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-slate-400">Sources:</span>
      {sources.map((source) => (
        <DataSourceBadge
          key={source.type}
          source={source.type}
          count={source.count}
          size="sm"
        />
      ))}
      <span className="text-xs text-slate-500">
        ({totalCount.toLocaleString()} total)
      </span>
    </div>
  );
}

interface DataSourceQualityBarProps {
  source: DataSourceType;
  clientCount: number;
  emailPercent: number;
  phonePercent: number;
  aumPercent: number;
}

export function DataSourceQualityBar({
  source,
  clientCount,
  emailPercent,
  phonePercent,
  aumPercent
}: DataSourceQualityBarProps) {
  const config = sourceConfig[source] || sourceConfig.custom;
  const avgScore = Math.round((emailPercent + phonePercent + aumPercent) / 3);

  return (
    <div className="p-3 rounded-lg bg-slate-800 border border-slate-700">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{config.icon}</span>
          <span className="font-medium text-white">{config.label}</span>
          <span className="text-sm text-slate-400">
            {clientCount.toLocaleString()} clients
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-sm text-slate-400">Score:</span>
          <span className={`font-bold ${avgScore >= 70 ? 'text-green-400' : 'text-orange-400'}`}>
            {avgScore}%
          </span>
        </div>
      </div>

      {/* Quality bars */}
      <div className="space-y-1.5">
        <QualityMetric label="Email" percent={emailPercent} />
        <QualityMetric label="Phone" percent={phonePercent} />
        <QualityMetric label="AUM" percent={aumPercent} />
      </div>
    </div>
  );
}

function QualityMetric({ label, percent }: { label: string; percent: number }) {
  const getColor = (p: number) => {
    if (p >= 90) return 'bg-green-500';
    if (p >= 70) return 'bg-emerald-500';
    if (p >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400 w-12">{label}</span>
      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor(percent)} transition-all duration-500`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-xs text-slate-300 w-10 text-right">{percent}%</span>
    </div>
  );
}
