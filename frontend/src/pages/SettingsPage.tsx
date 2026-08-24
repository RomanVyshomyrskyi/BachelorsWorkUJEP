/**
 * @module pages/SettingsPage
 * @description Application settings page for managing backend and Superset server configurations.
 * Provides UI for adding, editing, deleting, and enabling/disabling Superset servers,
 * as well as configuring the backend API connection.
 */

import { useState, useEffect } from 'react';
import type { SupersetServerConfig, AppConfig } from '../types';
import { api } from '../api/service';
import toast from 'react-hot-toast';

/**
 * Settings page component for application configuration.
 *
 * Features:
 * - Backend configuration: Edit backend host and port
 * - Superset servers: List, add, edit, delete, enable/disable servers
 * - Server form: Add new or edit existing server with validation
 *
 * State:
 * - config: Current application configuration (backend + servers)
 * - editingServer: ID of the server currently being edited (null if none)
 * - isAdding: Whether the form is in "add new server" mode
 * - loading: Whether data is being loaded from backend
 * - formData: Current form values for add/edit server
 *
 * @component
 * @returns {JSX.Element} The settings page with configuration UI.
 *
 * @example
 * // Used in App.tsx routing
 * <Route path="/settings" element={<SettingsPage />} />
 */
function SettingsPage() {
  const [config, setConfig] = useState<AppConfig>({
    backend: { host: 'localhost', port: 8000 },
    supersetServers: [],
  });
  const [editingServer, setEditingServer] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    host: 'localhost',
    port: '8001',
    enabled: true,
  });

  /**
   * Loads configuration on initial mount.
   */
  useEffect(() => {
    loadConfig();
  }, []);

  /**
   * Loads configuration from localStorage and merges with backend server configs.
   *
   * Backend-discovered servers are prepended to custom servers in the list.
   *
   * @async
   * @returns {Promise<void>}
   */
  const loadConfig = async () => {
    setLoading(true);
    const cfg = await api.loadConfig();
    try {
      const backendServers = await api.getBackendServerConfigs();
      console.log('Backend servers:', backendServers);
      const mergedServers: SupersetServerConfig[] = Object.entries(backendServers).map(([id, scfg]) => ({
        id,
        name: id,
        host: scfg.base_url.replace(/^https?:\/\//, '').replace(/\/.*$/, ''),
        port: 8001,
        enabled: true,
      }));
      console.log('Merged servers:', mergedServers);
      setConfig({
        ...cfg,
        supersetServers: [...mergedServers, ...cfg.supersetServers],
      });
    } catch (err) {
      console.error('Failed to load backend servers:', err);
      setConfig(cfg);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Resets the form for adding a new server.
   *
   * Clears editing state and sets default form values.
   */
  const handleAddServer = () => {
    setFormData({ id: '', name: '', host: 'localhost', port: '8001', enabled: true });
    setEditingServer(null);
    setIsAdding(true);
  };

  /**
   * Populates the form with an existing server's data for editing.
   *
   * @param {SupersetServerConfig} server - The server to edit.
   */
  const handleEditServer = (server: SupersetServerConfig) => {
    setFormData({
      id: server.id,
      name: server.name,
      host: server.host,
      port: String(server.port),
      enabled: server.enabled,
    });
    setEditingServer(server.id);
    setIsAdding(false);
  };

  /**
   * Deletes a server from the configuration after user confirmation.
   *
   * @param {string} id - The ID of the server to delete.
   */
  const handleDeleteServer = (id: string) => {
    if (!confirm(`Delete server "${id}"?`)) return;
    const updated = { ...config, supersetServers: config.supersetServers.filter(s => s.id !== id) };
    setConfig(updated);
    api.saveConfig(updated);
    toast.success('Server deleted');
  };

  /**
   * Saves the current form data as a new or updated server.
   *
   * Validates required fields (id, name, host) before saving.
   * Shows toast notification on success.
   */
  const handleSaveServer = () => {
    if (!formData.id || !formData.name || !formData.host) {
      toast.error('Please fill in all required fields');
      return;
    }

    const newServer: SupersetServerConfig = {
      id: formData.id,
      name: formData.name,
      host: formData.host,
      port: parseInt(formData.port) || 8001,
      enabled: formData.enabled,
    };

    let updated: AppConfig;
    if (isAdding) {
      updated = {
        ...config,
        supersetServers: [...config.supersetServers, newServer],
      };
    } else {
      updated = {
        ...config,
        supersetServers: config.supersetServers.map(s =>
          s.id === editingServer ? newServer : s
        ),
      };
    }

    setConfig(updated);
    api.saveConfig(updated);
    setIsAdding(false);
    setEditingServer(null);
    toast.success(isAdding ? 'Server added' : 'Server updated');
  };

  /**
   * Cancels the add/edit form and resets form state.
   */
  const handleCancel = () => {
    setIsAdding(false);
    setEditingServer(null);
  };

  /**
   * Toggles the enabled status of a server.
   *
   * @param {string} id - The ID of the server to toggle.
   */
  const toggleServer = (id: string) => {
    const updated = {
      ...config,
      supersetServers: config.supersetServers.map(s =>
        s.id === id ? { ...s, enabled: !s.enabled } : s
      ),
    };
    setConfig(updated);
    api.saveConfig(updated);
  };

  return (
    <div>
      <h1 className="page-title">Settings</h1>

      <div className="card">
        <div className="card-title">Backend Configuration</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div className="form-group">
            <label className="form-label">Backend Host</label>
            <input
              className="form-input"
              value={config.backend.host}
              onChange={(e) => setConfig({ ...config, backend: { ...config.backend, host: e.target.value } })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Backend Port</label>
            <input
              className="form-input"
              type="number"
              value={config.backend.port}
              onChange={(e) => setConfig({ ...config, backend: { ...config.backend, port: parseInt(e.target.value) } })}
            />
          </div>
        </div>
        <div className="actions-row">
          <button className="btn btn-primary" onClick={() => api.saveConfig(config)}>
            Save Backend Config
          </button>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div className="card-title" style={{ marginBottom: 0 }}>Superset Servers ({config.supersetServers.length})</div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-outline btn-sm" onClick={loadConfig} disabled={loading}>
              {loading ? 'Loading...' : '↻ Refresh'}
            </button>
            <button className="btn btn-primary btn-sm" onClick={handleAddServer}>
              + Add Server
            </button>
          </div>
        </div>

        {config.supersetServers.length === 0 && (
          <div className="empty-state" style={{ padding: '2rem 1rem' }}>
            <div className="empty-state-icon">🖥️</div>
            <div className="empty-state-text">No Superset servers configured</div>
            <div className="empty-state-sub">Click "Refresh" to load backend servers or "Add Server" to configure manually</div>
          </div>
        )}

        {config.supersetServers.map(server => (
          <div key={server.id} className="server-card">
            <div className="server-card-info">
              <div className="server-card-name">{server.name}</div>
              <div className="server-card-url">{server.host}:{server.port}</div>
            </div>
            <div className="server-card-actions">
              <button
                className={`btn btn-sm ${server.enabled ? 'btn-success' : 'btn-outline'}`}
                onClick={() => toggleServer(server.id)}
              >
                {server.enabled ? 'Enabled' : 'Disabled'}
              </button>
              <button className="btn btn-sm btn-outline" onClick={() => handleEditServer(server)}>
                Edit
              </button>
              <button className="btn btn-sm btn-danger" onClick={() => handleDeleteServer(server.id)}>
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {(isAdding || editingServer) && (
        <div className="card" style={{ borderTop: '3px solid var(--accent)' }}>
          <div className="card-title">
            {isAdding ? 'Add New Server' : `Edit Server: ${formData.id}`}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Server ID *</label>
              <input
                className="form-input"
                value={formData.id}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                placeholder="e.g., production, staging"
                disabled={!isAdding}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Display Name *</label>
              <input
                className="form-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Production Superset"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Host *</label>
              <input
                className="form-input"
                value={formData.host}
                onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                placeholder="e.g., 127.0.0.1"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Port</label>
              <input
                className="form-input"
                type="number"
                value={formData.port}
                onChange={(e) => setFormData({ ...formData, port: e.target.value })}
                placeholder="8001"
              />
            </div>
            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                />
                <span className="form-label" style={{ marginBottom: 0 }}>Enabled</span>
              </label>
            </div>
          </div>
          <div className="actions-row">
            <button className="btn btn-success" onClick={handleSaveServer}>
              {isAdding ? 'Add Server' : 'Save Changes'}
            </button>
            <button className="btn btn-outline" onClick={handleCancel}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SettingsPage;
