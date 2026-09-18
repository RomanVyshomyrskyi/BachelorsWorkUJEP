/**
 * @module api/service
 * @description Frontend API service for communicating with the backend MCP server.
 * Provides methods for exporting dashboards, validating imports, listing servers,
 * and managing application configuration via localStorage.
 */

import type {
  ExportResult,
  ImportCheckResult,
  DashboardItem,
  AppConfig,
  DbConnection,
  DbTable,
  DbColumn,
  BatchInsertResult,
  SupersetServer,
  SupersetDb,
  SupersetSchema,
} from '../types';

/**
 * Configuration object for a backend Superset server (internal use only).
 *
 * @interface BackendServerConfig
 * @property {string} base_url - The full URL of the backend server (e.g., "http://localhost:8000/api").
 * @property {string} auth_method - The authentication method used by the server (e.g., "token", "session").
 */
interface BackendServerConfig {
  base_url: string;
  auth_method: string;
}

/**
 * Determines the backend API URL based on environment configuration.
 *
 * Priority order:
 * 1. `VITE_BACKEND_URL` from environment variables
 * 2. `http://host.docker.internal:8000` when running on port 8080 or in dev mode
 * 3. Empty string (relative URL) for production behind a reverse proxy
 *
 * @returns {string} The resolved backend base URL.
 *
 * @example
 * // In development (VITE_BACKEND_URL not set):
 * // Returns "http://host.docker.internal:8000"
 * const url = getBackendUrl();
 */
const getBackendUrl = (): string => {
  const envUrl = import.meta.env.VITE_BACKEND_URL;
  if (envUrl) return envUrl;
  if (window.location.port === '8080' || import.meta.env.DEV) {
    return 'http://host.docker.internal:8000';
  }
  return '';
};

/**
 * Serializes query parameters into a URL-encoded query string.
 *
 * Handles null/undefined filtering and JSON-stringifies object values.
 *
 * @param {Record<string, any>} params - Key-value pairs of query parameters.
 * @returns {string} A URL-encoded query string (e.g., "key1=value1&key2=value2").
 *
 * @example
 * // Returns "server_id=prod&dashboard_id=42"
 * buildQueryString({ server_id: 'prod', dashboard_id: 42 });
 *
 * @example
 * // Filters out null/undefined values
 * // Returns "name=dashboard"
 * buildQueryString({ name: 'dashboard', filter: null, sort: undefined });
 */
const buildQueryString = (params: Record<string, any>): string => {
  return Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(typeof v === 'object' ? JSON.stringify(v) : v)}`)
    .join('&');
};

/**
 * Sends an HTTP request to a backend tool endpoint.
 *
 * Routes requests to GET (with query string) or POST (with JSON body)
 * based on the `usePost` flag. Automatically parses double-encoded JSON
 * responses from the backend.
 *
 * @param {string} toolName - The name of the backend tool/endpoint to call (e.g., "get_dashboard_expert_info").
 * @param {Record<string, any>} params - Parameters to pass to the endpoint. For GET, these are query params. For POST, these are the JSON body.
 * @param {boolean} [usePost=false] - Whether to use POST (true) or GET (false) method.
 * @returns {Promise<any>} The parsed JSON response from the backend.
 * @throws {Error} Throws an error with the HTTP status text if the response is not OK.
 *
 * @example
 * // GET request with query parameters
 * const result = await callTool('list_dashboards', { server_id: 'prod' });
 *
 * @example
 * // POST request with JSON body
 * const result = await callTool('validate_export_file', {
 *   target_server_id: 'staging',
 *   export_data: JSON.stringify(exportData),
 * }, true);
 */
const callTool = async (toolName: string, params: Record<string, any>, usePost = false): Promise<any> => {
  const backendUrl = getBackendUrl();
  let url: string;
  let fetchOptions: RequestInit;

  if (usePost) {
    url = backendUrl ? `${backendUrl}/${toolName}` : `/${toolName}`;
    fetchOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    };
  } else {
    const qs = buildQueryString(params);
    url = backendUrl
      ? qs ? `${backendUrl}/${toolName}?${qs}` : `${backendUrl}/${toolName}`
      : qs ? `/${toolName}?${qs}` : `/${toolName}`;
    fetchOptions = {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    };
  }

  const response = await fetch(url, fetchOptions);

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  const text = await response.text();
  console.log(`[callTool] ${toolName} response (first 200 chars):`, text.substring(0, 200));
  try {
    const parsed = JSON.parse(text);
    console.log(`[callTool] ${toolName} parsed type:`, typeof parsed);
    return parsed;
  } catch {
    console.log(`[callTool] ${toolName} parse failed, returning as text`);
    return { result: text };
  }
};

/**
 * Recursively parses double-encoded JSON strings in an object.
 *
 * The backend sometimes returns JSON strings that are themselves
 * JSON-encoded. This function detects string values that are valid
 * JSON and parses them into native JavaScript objects.
 *
 * @param {any} data - The data to parse. Can be a string, object, or other value.
 * @returns {any} The parsed data with all string values attempted to be JSON-decoded.
 *
 * @example
 * // Input: { message: '{"status": "ok"}' }
 * // Output: { message: { status: 'ok' } }
 * const parsed = parseDoubleEncoded({ message: '{"status": "ok"}' });
 *
 * @example
 * // String that is valid JSON gets parsed
 * // Input: '{"key": "value"}'
 * // Output: { key: 'value' }
 * const parsed = parseDoubleEncoded('{"key": "value"}');
 */
const parseDoubleEncoded = (data: any): any => {
  if (typeof data === 'string') {
    try {
      return JSON.parse(data);
    } catch {
      return data;
    }
  }
  if (typeof data === 'object' && data !== null) {
    for (const key of Object.keys(data)) {
      if (typeof data[key] === 'string') {
        try {
          data[key] = JSON.parse(data[key]);
        } catch {
          // keep as string
        }
      }
    }
  }
  return data;
};

/**
 * Frontend API service module for communicating with the backend MCP server.
 *
 * Provides methods for exporting dashboards, validating imports, managing
 * server configurations, and persisting app settings to localStorage.
 *
 * @namespace api
 *
 * @example
 * // Export a dashboard
 * const result = await api.exportDashboard('production', 42);
 * console.log(result.dashboard.name);
 *
 * @example
 * // Validate import readiness
 * const check = await api.checkImportReady('staging', JSON.stringify(exportData));
 * if (check.can_import) {
 *   console.log('Ready to import');
 * }
 *
 * @example
 * // List available servers
 * const servers = await api.listServers();
 * console.log(servers);
 */
export const api = {
  /**
   * Exports detailed information about a Superset dashboard including charts,
   * datasets, databases, and SQL queries.
   *
   * @param {string} serverId - The ID of the Superset server to query.
   * @param {number} dashboardId - The numeric ID of the dashboard to export.
   * @returns {Promise<ExportResult>} A promise resolving to the full export result containing
   *   dashboard metadata, charts, datasets, databases, tables, and SQL queries.
   *
   * @example
   * const result = await api.exportDashboard('production', 10);
   * console.log(result.dashboard.name);           // "Sales Overview"
   * console.log(result.summary.total_charts);     // 5
   * console.log(result.charts[0].name);           // "Revenue Chart"
   */
  exportDashboard: async (serverId: string, dashboardId: number): Promise<ExportResult> => {
    const data = await callTool('get_dashboard_expert_info', { server_id: serverId, dashboard_id: dashboardId });
    return parseDoubleEncoded(data) as ExportResult;
  },

  /**
   * Validates whether an exported dashboard can be safely imported into a target server.
   *
   * Checks for missing databases, datasets, and chart issues that would block
   * the import. Returns a detailed report with blockers and recommendations.
   *
   * @param {string} targetServerId - The ID of the target Superset server for import.
   * @param {string} exportData - JSON string of the export data to validate.
   * @returns {Promise<ImportCheckResult>} A promise resolving to the import check result
   *   containing can_import flag, detailed checks, blockers, and recommendations.
   *
   * @example
   * const result = await api.checkImportReady('staging', JSON.stringify(exportData));
   * if (result.can_import) {
   *   console.log('Safe to import');
   * } else {
   *   result.blockers.forEach(b => console.log('Blocker:', b));
   * }
   */
  checkImportReady: async (targetServerId: string, exportData: string): Promise<ImportCheckResult> => {
    const data = await callTool('validate_export_file', {
      target_server_id: targetServerId,
      export_data: exportData,
    }, true);
    return parseDoubleEncoded(data) as ImportCheckResult;
  },

  /**
   * Retrieves a list of configured server IDs from the backend.
   *
   * @returns {Promise<string[]>} A promise resolving to an array of server ID strings.
   *
   * @example
   * const servers = await api.listServers();
   * // Returns: ["production", "staging", "development"]
   */
  listServers: async (): Promise<string[]> => {
    const data = await callTool('get_server_configs_json', {});
    return Array.isArray(data) ? data : [];
  },

  /**
   * Fetches full configuration objects for all backend servers.
   *
   * @returns {Promise<Record<string, BackendServerConfig>>} A promise resolving to a record mapping
   *   server IDs to their configuration (base_url, auth_method).
   *
   * @example
   * const configs = await api.getBackendServerConfigs();
   * console.log(configs['production'].base_url);
   * // Returns: "http://prod-server:8000/api"
   */
  getBackendServerConfigs: async (): Promise<Record<string, BackendServerConfig>> => {
    try {
      const data = await callTool('get_server_configs_full', {});
      if (typeof data === 'string') {
        return JSON.parse(data);
      }
      return typeof data === 'object' ? data : {};
    } catch {
      return {};
    }
  },

  /**
   * Lists all available dashboards for a given Superset server.
   *
   * @param {string} serverId - The ID of the Superset server to query.
   * @returns {Promise<DashboardItem[]>} A promise resolving to an array of dashboard items
   *   containing id and dashboard_title for each dashboard.
   *
   * @example
   * const dashboards = await api.listDashboards('production');
   * // Returns: [{ id: 10, dashboard_title: "Sales Overview" }, { id: 11, dashboard_title: "Marketing ROI" }]
   */
  listDashboards: async (serverId: string): Promise<DashboardItem[]> => {
    const data = await callTool('list_dashboards', { server_id: serverId });
    console.log('listDashboards raw data:', data, typeof data);
    let parsedData: any = data;
    if (typeof data === 'string') {
      try {
        parsedData = JSON.parse(data);
        console.log('listDashboards parsed string data:', parsedData);
      } catch {
        console.error('Failed to parse list_dashboards response as JSON');
        return [];
      }
    }
    if (parsedData && parsedData.result && Array.isArray(parsedData.result)) {
      const items = parsedData.result.map((d: any) => ({
        id: d.id,
        dashboard_title: d.dashboard_title,
      }));
      console.log('listDashboards returned items:', items.length);
      return items;
    }
    console.warn('listDashboards: no result array found, structure:', typeof parsedData === 'object' ? Object.keys(parsedData) : parsedData);
    return [];
  },

  /**
   * Loads the application configuration from localStorage.
   *
   * Falls back to default configuration (backend host: localhost, port: 8000,
   * no Superset servers) if no stored config exists.
   *
   * @returns {Promise<AppConfig>} A promise resolving to the application configuration.
   *
   * @example
   * const config = await api.loadConfig();
   * console.log(config.backend.host);  // "localhost"
   * console.log(config.supersetServers);  // Array of server configs
   */
  loadConfig: async (): Promise<AppConfig> => {
    const stored = localStorage.getItem('app_config');
    if (stored) {
      return JSON.parse(stored);
    }
    return {
      backend: { host: 'localhost', port: 8000 },
      supersetServers: [],
    };
  },

  /**
   * Saves the application configuration to localStorage.
   *
   * @param {AppConfig} config - The complete application configuration to persist.
   *
   * @example
   * const config = {
   *   backend: { host: 'localhost', port: 8000 },
   *   supersetServers: [
   *     { id: 'prod', name: 'Production', host: '10.0.0.1', port: 8001, enabled: true }
   *   ]
   * };
   * api.saveConfig(config);
   */
  saveConfig: (config: AppConfig): void => {
     localStorage.setItem('app_config', JSON.stringify(config));
   },

   /**
    * Lists all configured database connections from databases.json.
    *
    * @returns {Promise<DbConnection[]>} A promise resolving to an array of database connections.
    */
   listDatabaseConnections: async (): Promise<DbConnection[]> => {
     const data = await callTool('list_db_connections', {});
     return Array.isArray(data) ? data : [];
   },

   /**
    * Lists all tables in the specified database.
    *
    * @param {string} dbId - Database ID from databases.json.
    * @param {string|null} [schema=null] - Optional schema name (PostgreSQL).
    * @returns {Promise<DbTable[]>} A promise resolving to an array of table objects.
    */
   listDatabaseTables: async (dbId: string, schema?: string): Promise<DbTable[]> => {
     const data = await callTool('list_database_tables', { db_id: dbId, schema: schema || undefined });
     return Array.isArray(data) ? data : [];
   },

   /**
    * Gets column metadata for a table in the specified database.
    *
    * @param {string} dbId - Database ID from databases.json.
    * @param {string} tableName - Table name.
    * @param {string|null} [schema=null] - Optional schema name (PostgreSQL).
    * @returns {Promise<DbColumn[]>} A promise resolving to an array of column definitions.
    */
   getTableColumns: async (dbId: string, tableName: string, schema?: string): Promise<DbColumn[]> => {
     const data = await callTool('get_table_columns', { db_id: dbId, table_name: tableName, schema: schema || undefined });
     return Array.isArray(data) ? data : [];
   },

   /**
    * Inserts rows into a database table with column mapping.
    *
    * @param {string} dbId - Database ID from databases.json.
    * @param {string} tableName - Target table name.
    * @param {string[]} columns - Column names in order matching row data.
    * @param {any[][]} rows - Row data as arrays of values.
    * @param {number} [batchSize=50] - Rows per INSERT batch (recommended max: 200).
    * @param {string|null} [schema=null] - Optional schema name (PostgreSQL).
    * @returns {Promise<BatchInsertResult>} A promise resolving to the insert result.
    */
  batchInsertRows: async (
      dbId: string,
      tableName: string,
      columns: string[],
      rows: any[][],
      batchSize: number = 50,
      schema?: string,
    ): Promise<BatchInsertResult> => {
      const data = await callTool('batch_insert_rows', {
        db_id: dbId,
        table_name: tableName,
        columns,
        rows,
        batch_size: batchSize,
        schema: schema || undefined,
      }, true);
      return parseDoubleEncoded(data) as BatchInsertResult;
    },

    supersetBatchInsertRows: async (
      serverId: string,
      databaseId: number,
      tableName: string,
      columns: string[],
      dataRows: Record<string, any>[],
      batchSize: number = 50,
      schema?: string,
    ): Promise<BatchInsertResult> => {
      const data = await callTool('superset_batch_insert_rows', {
        server_id: serverId,
        database_id: databaseId,
        table_name: tableName,
        columns: JSON.stringify(columns),
        data_rows: JSON.stringify(dataRows),
        batch_size: batchSize,
        schema: schema || undefined,
      }, true);
      return parseDoubleEncoded(data) as BatchInsertResult;
    },

    /**
     * Lists all configured Superset servers.
     *
     * @returns {Promise<SupersetServer[]>} A promise resolving to an array of Superset servers.
     */
    listSupersetServers: async (): Promise<SupersetServer[]> => {
      const data = await callTool('list_superset_servers', {});
      let parsedData: any = data;
      if (typeof data === 'string') {
        try {
          parsedData = JSON.parse(data);
        } catch {
          return [];
        }
      }
      if (parsedData && parsedData.result && Array.isArray(parsedData.result)) {
        return parsedData.result;
      }
      return [];
    },

    /**
     * Lists all databases from a Superset server.
     *
     * @param {string} serverId - The Superset server ID.
     * @returns {Promise<SupersetDb[]>} A promise resolving to an array of databases.
     */
    listSupersetDatabases: async (serverId: string): Promise<SupersetDb[]> => {
      const data = await callTool('list_databases', { server_id: serverId });
      let parsedData: any = data;
      if (typeof data === 'string') {
        try {
          parsedData = JSON.parse(data);
        } catch {
          return [];
        }
      }
      if (parsedData && parsedData.result && Array.isArray(parsedData.result)) {
        return parsedData.result;
      }
      return [];
    },

    /**
     * Gets the database schema from a Superset database.
     *
     * @param {string} serverId - The Superset server ID.
     * @param {number} databaseId - The database ID in Superset.
     * @param {string|null} [schemaName=null] - Optional schema name.
     * @returns {Promise<SupersetSchema>} A promise resolving to the schema data.
     */
    getSupersetDatabaseSchema: async (
      serverId: string,
      databaseId: number,
      schemaName?: string,
    ): Promise<SupersetSchema> => {
      console.log('[API] Calling superset_get_database_schema with:', { serverId, databaseId, schemaName });
      const data = await callTool('superset_get_database_schema', {
        server_id: serverId,
        database_id: databaseId,
        schema_name: schemaName || undefined,
      });
      console.log('[API] Raw callTool response:', typeof data, JSON.stringify(data).substring(0, 200));
      let parsedData: any = data;
      if (typeof data === 'string') {
        try {
          parsedData = JSON.parse(data);
          console.log('[API] After JSON.parse, parsedData type:', typeof parsedData, 'keys:', Object.keys(parsedData).slice(0, 5));
        } catch {
          return { database_id: databaseId, database_name: '', engine: '', tables: [] };
        }
      }
      if (parsedData && parsedData.result) {
        console.log('[API] Returning parsedData.result');
        return parsedData.result;
      }
      if (parsedData && parsedData.database_id) {
        console.log('[API] Returning parsedData directly with database_id:', parsedData.database_id, 'tables:', parsedData.tables?.length);
        return parsedData;
      }
      console.log('[API] Fallback - returning empty schema');
      return { database_id: databaseId, database_name: '', engine: '', tables: [] };
    },
};
