// Data source types
export type DataSourceType = 'csv' | 'salesforce' | 'wealthbox' | 'hubspot' | 'custom';

export interface DataSourceInfo {
  type: DataSourceType;
  name: string;
  clientCount: number;
  icon: string;
  color: string;
}

export interface DataSource {
  id: string;
  file_name: string;
  file_type: string;
  status: string;
  records_imported: number;
  uploaded_at: string;
  processed_at?: string;
  meta_data?: {
    rows?: number;
    columns?: string[];
    dataset_name?: string;
  };
}

export interface UploadResponse {
  status: string;
  file_name: string;
  gcs_path: string;
  result: {
    data_source_id: string;
    records_ingested: number;
    columns: string[];
    field_mappings: Record<string, any>;
  };
}

export interface User {
  email: string;
  name?: string;
  picture?: string;
  user_id: string;
}
