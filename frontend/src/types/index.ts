export interface SupersetServerConfig {
  id: string;
  name: string;
  host: string;
  port: number;
  enabled: boolean;
}

export interface DashboardItem {
  id: number;
  dashboard_title: string;
}

export interface ChartInfo {
  id: number;
  name: string;
  viz_type: string;
  datasource_id?: number;
  datasource_type?: string;
  sql_in_params: string[];
}

export interface DatasetInfo {
  id: number;
  name: string;
  type: 'virtual' | 'physical';
  database_id?: number;
  schema?: string;
  table_name: string;
  columns: { name: string; type: string }[];
  metrics: { name: string; expression: string }[];
  sql?: string;
}

export interface DatabaseInfo {
  id: number;
  name: string;
  engine?: string;
  sqlalchemy_uri?: string;
}

export interface ExportResult {
  dashboard: {
    id: number;
    name: string;
    chart_count: number;
    chart_ids: number[];
  };
  charts: ChartInfo[];
  datasets: DatasetInfo[];
  databases: DatabaseInfo[];
  tables: string[];
  sql_queries: { chart_id: number; chart_name: string; sql: string }[];
  summary: {
    total_charts: number;
    total_datasets: number;
    total_databases: number;
    total_tables: number;
    total_sql_queries: number;
  };
}

export interface ImportCheckResult {
  can_import: boolean;
  dashboard: {
    id: number;
    name: string;
    source_server: string;
    chart_count: number;
  };
  target_server: string;
  checks: {
    databases: CheckItem[];
    datasets: CheckItem[];
    charts: CheckItem[];
  };
  summary: {
    databases_checked: number;
    datasets_checked: number;
    charts_checked: number;
    databases_missing: number;
    datasets_missing: number;
    chart_issues: number;
  };
  blockers: string[];
  recommendations: string[];
}

interface CheckItem {
  source_id?: number;
  source_name?: string;
  type?: string;
  exists_on_target?: boolean;
  target_id?: number;
  chart_id?: number;
  chart_name?: string;
  datasource_id?: number;
  dataset_missing?: boolean;
  error?: string;
}

export interface BackendServerConfig {
  host: string;
  port: number;
}

export interface AppConfig {
  backend: BackendServerConfig;
  supersetServers: SupersetServerConfig[];
}
