(function () {
  if (typeof window.__TAURI__ === 'undefined' || !window.__TAURI__.core) return;
  if (window.electronAPI) return;
  const invoke = window.__TAURI__.core.invoke;
  if (!invoke) return;
  window.electronAPI = {
    getBackendUrl: () => invoke('get_backend_url'),
    getProjectPath: () => invoke('get_project_path'),
    getLogPath: () => invoke('get_log_path'),
    getLogDir: () => invoke('get_log_dir'),
    setLogDir: (dir) => invoke('set_log_dir', { dir: dir || null }),
    getTheme: () => invoke('get_theme'),
    setTheme: (theme) => invoke('set_theme', { theme }),
    readLogs: (type) => invoke('read_logs', { logType: type }),
    openFolder: () => invoke('open_folder'),
    openPath: (path) => invoke('open_path', { path }),
    openFile: () => invoke('open_file'),
    openImage: () => invoke('open_image'),
    saveFile: (defaultName, content) => invoke('save_file', { defaultName, content }),
    setProjectPath: (p) => invoke('set_project_path', { path: p }),
    onProjectPath: (cb) => {
      window.addEventListener('project-path', (e) => cb(e.detail));
    },
    onRequestOpenFolder: (cb) => {
      window.addEventListener('request-open-folder', () => cb());
    },
    onNavNewChat: (cb) => {
      window.addEventListener('nav-new-chat', () => cb());
    },
    splashRetry: () => invoke('retry_backend'),
    splashExit: () => { if (window.__TAURI__?.core?.exit) window.__TAURI__.core.exit(0); },
    splashChoosePython: () => invoke('retry_backend'),
    retryBackend: () => invoke('retry_backend'),
    getLLMProvider: () => invoke('get_llm_provider'),
    getLLMConfig: () => invoke('get_llm_config'),
    setLLMProvider: (p) => invoke('set_llm_provider', { provider: p }),
    setLLMConfig: (cfg) => invoke('set_llm_config', { cfg }),
    restartBackend: () => invoke('restart_backend')
  };
})();
