import { useState } from 'react';
import { Upload, FileSpreadsheet, X, CheckCircle, AlertCircle } from 'lucide-react';
import { dataApi } from '../services/api';

interface DataUploadProps {
  onUploadComplete?: () => void;
}

export function DataUpload({ onUploadComplete }: DataUploadProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{
    type: 'success' | 'error' | null;
    message: string;
  }>({ type: null, message: '' });

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.type === 'text/csv' || selectedFile.name.endsWith('.csv')) {
        setFile(selectedFile);
        setUploadStatus({ type: null, message: '' });
      } else {
        setUploadStatus({ type: 'error', message: 'Please select a CSV file' });
      }
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setUploadStatus({ type: null, message: '' });

    try {
      const response = await dataApi.uploadCSV(file);
      setUploadStatus({
        type: 'success',
        message: `Successfully uploaded ${response.records_processed} records`
      });
      setFile(null);

      setTimeout(() => {
        setIsOpen(false);
        setUploadStatus({ type: null, message: '' });
        onUploadComplete?.();
      }, 2000);
    } catch (error: any) {
      setUploadStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Upload failed. Please try again.'
      });
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.type === 'text/csv' || droppedFile.name.endsWith('.csv'))) {
      setFile(droppedFile);
      setUploadStatus({ type: null, message: '' });
    } else {
      setUploadStatus({ type: 'error', message: 'Please drop a CSV file' });
    }
  };

  return (
    <>
      {/* Upload Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
      >
        <Upload className="w-4 h-4" />
        <span className="text-sm font-medium">Upload Data</span>
      </button>

      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 max-w-md w-full mx-4">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">Upload Client Data</h2>
              <button
                onClick={() => setIsOpen(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drop Zone */}
            <div
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className="border-2 border-dashed border-slate-700 rounded-lg p-8 mb-4 text-center hover:border-primary-500 transition-colors"
            >
              <FileSpreadsheet className="w-12 h-12 text-slate-400 mx-auto mb-3" />
              <p className="text-sm text-slate-300 mb-2">
                Drag and drop your CSV file here
              </p>
              <p className="text-xs text-slate-500 mb-4">or</p>
              <label className="inline-block px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg cursor-pointer transition-colors">
                <span className="text-sm">Browse Files</span>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
            </div>

            {/* Selected File */}
            {file && (
              <div className="bg-slate-800 rounded-lg p-3 mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-primary-400" />
                  <span className="text-sm">{file.name}</span>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Status Message */}
            {uploadStatus.type && (
              <div className={`flex items-center gap-2 p-3 rounded-lg mb-4 ${
                uploadStatus.type === 'success'
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-red-500/10 text-red-400'
              }`}>
                {uploadStatus.type === 'success' ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  <AlertCircle className="w-4 h-4" />
                )}
                <span className="text-sm">{uploadStatus.message}</span>
              </div>
            )}

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {uploading ? 'Uploading...' : 'Upload Data'}
            </button>

            {/* Info */}
            <p className="text-xs text-slate-500 mt-4">
              Upload a CSV file with client data. The system will automatically analyze the structure and make it available for multi-agent analysis.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
