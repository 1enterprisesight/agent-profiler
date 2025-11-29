import { useEffect, useState } from 'react';
import { Database, Calendar, FileText, AlertCircle } from 'lucide-react';
import { dataApi } from '../services/api';
import { DataUpload } from './DataUpload';

interface DataSource {
  id: string;
  source_type: string;
  source_name: string;
  file_name: string;
  status: string;
  records_ingested: number;
  created_at: string;
  metadata: any;
}

interface DataSourceListProps {
  onManageClick?: () => void;
}

export function DataSourceList({ onManageClick }: DataSourceListProps) {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDataSources = async () => {
    try {
      setLoading(true);
      const response = await dataApi.getDataSources();
      setDataSources(response.uploads || []);
      setError(null);
    } catch (err: any) {
      setError('Failed to load data sources');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDataSources();
    // Refresh every 30 seconds
    const interval = setInterval(loadDataSources, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && dataSources.length === 0) {
    return (
      <div className="bg-slate-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Database className="w-5 h-5" />
          Active Data Sources
        </h3>
        <div className="text-center text-slate-400 py-8">
          <div className="animate-pulse">Loading...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Database className="w-5 h-5" />
          Active Data Sources
        </h3>
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      </div>
    );
  }

  const activeDataSources = dataSources.filter(ds => ds.status === 'completed' || ds.status === 'active');
  const totalRecords = activeDataSources.reduce((sum, ds) => sum + (ds.records_ingested || 0), 0);

  return (
    <div className="bg-slate-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Database className="w-5 h-5" />
          Active Data Sources
        </h3>
        <div className="flex items-center gap-2">
          <DataUpload onUploadComplete={loadDataSources} />
          {onManageClick && (
            <button
              onClick={onManageClick}
              className="text-sm text-primary-400 hover:text-primary-300 transition-colors"
            >
              Manage
            </button>
          )}
        </div>
      </div>

      {activeDataSources.length === 0 ? (
        <div className="text-center text-slate-400 py-8">
          <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-sm">No data sources uploaded yet</p>
          <p className="text-xs mt-1">Upload a CSV file to get started</p>
        </div>
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-slate-700/50 rounded-lg p-3">
              <div className="text-2xl font-bold text-white">{activeDataSources.length}</div>
              <div className="text-xs text-slate-400">Data Sources</div>
            </div>
            <div className="bg-slate-700/50 rounded-lg p-3">
              <div className="text-2xl font-bold text-white">{totalRecords.toLocaleString()}</div>
              <div className="text-xs text-slate-400">Total Records</div>
            </div>
          </div>

          {/* Data Source List - show all since panel is scrollable */}
          <div className="space-y-2">
            {activeDataSources.map((ds) => (
              <DataSourceCard key={ds.id} dataSource={ds} />
            ))}
          </div>

          {/* Manage link always visible */}
          {activeDataSources.length > 0 && (
            <button
              onClick={onManageClick}
              className="w-full mt-3 text-sm text-slate-400 hover:text-white transition-colors"
            >
              Manage data sources →
            </button>
          )}
        </>
      )}
    </div>
  );
}

function DataSourceCard({ dataSource }: { dataSource: DataSource }) {
  const uploadDate = new Date(dataSource.created_at);
  const isRecent = Date.now() - uploadDate.getTime() < 24 * 60 * 60 * 1000; // Last 24 hours

  return (
    <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600 hover:border-primary-500 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-primary-400 flex-shrink-0" />
            <h4 className="text-sm font-medium text-white truncate">
              {dataSource.source_name || dataSource.file_name}
            </h4>
            {isRecent && (
              <span className="px-2 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 rounded">
                New
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {uploadDate.toLocaleDateString()}
            </span>
            <span>{(dataSource.records_ingested || 0).toLocaleString()} records</span>
          </div>
        </div>
      </div>
    </div>
  );
}
