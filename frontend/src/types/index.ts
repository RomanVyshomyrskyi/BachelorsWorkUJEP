/**
 * @module types
 * @description TypeScript type definitions for the Superset Dashboard Manager application.
 * Contains interfaces for server configurations, dashboard data, export/import results,
 * and application settings.
 */

/**
 * Configuration for a Superset server managed by the application.
 *
 * @interface SupersetServerConfig
 * @property {string} id - Unique identifier for the server (e.g., "production", "staging").
 * @property {string} name - Human-readable display name for the server.
 * @property {string} host - The hostname or IP address of the Superset server.
 * @property {number} port - The port number the Superset server is running on.
 * @property {boolean} enabled - Whether this server is active and available for use.
 *
 * @example
 * const server: SupersetServerConfig = {
 *   id: 'production',
 *   name: 'Production Superset',
 *   host: '10.0.0.1',
 *   port: 8001,
 *   enabled: true
 * };
 */
export interface SupersetServerConfig {
  id: string;
  name: string;
  host: string;
  port: number;
  enabled: boolean;
}

/**
 * A minimal representation of a Superset dashboard for listing purposes.
 *
 * @interface DashboardItem
 * @property {number} id - The numeric ID of the dashboard in Superset.
 * @property {string} dashboard_title - The display title of the dashboard.
 *
 * @example
 * const dashboard: DashboardItem = {
 *   id: 42,
 *   dashboard_title: 'Sales Overview'
 * };
 */
export interface DashboardItem {
  id: number;
  dashboard_title: string;
}

/**
 * Detailed information about a Superset chart within a dashboard.
 *
 * @interface ChartInfo
 * @property {number} id - The numeric ID of the chart in Superset.
 * @property {string} name - The display name of the chart.
 * @property {string} viz_type - The visualization type (e.g., "bar", "line", "pie", "table").
 * @property {number} [datasource_id] - The ID of the datasource this chart uses.
 * @property {string} [datasource_type] - The type of datasource (e.g., "table", "query").
 * @property {string[]} sql_in_params - Array of SQL query parameters associated with the chart.
 *
 * @example
 * const chart: ChartInfo = {
 *   id: 101,
 *   name: 'Revenue by Month',
 *   viz_type: 'bar',
 *   datasource_id: 5,
 *   datasource_type: 'table',
 *   sql_in_params: []
 * };
 */
export interface ChartInfo {
  id: number;
  name: string;
  viz_type: string;
  datasource_id?: number;
  datasource_type?: string;
  sql_in_params: string[];
}

/**
 * Information about a Superset dataset (physical table or virtual SQL query).
 *
 * @interface DatasetInfo
 * @property {number} id - The numeric ID of the dataset in Superset.
 * @property {string} name - The display name of the dataset.
 * @property {'virtual' | 'physical'} type - Whether this is a physical table or a virtual SQL query dataset.
 * @property {number} [database_id] - The ID of the database this dataset belongs to.
 * @property {string} [schema] - The database schema (e.g., "public", "analytics").
 * @property {string} table_name - The table name (for physical datasets) or alias (for virtual).
 * @property {{ name: string; type: string }[]} columns - Array of column definitions with name and type.
 * @property {{ name: string; expression: string }[]} metrics - Array of metric definitions with name and SQL expression.
 * @property {string} [sql] - The SQL query for virtual datasets (undefined for physical).
 *
 * @example
 * const dataset: DatasetInfo = {
 *   id: 10,
 *   name: 'sales_data',
 *   type: 'physical',
 *   database_id: 1,
 *   schema: 'public',
 *   table_name: 'sales',
 *   columns: [
 *     { name: 'id', type: 'INTEGER' },
 *     { name: 'amount', type: 'NUMERIC' }
 *   ],
 *   metrics: [
 *     { name: 'total_revenue', expression: 'SUM(amount)' }
 *   ]
 * };
 */
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

/**
 * Information about a database connection configured in Superset.
 *
 * @interface DatabaseInfo
 * @property {number} id - The numeric ID of the database in Superset.
 * @property {string} name - The display name of the database connection.
 * @property {string} [engine] - The database engine/driver (e.g., "postgresql", "mysql").
 * @property {string} [sqlalchemy_uri] - The SQLAlchemy connection URI for the database.
 *
 * @example
 * const db: DatabaseInfo = {
 *   id: 1,
 *   name: 'Production PostgreSQL',
 *   engine: 'postgresql',
 *   sqlalchemy_uri: 'postgresql://user:pass@host:5432/dbname'
 * };
 */
export interface DatabaseInfo {
  id: number;
  name: string;
  engine?: string;
  sqlalchemy_uri?: string;
}

/**
 * Complete result of a dashboard export operation.
 *
 * Contains all metadata, charts, datasets, databases, and SQL queries
 * associated with the exported dashboard.
 *
 * @interface ExportResult
 * @property {{ id: number; name: string; chart_count: number; chart_ids: number[] }} dashboard - Core dashboard metadata.
 * @property {ChartInfo[]} charts - Array of all charts in the dashboard.
 * @property {DatasetInfo[]} datasets - Array of all datasets used by the dashboard charts.
 * @property {DatabaseInfo[]} databases - Array of all databases referenced by the datasets.
 * @property {string[]} tables - Array of table names referenced by the datasets.
 * @property {{ chart_id: number; chart_name: string; sql: string }[]} sql_queries - Array of SQL queries extracted from charts.
 * @property {{ total_charts: number; total_datasets: number; total_databases: number; total_tables: number; total_sql_queries: number }} summary - Aggregate counts of all exported resources.
 *
 * @example
 * const result: ExportResult = await api.exportDashboard('production', 42);
 * console.log(result.dashboard.name);           // "Sales Overview"
 * console.log(result.summary.total_charts);     // 5
 * console.log(result.charts[0].name);           // "Revenue Chart"
 * console.log(result.databases[0].engine);      // "postgresql"
 */
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

/**
 * Individual item in an import readiness check result.
 *
 * @interface CheckItem
 * @property {number} [source_id] - The ID of the item on the source server.
 * @property {string} [source_name] - The name of the item on the source server.
 * @property {string} [type] - The type of the item being checked.
 * @property {boolean} [exists_on_target] - Whether the item exists on the target server.
 * @property {number} [target_id] - The ID of the matching item on the target server.
 * @property {number} [chart_id] - The chart ID (for chart-related checks).
 * @property {string} [chart_name] - The chart name (for chart-related checks).
 * @property {number} [datasource_id] - The datasource ID referenced by a chart.
 * @property {boolean} [dataset_missing] - Whether the dataset is missing on target.
 * @property {string} [error] - Error message if the check failed.
 */
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

/**
 * Result of an import readiness validation check.
 *
 * Provides a comprehensive report on whether an exported dashboard can be
 * safely imported into a target Superset server, including blockers and
 * recommendations.
 *
 * @interface ImportCheckResult
 * @property {boolean} can_import - Whether the import can proceed without blockers.
 * @property {{ id: number; name: string; source_server: string; chart_count: number }} dashboard - Dashboard metadata from the export.
 * @property {string} target_server - The ID of the target server being checked.
 * @property {{ databases: CheckItem[]; datasets: CheckItem[]; charts: CheckItem[] }} checks - Detailed check results for databases, datasets, and charts.
 * @property {{ databases_checked: number; datasets_checked: number; charts_checked: number; databases_missing: number; datasets_missing: number; chart_issues: number }} summary - Aggregate counts of checked items and issues.
 * @property {string[]} blockers - List of critical issues that would prevent import.
 * @property {string[]} recommendations - List of suggestions to improve import success.
 *
 * @example
 * const result: ImportCheckResult = await api.checkImportReady('staging', exportJson);
 * if (result.can_import) {
 *   console.log('Safe to import');
 * } else {
 *   console.log('Blockers:', result.blockers);
 *   console.log('Recommendations:', result.recommendations);
 * }
 */
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

/**
 * Backend server connection configuration for the frontend app.
 *
 * @interface BackendServerConfig
 * @property {string} host - The hostname of the backend API server.
 * @property {number} port - The port number of the backend API server.
 *
 * @example
 * const backend: BackendServerConfig = {
 *   host: 'localhost',
 *   port: 8000
 * };
 */
export interface BackendServerConfig {
  host: string;
  port: number;
}

/**
 * Complete application configuration stored in localStorage.
 *
 * @interface AppConfig
 * @property {BackendServerConfig} backend - Configuration for the backend API server.
 * @property {SupersetServerConfig[]} supersetServers - Array of configured Superset servers.
 *
 * @example
 * const config: AppConfig = {
 *   backend: { host: 'localhost', port: 8000 },
 *   supersetServers: [
 *     { id: 'prod', name: 'Production', host: '10.0.0.1', port: 8001, enabled: true },
 *     { id: 'staging', name: 'Staging', host: '10.0.0.2', port: 8001, enabled: true }
 *   ]
 * };
 */
export interface AppConfig {
  backend: BackendServerConfig;
  supersetServers: SupersetServerConfig[];
}
