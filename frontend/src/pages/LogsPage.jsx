import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import './LogsPage.css';

const logTypes = [
  { id: 'backend', label: 'Backend' },
  { id: 'agent', label: 'Agent / LLM' },
  { id: 'app', label: 'Application' },
  { id: 'ui', label: 'UI' },
];

function LogsPage() {
  const { baseUrl } = useApp();
  const [logsType, setLogsType] = useState('backend');
  const [logs, setLogs] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadLogs();
  }, [logsType]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${baseUrl}/logs/${logsType}`);
      if (r.ok) {
        const data = await r.text();
        setLogs(data.split('\n').filter(Boolean));
      }
    } catch {
      console.error('Failed to load logs');
    }
    setLoading(false);
  };

  const handleCopy = () => {
    const text = filteredLogs.join('\n');
    navigator.clipboard.writeText(text);
  };

  const filteredLogs = searchQuery
    ? logs.filter((log) => log.toLowerCase().includes(searchQuery.toLowerCase()))
    : logs;

  const getLogClass = (line) => {
    if (line.includes('ERROR') || line.includes('error')) return 'log-error';
    if (line.includes('WARNING') || line.includes('warn')) return 'log-warning';
    if (line.includes('INFO')) return 'log-info';
    if (line.includes('DEBUG')) return 'log-debug';
    if (line.includes('Traceback')) return 'log-traceback';
    return '';
  };

  return (
    <div className="logs-view">
      <div className="logs-header">
        <h2 className="logs-title">Logs</h2>
        <div className="logs-controls">
          <div className="logs-tabs">
            {logTypes.map((type) => (
              <button
                key={type.id}
                type="button"
                className={`logs-tab ${logsType === type.id ? 'active' : ''}`}
                onClick={() => setLogsType(type.id)}
              >
                {type.label}
              </button>
            ))}
          </div>
          <div className="logs-actions">
            <input
              type="text"
              className="logs-search"
              placeholder="Search logs…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              maxLength={200}
            />
            <button type="button" className="btn-refresh-logs" onClick={loadLogs}>
              Refresh
            </button>
            <button type="button" className="btn-copy-logs" onClick={handleCopy}>
              Copy
            </button>
          </div>
        </div>
      </div>
      <div className="logs-content-wrap">
        <div className="logs-content">
          {loading ? (
            <div className="log-line log-empty">Loading...</div>
          ) : filteredLogs.length === 0 ? (
            <div className="log-line log-empty">No logs available</div>
          ) : (
            filteredLogs.map((line, index) => (
              <div key={index} className={`log-line ${getLogClass(line)}`}>
                {line}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default LogsPage;
