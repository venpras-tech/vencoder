import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import './StatusBanners.css';

function StatusBanners() {
  const { backendConnected, setBackendConnected, setModelInfo, baseUrl } = useApp();
  const [connecting, setConnecting] = useState(true);
  const [downloadStatus, setDownloadStatus] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function checkBackend() {
      try {
        const r = await fetch(baseUrl + '/health');
        if (r.ok && mounted) {
          const data = await r.json();
          const ok = data.ollama === true && data.model_available !== false;
          setBackendConnected(ok);
          if (data.model) {
            setModelInfo(data.model, data.provider || 'Ollama');
          }
          setConnecting(false);
        }
      } catch {
        if (mounted) {
          setBackendConnected(false);
          setConnecting(false);
        }
      }
    }

    checkBackend();
    const interval = setInterval(checkBackend, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [baseUrl, setBackendConnected, setModelInfo]);

  return (
    <>
      {connecting && (
        <div className="connecting-banner" role="status">
          <span className="connecting-spinner" aria-hidden="true" />
          <span className="connecting-text">Starting backend…</span>
        </div>
      )}

      {downloadStatus && (
        <div className="download-status-bar" role="status">
          <span className="download-status-spinner" aria-hidden="true" />
          <span className="download-status-text">{downloadStatus.text}</span>
          {downloadStatus.progress !== undefined && (
            <div className="download-status-progress">
              <div
                className="download-status-progress-bar"
                style={{ width: `${downloadStatus.progress}%` }}
              />
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default StatusBanners;
