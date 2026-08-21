import type {
  ExportResult,
  ImportCheckResult,
  DashboardItem,
  AppConfig,
} from '../types';

interface BackendServerConfig {
  base_url: string;
  auth_method: string;
}

const getBackendUrl = (): string => {
  const envUrl = import.meta.env.VITE_BACKEND_URL;
  if (envUrl) return envUrl;
  if (window.location.port === '8080' || import.meta.env.DEV) {
    return 'http://host.docker.internal:8000';
  }
  return '';
};

const buildQueryString = (params: Record<string, any>): string => {
  return Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(typeof v === 'object' ? JSON.stringify(v) : v)}`)
    .join('&');
};

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
  try {
    return JSON.parse(text);
  } catch {
    return { result: text };
  }
};

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

export const api = {
  exportDashboard: async (serverId: string, dashboardId: number): Promise<ExportResult> => {
    const data = await callTool('get_dashboard_expert_info', { server_id: serverId, dashboard_id: dashboardId });
    return parseDoubleEncoded(data) as ExportResult;
  },

  checkImportReady: async (targetServerId: string, exportData: string): Promise<ImportCheckResult> => {
    const data = await callTool('validate_export_file', {
      target_server_id: targetServerId,
      export_data: exportData,
    }, true);
    return parseDoubleEncoded(data) as ImportCheckResult;
  },

  listServers: async (): Promise<string[]> => {
    const data = await callTool('get_server_configs_json', {});
    return Array.isArray(data) ? data : [];
  },

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

  saveConfig: (config: AppConfig): void => {
    localStorage.setItem('app_config', JSON.stringify(config));
  },
};
