import { useState, useEffect } from 'react';
import { X, Trash2, FileText, Calendar, Database, AlertCircle, CheckCircle } from 'lucide-react';
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

interface DataSourceManagerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DataSourceManager({ isOpen, onClose }: DataSourceManagerProps) {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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
    if (isOpen) {
      loadDataSources();
    }
  }, [isOpen]);

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete "${name}"? This will remove all associated data and cannot be undone.`)) {
      return;
    }

    setDeletingId(id);
    try {
      await dataApi.deleteDataSource(id);
      await loadDataSources(); // Reload list
    } catch (err: any) {
      alert(`Failed to delete: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const handleUploadComplete = () => {
    loadDataSources(); // Reload list after upload
  };

  if (!isOpen) return null;

  const activeCount = dataSources.filter(ds => ds.status === 'completed' || ds.status === 'active').length;
  const totalRecords = dataSources.reduce((sum, ds) => sum + (ds.records_ingested || 0), 0);

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-slate-900 rounded-xl border border-slate-800 max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <div>
            <h2 className="text-2xl font-bold text-white">Manage Data Sources</h2>
            <p className="text-sm text-slate-400 mt-1">
              View and manage your uploaded datasets
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 p-6 border-b border-slate-800 bg-slate-800/50">
          <StatCard
            icon={<Database className="w-5 h-5" />}
            value={dataSources.length}
            label="Total Uploads"
            color="text-primary-400"
          />
          <StatCard
            icon={<CheckCircle className="w-5 h-5" />}
            value={activeCount}
            label="Active Sources"
            color="text-emerald-400"
          />
          <StatCard
            icon={<FileText className="w-5 h-5" />}
            value={totalRecords.toLocaleString()}
            label="Total Records"
            color="text-blue-400"
          />
        </div>

        {/* Upload Button */}
        <div className="p-6 border-b border-slate-800 bg-slate-800/30">
          <DataUpload onUploadComplete={handleUploadComplete} />
        </div>

        {/* Data Sources List */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="text-center text-slate-400 py-12">
              <div className="animate-pulse">Loading data sources...</div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center gap-2 text-red-400 py-12">
              <AlertCircle className="w-5 h-5" />
              {error}
            </div>
          ) : dataSources.length === 0 ? (
            <div className="text-center text-slate-400 py-12">
              <Database className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg mb-2">No data sources yet</p>
              <p className="text-sm">Upload your first CSV file to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {dataSources.map((ds) => (
                <DataSourceRow
                  key={ds.id}
                  dataSource={ds}
                  onDelete={() => handleDelete(ds.id, ds.source_name || ds.file_name)}
                  isDeleting={deletingId === ds.id}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, value, label, color }: { icon: React.ReactNode; value: number | string; label: string; color: string }) {
  return (
    <div className="bg-slate-700/50 rounded-lg p-4">
      <div className={`${color} mb-2`}>{icon}</div>
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-slate-400">{label}</div>
    </div>
  );
}

function DataSourceRow({
  dataSource,
  onDelete,
  isDeleting
}: {
  dataSource: DataSource;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  const uploadDate = new Date(dataSource.created_at);
  const isRecent = Date.now() - uploadDate.getTime() < 24 * 60 * 60 * 1000;

  const statusColors = {
    completed: 'text-emerald-400 bg-emerald-500/10',
    active: 'text-emerald-400 bg-emerald-500/10',
    processing: 'text-blue-400 bg-blue-500/10',
    failed: 'text-red-400 bg-red-500/10',
  };

  const statusColor = statusColors[dataSource.status as keyof typeof statusColors] || 'text-slate-400 bg-slate-500/10';

  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 hover:border-slate-600 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-3 mb-2">
            <FileText className="w-5 h-5 text-primary-400 flex-shrink-0" />
            <h3 className="text-base font-semibold text-white truncate">
              {dataSource.source_name || dataSource.file_name}
            </h3>
            {isRecent && (
              <span className="px-2 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 rounded flex-shrink-0">
                New
              </span>
            )}
            <span className={`px-2 py-0.5 text-xs rounded flex-shrink-0 ${statusColor}`}>
              {dataSource.status}
            </span>
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4 text-sm text-slate-400">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Calendar className="w-4 h-4" />
                <span>Uploaded: {uploadDate.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4" />
                <span>Records: {(dataSource.records_ingested || 0).toLocaleString()}</span>
              </div>
            </div>
            {dataSource.metadata && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Dataset Info:</div>
                <div className="text-xs">
                  {dataSource.metadata.rows && <div>Rows: {dataSource.metadata.rows}</div>}
                  {dataSource.metadata.columns && <div>Columns: {dataSource.metadata.columns.length}</div>}
                </div>
              </div>
            )}
          </div>

          {/* Columns */}
          {dataSource.metadata?.columns && (
            <div className="mt-3">
              <div className="text-xs text-slate-500 mb-1">Columns:</div>
              <div className="flex flex-wrap gap-1">
                {dataSource.metadata.columns.slice(0, 8).map((col: string, idx: number) => (
                  <span key={idx} className="px-2 py-0.5 text-xs bg-slate-700 text-slate-300 rounded">
                    {col}
                  </span>
                ))}
                {dataSource.metadata.columns.length > 8 && (
                  <span className="px-2 py-0.5 text-xs text-slate-500">
                    +{dataSource.metadata.columns.length - 8} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="ml-4 p-2 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
          title="Delete data source"
        >
          {isDeleting ? (
            <div className="w-5 h-5 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <Trash2 className="w-5 h-5" />
          )}
        </button>
      </div>
    </div>
  );
}
