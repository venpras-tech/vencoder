import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import App from './App';
import { AppProvider } from './context/AppContext';
import { tauriAPI } from './utils/tauriAPI';
import { electronAPI } from './utils/electronAPI';
import './styles/index.css';

function isTauriRuntime() {
  if (typeof window === 'undefined') return false;
  return Boolean(window.__TAURI__ || window.__TAURI_INTERNALS__);
}

if (typeof window !== 'undefined') {
  if (isTauriRuntime()) {
    window.electronAPI = tauriAPI;
  } else if (!window.electronAPI) {
    window.electronAPI = electronAPI;
  }
}

const Router = isTauriRuntime() ? HashRouter : BrowserRouter;

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            padding: 24,
            fontFamily: 'system-ui, sans-serif',
            maxWidth: 560,
            margin: '48px auto',
            color: '#0f172a',
          }}
        >
          <h1 style={{ fontSize: '1.25rem', margin: '0 0 12px' }}>Something went wrong</h1>
          <pre
            style={{
              fontSize: 13,
              overflow: 'auto',
              background: '#f1f5f9',
              padding: 12,
              borderRadius: 8,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {this.state.error?.message || String(this.state.error)}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

const rootEl = document.getElementById('root');
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <RootErrorBoundary>
        <Router>
          <AppProvider>
            <App />
          </AppProvider>
        </Router>
      </RootErrorBoundary>
    </React.StrictMode>
  );
}
