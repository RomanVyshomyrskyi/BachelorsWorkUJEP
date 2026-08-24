/**
 * @module pages/DashboardPage
 * @description Main dashboard management page with export and import functionality.
 * Provides UI for selecting servers, exporting dashboards, loading export files,
 * and checking import readiness.
 */

import { useState, useEffect } from 'react';
import type { ExportResult, ImportCheckResult, DashboardItem } from '../types';
import { api } from '../api/service';
import SummaryCards from '../components/SummaryCards';
import ExportResults from '../components/ExportResults';
import ImportResults from '../components/ImportResults';

/**
 * Dashboard management page component with export and import tabs.
 *
 * Features:
 * - Export tab: Select a server and dashboard, export to JSON, download results
 * - Import tab: Load a JSON export file, select target server, check import readiness
 *
 * State:
 * - servers: Merged list of custom and backend Superset servers
 * - selectedServer: Currently selected source server ID
 * - dashboards: List of dashboards on the selected server
 * - selectedDashboard: Currently selected dashboard ID
 * - exportData: Result of the last export operation
 * - importCheckData: Result of the last import readiness check
 * - loading: Current loading state ('servers' | 'dashboards' | 'export' | 'import' | '')
 * - importFile: Selected file for import
 * - importFileData: Parsed JSON data from the import file
 * - importTargetServer: Target server ID for import check
 * - activeTab: Currently active tab ('export' | 'import')
 *
 * @component
 * @returns {JSX.Element} The dashboard management page with export/import UI.
 *
 * @example
 * // Used in App.tsx routing
 * <Route path="/" element={<DashboardPage />} />
 */
function DashboardPage() {
  const [servers, setServers] = useState<Array<{id: string; name: string; host: string; port: number; enabled: boolean}>>([]);
  const [selectedServer, setSelectedServer] = useState<string>('');
  const [dashboards, setDashboards] = useState<DashboardItem[]>([]);
  const [selectedDashboard, setSelectedDashboard] = useState<string>('');
  const [exportData, setExportData] = useState<ExportResult | null>(null);
  const [importCheckData, setImportCheckData] = useState<ImportCheckResult | null>(null);
  const [loading, setLoading] = useState<string>('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importFileData, setImportFileData] = useState<ExportResult | null>(null);
  const [importTargetServer, setImportTargetServer] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'export' | 'import'>('export');

  /**
   * Loads servers on initial mount.
   * Merges custom servers from config with backend-discovered servers.
   */
  useEffect(() => {
    loadServers();
  }, []);

  /**
   * Loads dashboards when selected server changes.
   * Resets export/import state when server changes.
   */
  useEffect(() => {
    if (selectedServer && servers.length > 0) {
      const server = servers.find(s => s.id === selectedServer);
      if (server) {
        loadDashboards(server.id);
      }
    }
  }, [selectedServer]);

  /**
   * Loads and merges server configurations from localStorage and backend.
   *
   * Custom servers from config take precedence over backend-discovered servers.
   * Backend servers are added only if not already present in custom config.
   *
   * @async
   * @returns {Promise<void>}
   */
  const loadServers = async () => {
    setLoading('servers');
    try {
      const config = await api.loadConfig();
      const customServers = config.supersetServers.filter(s => s.enabled);
      const backendServers = await api.getBackendServerConfigs();

      const merged = new Map<string, {id: string; name: string; host: string; port: number; enabled: boolean}>();

      for (const s of customServers) {
        merged.set(s.id, {
          id: s.id,
          name: s.name,
          host: s.host,
          port: s.port,
          enabled: true,
        });
      }

      for (const [id, info] of Object.entries(backendServers)) {
        if (!merged.has(id)) {
          const url = new URL(info.base_url);
          merged.set(id, {
            id,
            name: `${id} (backend)`,
            host: url.hostname,
            port: url.port ? parseInt(url.port) : 80,
            enabled: true,
          });
        }
      }

      setServers(Array.from(merged.values()));
    } catch (error) {
      console.error('Failed to load servers:', error);
    } finally {
      setLoading('');
    }
  };

  /**
   * Loads dashboards for the specified server.
   *
   * Resets all export/import state when switching servers.
   *
   * @async
   * @param {string} serverId - The ID of the server to load dashboards for.
   * @returns {Promise<void>}
   */
  const loadDashboards = async (serverId: string) => {
    setLoading('dashboards');
    try {
      const items = await api.listDashboards(serverId);
      setDashboards(items);
      setSelectedDashboard('');
      setExportData(null);
      setImportCheckData(null);
      setImportFileData(null);
    } catch (error) {
      console.error('Failed to load dashboards:', error);
    } finally {
      setLoading('');
    }
  };

  /**
   * Exports the selected dashboard from the selected server.
   *
   * Fetches dashboard details including charts, datasets, databases, and SQL queries.
   * Sets both exportData and importFileData so the export can be immediately used for import.
   *
   * @async
   * @returns {Promise<void>}
   */
  const handleExport = async () => {
    if (!selectedServer || !selectedDashboard) return;
    setLoading('export');
    try {
      const result = await api.exportDashboard(selectedServer, parseInt(selectedDashboard));
      setExportData(result);
      setImportFileData(result);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setLoading('');
    }
  };

  /**
   * Handles file selection for import.
   *
   * Reads the selected JSON file and parses it into ExportResult format.
   * Resets export and import check state when a new file is loaded.
   *
   * @param {React.ChangeEvent<HTMLInputElement>} event - The file input change event.
   */
  const handleFileLoad = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setImportFile(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target?.result as string);
        setImportFileData(json);
        setExportData(null);
        setImportCheckData(null);
      } catch {
        alert('Invalid JSON file');
      }
    };
    reader.readAsText(file);
  };

  /**
   * Checks import readiness for the loaded export file against the target server.
   *
   * Sends the export data to the backend for validation and displays
   * blockers, recommendations, and detailed check results.
   *
   * @async
   * @returns {Promise<void>}
   */
  const handleImportCheck = async () => {
    if (!importFileData || !importTargetServer) return;
    setLoading('import');
    try {
      const exportJson = JSON.stringify(importFileData);
      const result = await api.checkImportReady(importTargetServer, exportJson);
      setImportCheckData(result);
    } catch (error) {
      console.error('Import check failed:', error);
    } finally {
      setLoading('');
    }
  };

  /**
   * Downloads data as a JSON file.
   *
   * Creates a Blob from the JSON data, generates a temporary download link,
   * triggers the download, and cleans up the object URL.
   *
   * @param {any} data - The data to serialize and download.
   * @param {string} filename - The filename for the downloaded file.
   */
  const downloadJson = (data: any, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const selectedDashboardItem = dashboards.find(d => String(d.id) === selectedDashboard);

  return (
    <div>
      <h1 className="page-title">Dashboard Manager</h1>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'export' ? 'active' : ''}`}
          onClick={() => setActiveTab('export')}
        >
          Export
        </button>
        <button
          className={`tab ${activeTab === 'import' ? 'active' : ''}`}
          onClick={() => setActiveTab('import')}
        >
          Import
        </button>
      </div>

      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Loading...</span>
        </div>
      )}

      {activeTab === 'export' && (
        <div>
          <div className="card">
            <div className="card-title">Select Source</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Superset Server</label>
                <select
                  className="form-select"
                  value={selectedServer}
                  onChange={(e) => setSelectedServer(e.target.value)}
                  disabled={loading !== ''}
                >
                  <option value="">Select a server...</option>
                  {servers.map(s => (
                    <option key={s.id} value={s.id}>{s.name} ({s.host})</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Dashboard</label>
                <select
                  className="form-select"
                  value={selectedDashboard}
                  onChange={(e) => setSelectedDashboard(e.target.value)}
                  disabled={!selectedServer || loading !== ''}
                >
                  <option value="">Select a dashboard...</option>
                  {dashboards.map(d => (
                    <option key={d.id} value={d.id}>{d.dashboard_title}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="actions-row">
              <button
                className="btn btn-primary btn-lg"
                onClick={handleExport}
                disabled={!selectedServer || !selectedDashboard || loading !== ''}
              >
                Export Dashboard
              </button>
            </div>
          </div>

          {exportData && (
            <div className="results-container">
              <SummaryCards summary={exportData.summary} dashboard={exportData.dashboard} />
              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <button
                  className="btn btn-success"
                  onClick={() => downloadJson(exportData, `dashboard-${exportData.dashboard.id}-export.json`)}
                >
                  Download JSON
                </button>
              </div>
              <ExportResults data={exportData} />
            </div>
          )}

          {!exportData && !loading && selectedDashboardItem && (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <div className="empty-state-text">Select a dashboard and click Export</div>
              <div className="empty-state-sub">
                Selected: {selectedDashboardItem.dashboard_title}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'import' && (
        <div>
          <div className="card">
            <div className="card-title">Load Dashboard Export</div>
            <div className="file-input-wrapper">
              <label className="btn btn-outline btn-lg" style={{ width: '100%', display: 'inline-flex', cursor: 'pointer' }}>
                {importFile ? `Selected: ${importFile.name}` : 'Choose JSON File'}
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileLoad}
                  disabled={loading !== ''}
                  style={{ position: 'absolute', opacity: 0, width: '100%', height: '100%', cursor: 'pointer', zIndex: 1 }}
                />
              </label>
            </div>
          </div>

          {importFileData && (
            <div className="card">
              <div className="card-title">Import Configuration</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Source (this export)</label>
                  <div className="form-input" style={{ background: '#f8f9fa' }}>
                    {importFileData.dashboard.name}
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Target Superset Server</label>
                  <select
                    className="form-select"
                    value={importTargetServer}
                    onChange={(e) => setImportTargetServer(e.target.value)}
                    disabled={loading !== ''}
                  >
                    <option value="">Select target server...</option>
                    {servers.map(s => (
                      <option key={s.id} value={s.id}>{s.name} ({s.host})</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="actions-row">
                <button
                  className="btn btn-primary btn-lg"
                  onClick={handleImportCheck}
                  disabled={!importTargetServer || loading !== ''}
                >
                  Check Import Readiness
                </button>
              </div>
            </div>
          )}

          {importCheckData && (
            <div className="results-container">
              <ImportResults data={importCheckData} />
            </div>
          )}

          {!importFileData && !loading && (
            <div className="empty-state">
              <div className="empty-state-icon">📁</div>
              <div className="empty-state-text">Load a dashboard export file to check import readiness</div>
              <div className="empty-state-sub">Upload a JSON file exported from another Superset instance</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default DashboardPage;
