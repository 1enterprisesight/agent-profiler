/**
 * AnalysisResultsPanel Component
 *
 * Displays comprehensive analysis results:
 * - Understanding/interpretation of the query
 * - SQL query executed (collapsible)
 * - Data table with results
 * - Chart visualization (bar, line, pie) with column selection
 */

import { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Code,
  Lightbulb,
  ArrowRight,
  Copy,
  Check,
  BarChart3,
  TrendingUp,
  PieChart,
} from 'lucide-react';
import { clsx } from 'clsx';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart as RechartsPie,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { AgentActivity } from '../hooks/useChat';

interface AnalysisResultsPanelProps {
  agentActivities: AgentActivity[];
  data?: any;
  visualization?: {
    type?: string;
    data?: any[];
  };
}

type ChartType = 'bar' | 'line' | 'pie';

// Colors for pie chart
const CHART_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1',
];

export function AnalysisResultsPanel({
  agentActivities,
  data,
  visualization: _visualization,
}: AnalysisResultsPanelProps) {
  const [showSql, setShowSql] = useState(false);
  const [copiedSql, setCopiedSql] = useState(false);
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [labelColumn, setLabelColumn] = useState<string>('');

  // Extract data from agent activities
  const sqlActivity = agentActivities.find((a) => a.agent === 'sql_analytics');
  const sqlResult = sqlActivity?.result;

  // Get query results
  const queryResults = sqlResult?.results?.[0]?.data || data || [];
  const queriesExecuted = sqlResult?.queries_executed || [];
  const insights = sqlResult?.insights;

  // Get columns from first result row
  const columns = queryResults.length > 0 ? Object.keys(queryResults[0]) : [];

  // Identify numeric and text columns
  const { numericColumns, textColumns } = useMemo(() => {
    if (queryResults.length === 0) return { numericColumns: [], textColumns: [] };

    const numeric: string[] = [];
    const text: string[] = [];

    columns.forEach(col => {
      const hasNumeric = queryResults.some((row: any) => typeof row[col] === 'number');
      if (hasNumeric) {
        numeric.push(col);
      } else {
        text.push(col);
      }
    });

    return { numericColumns: numeric, textColumns: text };
  }, [queryResults, columns]);

  // Set default label column
  useMemo(() => {
    if (!labelColumn && textColumns.length > 0) {
      setLabelColumn(textColumns[0]);
    }
  }, [textColumns, labelColumn]);

  // Format value for display
  const formatValue = (value: any): string => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'number') {
      return value.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      });
    }
    return String(value);
  };

  // Copy SQL to clipboard
  const copySql = async () => {
    const sql = queriesExecuted.map((q: any) => q.sql).join('\n\n');
    await navigator.clipboard.writeText(sql);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  // Prepare chart data
  const chartData = useMemo(() => {
    if (queryResults.length === 0 || numericColumns.length === 0) return [];

    const labelCol = labelColumn || textColumns[0];
    const valueCol = numericColumns[0];

    if (!labelCol || !valueCol) return [];

    // Aggregate data by label if there are duplicates
    const aggregated = new Map<string, number>();
    queryResults.forEach((row: any) => {
      const label = String(row[labelCol] || 'Unknown');
      const value = Number(row[valueCol]) || 0;
      aggregated.set(label, (aggregated.get(label) || 0) + value);
    });

    return Array.from(aggregated.entries())
      .slice(0, 15)
      .map(([name, value]) => ({
        name: name.length > 25 ? name.slice(0, 22) + '...' : name,
        value,
        fullName: name,
      }));
  }, [queryResults, labelColumn, textColumns, numericColumns]);

  if (!sqlActivity && queryResults.length === 0) {
    return null;
  }

  const hasChartData = chartData.length > 0 && numericColumns.length > 0;

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-4 h-4 text-yellow-400" />
          <h3 className="text-sm font-semibold text-white">Analysis Results</h3>
          {queryResults.length > 0 && (
            <span className="text-xs text-slate-400">
              ({queryResults.length} rows)
            </span>
          )}
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Insights Summary */}
        {insights?.summary && (
          <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-600">
            <div className="flex items-start gap-2">
              <Lightbulb className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-slate-200">{insights.summary}</p>
            </div>
          </div>
        )}

        {/* SQL Query (Collapsible) */}
        {queriesExecuted.length > 0 && (
          <div className="border border-slate-600 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowSql(!showSql)}
              className="w-full px-3 py-2 flex items-center justify-between bg-slate-700/50 hover:bg-slate-700 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Code className="w-4 h-4 text-green-400" />
                <span className="text-xs font-medium text-slate-300">
                  SQL Query ({queriesExecuted.length})
                </span>
              </div>
              <div className="flex items-center gap-2">
                {showSql && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      copySql();
                    }}
                    className="p-1 hover:bg-slate-600 rounded transition-colors"
                    title="Copy SQL"
                  >
                    {copiedSql ? (
                      <Check className="w-3 h-3 text-green-400" />
                    ) : (
                      <Copy className="w-3 h-3 text-slate-400" />
                    )}
                  </button>
                )}
                {showSql ? (
                  <ChevronUp className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                )}
              </div>
            </button>

            {showSql && (
              <div className="p-3 bg-slate-900 border-t border-slate-600">
                {queriesExecuted.map((query: any, idx: number) => (
                  <div key={idx} className="mb-2 last:mb-0">
                    {query.purpose && (
                      <p className="text-xs text-slate-400 mb-1">
                        -- {query.purpose}
                      </p>
                    )}
                    <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap overflow-x-auto">
                      {query.sql}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Data Table */}
        {queryResults.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-slate-600">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-700/50">
                  {columns.map((col) => (
                    <th
                      key={col}
                      className="text-left px-3 py-2 text-xs font-medium text-slate-300 uppercase tracking-wider"
                    >
                      {col.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {queryResults.slice(0, 20).map((row: any, idx: number) => (
                  <tr
                    key={idx}
                    className="hover:bg-slate-700/30 transition-colors"
                  >
                    {columns.map((col) => (
                      <td
                        key={col}
                        className="px-3 py-2 text-slate-200 whitespace-nowrap"
                      >
                        {formatValue(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {queryResults.length > 20 && (
              <div className="px-3 py-2 bg-slate-700/30 text-xs text-slate-400 text-center">
                Showing 20 of {queryResults.length} rows
              </div>
            )}
          </div>
        )}

        {/* Chart Section */}
        {hasChartData && (
          <div className="border border-slate-600 rounded-lg overflow-hidden">
            {/* Chart Controls */}
            <div className="px-3 py-2 bg-slate-700/50 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Chart Type:</span>
                <div className="flex gap-1 bg-slate-800 rounded p-0.5">
                  <button
                    onClick={() => setChartType('bar')}
                    className={clsx(
                      'p-1.5 rounded transition-colors',
                      chartType === 'bar' ? 'bg-primary-600 text-white' : 'text-slate-400 hover:text-white'
                    )}
                    title="Bar Chart"
                  >
                    <BarChart3 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setChartType('line')}
                    className={clsx(
                      'p-1.5 rounded transition-colors',
                      chartType === 'line' ? 'bg-primary-600 text-white' : 'text-slate-400 hover:text-white'
                    )}
                    title="Line Chart"
                  >
                    <TrendingUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setChartType('pie')}
                    className={clsx(
                      'p-1.5 rounded transition-colors',
                      chartType === 'pie' ? 'bg-primary-600 text-white' : 'text-slate-400 hover:text-white'
                    )}
                    title="Pie Chart"
                  >
                    <PieChart className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {textColumns.length > 1 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">Group by:</span>
                  <select
                    value={labelColumn}
                    onChange={(e) => setLabelColumn(e.target.value)}
                    className="bg-slate-800 text-white text-xs rounded px-2 py-1 border border-slate-600 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  >
                    {textColumns.map(col => (
                      <option key={col} value={col}>
                        {col.replace(/_/g, ' ')}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Chart */}
            <div className="h-72 bg-slate-900/50 p-4">
              <ResponsiveContainer width="100%" height="100%">
                {chartType === 'bar' ? (
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 60 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis
                      dataKey="name"
                      stroke="#94a3b8"
                      fontSize={10}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                      interval={0}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      fontSize={10}
                      tickFormatter={(value) =>
                        value >= 1000000 ? `${(value / 1000000).toFixed(1)}M` :
                        value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value
                      }
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      labelStyle={{ color: '#f1f5f9' }}
                      formatter={(value: number) => [value.toLocaleString(), numericColumns[0]?.replace(/_/g, ' ')]}
                      labelFormatter={(label) => chartData.find(d => d.name === label)?.fullName || label}
                    />
                    <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                ) : chartType === 'line' ? (
                  <LineChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 60 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis
                      dataKey="name"
                      stroke="#94a3b8"
                      fontSize={10}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                      interval={0}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      fontSize={10}
                      tickFormatter={(value) =>
                        value >= 1000000 ? `${(value / 1000000).toFixed(1)}M` :
                        value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value
                      }
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      labelStyle={{ color: '#f1f5f9' }}
                      formatter={(value: number) => [value.toLocaleString(), numericColumns[0]?.replace(/_/g, ' ')]}
                      labelFormatter={(label) => chartData.find(d => d.name === label)?.fullName || label}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={{ fill: '#3b82f6', strokeWidth: 2 }}
                    />
                  </LineChart>
                ) : (
                  <RechartsPie>
                    <Pie
                      data={chartData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} (${((percent || 0) * 100).toFixed(0)}%)`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {chartData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      formatter={(value: number) => [value.toLocaleString(), numericColumns[0]?.replace(/_/g, ' ')]}
                    />
                    <Legend />
                  </RechartsPie>
                )}
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Key Findings */}
        {insights?.findings && insights.findings.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Key Findings
            </h4>
            <div className="space-y-1">
              {insights.findings.map((finding: string, idx: number) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 text-sm text-slate-300"
                >
                  <ArrowRight className="w-3 h-3 text-primary-400 mt-1 flex-shrink-0" />
                  <span>{finding}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
