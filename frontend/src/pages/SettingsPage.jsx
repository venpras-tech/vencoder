import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import './SettingsPage.css';

function SettingsPage() {
  const { theme, setTheme, baseUrl } = useApp();
  const [activeSection, setActiveSection] = useState('general');
  const [logPath, setLogPath] = useState('');
  const [temperature, setTemperature] = useState('');
  const [numPredict, setNumPredict] = useState('');
  const [mcpJson, setMcpJson] = useState('[]');
  const [mcpStatus, setMcpStatus] = useState('');

  const handleThemeChange = (newTheme) => {
    setTheme(newTheme);
  };

  const handleBrowseLogPath = async () => {
    if (window.electronAPI?.openDirectory) {
      const path = await window.electronAPI.openDirectory();
      if (path) setLogPath(path);
    }
  };

  useEffect(() => {
    if (activeSection !== 'mcp') return;
    let cancelled = false;
    (async () => {
      setMcpStatus('');
      try {
        const r = await fetch(`${baseUrl.replace(/\/$/, '')}/mcp/external`);
        if (!r.ok || cancelled) return;
        const data = await r.json();
        const servers = Array.isArray(data.servers) ? data.servers : [];
        if (!cancelled) setMcpJson(JSON.stringify(servers, null, 2));
      } catch {
        if (!cancelled) setMcpStatus('Could not load MCP config (backend unreachable).');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeSection, baseUrl]);

  const handleMcpSave = async () => {
    setMcpStatus('');
    let parsed;
    try {
      parsed = JSON.parse((mcpJson || '').trim() || '[]');
    } catch {
      setMcpStatus('Invalid JSON.');
      return;
    }
    if (!Array.isArray(parsed)) {
      setMcpStatus('JSON must be an array of server objects.');
      return;
    }
    try {
      const r = await fetch(`${baseUrl.replace(/\/$/, '')}/mcp/external`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ servers: parsed }),
      });
      setMcpStatus(r.ok ? 'Saved. Restart the backend if it is already running.' : 'Save failed.');
    } catch {
      setMcpStatus('Save failed (network error).');
    }
  };

  const handleMcpRefresh = async () => {
    setMcpStatus('');
    try {
      const r = await fetch(`${baseUrl.replace(/\/$/, '')}/mcp/external`);
      if (!r.ok) {
        setMcpStatus('Refresh failed.');
        return;
      }
      const data = await r.json();
      const servers = Array.isArray(data.servers) ? data.servers : [];
      setMcpJson(JSON.stringify(servers, null, 2));
      setMcpStatus('Reloaded.');
    } catch {
      setMcpStatus('Refresh failed.');
    }
  };

  const handleLLMParamsApply = async () => {
    try {
      const cfg = {};
      if (temperature) cfg.temperature = parseFloat(temperature);
      if (numPredict) cfg.numPredict = parseInt(numPredict, 10);
      
      if (window.electronAPI?.setLLMConfig) {
        await window.electronAPI.setLLMConfig(cfg);
        if (window.electronAPI?.restartBackend) {
          await window.electronAPI.restartBackend();
        }
      }
    } catch (err) {
      console.error('Failed to apply LLM params:', err);
    }
  };

  return (
    <div className="settings-view">
      <h2 className="settings-title">Settings</h2>
      <div className="settings-layout">
        <nav className="settings-nav" role="tablist">
          <button
            type="button"
            className={`settings-nav-item ${activeSection === 'general' ? 'active' : ''}`}
            onClick={() => setActiveSection('general')}
            role="tab"
          >
            General
          </button>
          <button
            type="button"
            className={`settings-nav-item ${activeSection === 'llm' ? 'active' : ''}`}
            onClick={() => setActiveSection('llm')}
            role="tab"
          >
            LLM
          </button>
          <button
            type="button"
            className={`settings-nav-item ${activeSection === 'mcp' ? 'active' : ''}`}
            onClick={() => setActiveSection('mcp')}
            role="tab"
          >
            MCP
          </button>
        </nav>
        <div className="settings-panels">
          {activeSection === 'general' && (
            <div className="settings-panel active">
              <h3 className="settings-panel-heading">General</h3>
              <div className="settings-field">
                <label className="settings-label">Theme</label>
                <div className="settings-theme-options">
                  <label className="settings-radio">
                    <input
                      type="radio"
                      name="theme"
                      value="light"
                      checked={theme === 'light'}
                      onChange={() => handleThemeChange('light')}
                    />
                    <span>Light</span>
                  </label>
                  <label className="settings-radio">
                    <input
                      type="radio"
                      name="theme"
                      value="dark"
                      checked={theme === 'dark'}
                      onChange={() => handleThemeChange('dark')}
                    />
                    <span>Dark</span>
                  </label>
                  <label className="settings-radio">
                    <input
                      type="radio"
                      name="theme"
                      value="system"
                      checked={theme === 'system'}
                      onChange={() => handleThemeChange('system')}
                    />
                    <span>System</span>
                  </label>
                  <label className="settings-radio">
                    <input
                      type="radio"
                      name="theme"
                      value="high-contrast"
                      checked={theme === 'high-contrast'}
                      onChange={() => handleThemeChange('high-contrast')}
                    />
                    <span>High contrast</span>
                  </label>
                </div>
                <p className="settings-hint">
                  System follows your OS appearance. High contrast increases contrast for accessibility.
                </p>
              </div>
              <div className="settings-field">
                <label className="settings-label" htmlFor="log-path-input">Log path</label>
                <div className="settings-input-row">
                  <input
                    type="text"
                    id="log-path-input"
                    className="settings-input"
                    placeholder="Default location"
                    value={logPath}
                    onChange={(e) => setLogPath(e.target.value)}
                  />
                  <button type="button" className="btn-browse" onClick={handleBrowseLogPath}>
                    Browse
                  </button>
                </div>
                <p className="settings-hint">
                  Folder where app.log is stored. Leave empty for default.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'llm' && (
            <div className="settings-panel active">
              <h3 className="settings-panel-heading">LLM parameters</h3>
              <p className="settings-hint settings-hint-llm">
                Temperature and max tokens apply to all providers. Restart backend to apply changes.
              </p>
              <div className="settings-llm-grid">
                <div className="settings-llm-item">
                  <label className="settings-llm-label" htmlFor="setting-temperature">Temperature</label>
                  <input
                    type="number"
                    id="setting-temperature"
                    className="settings-input settings-input-num"
                    min="0"
                    max="2"
                    step="0.05"
                    placeholder="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                  />
                  <span className="settings-llm-default">Default: 0.1</span>
                </div>
                <div className="settings-llm-item">
                  <label className="settings-llm-label" htmlFor="setting-num-predict">Max tokens</label>
                  <input
                    type="number"
                    id="setting-num-predict"
                    className="settings-input settings-input-num"
                    min="0"
                    max="65536"
                    step="1"
                    placeholder="0"
                    value={numPredict}
                    onChange={(e) => setNumPredict(e.target.value)}
                  />
                  <span className="settings-llm-default">Default: 0 (unlimited)</span>
                </div>
              </div>
              <div className="settings-input-row">
                <button type="button" className="btn-browse btn-apply" onClick={handleLLMParamsApply}>
                  Apply
                </button>
              </div>
            </div>
          )}

          {activeSection === 'mcp' && (
            <div className="settings-panel active">
              <h3 className="settings-panel-heading">MCP (Model Context Protocol)</h3>
              <p className="settings-hint settings-hint-mcp">
                External stdio MCP servers for the agent (same as the Electron app). JSON array of objects with{' '}
                <code>id</code>, <code>command</code>, <code>args</code>, and optional <code>env</code> / <code>cwd</code>.
                Saved to the backend via <code>/mcp/external</code>.
              </p>
              <label className="settings-label" htmlFor="setting-mcp-external-json">
                External MCP servers (JSON array)
              </label>
              <textarea
                id="setting-mcp-external-json"
                className="settings-mcp-textarea"
                rows={12}
                spellCheck={false}
                value={mcpJson}
                onChange={(e) => setMcpJson(e.target.value)}
                placeholder='[{"id":"example","command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/path"]}]'
              />
              <div className="settings-input-row">
                <button type="button" className="btn-browse btn-apply" onClick={handleMcpSave}>
                  Save MCP settings
                </button>
                <button type="button" className="btn-browse" onClick={handleMcpRefresh}>
                  Reload from backend
                </button>
              </div>
              {mcpStatus ? (
                <p className="settings-hint settings-mcp-status-line" role="status">
                  {mcpStatus}
                </p>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;
