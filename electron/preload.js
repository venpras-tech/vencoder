const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  getProjectPath: () => ipcRenderer.invoke('get-project-path'),
  getLogPath: () => ipcRenderer.invoke('get-log-path'),
  getLogDir: () => ipcRenderer.invoke('get-log-dir'),
  setLogDir: (dir) => ipcRenderer.invoke('set-log-dir', dir),
  getTheme: () => ipcRenderer.invoke('get-theme'),
  setTheme: (theme) => ipcRenderer.invoke('set-theme', theme),
  readLogs: (type) => ipcRenderer.invoke('read-logs', type),
  openFolder: () => ipcRenderer.invoke('open-folder'),
  openFile: () => ipcRenderer.invoke('open-file'),
  openImage: () => ipcRenderer.invoke('open-image'),
  saveFile: (defaultName, content) => ipcRenderer.invoke('save-file', defaultName, content),
  setProjectPath: (p) => ipcRenderer.send('set-project-path', p),
  onProjectPath: (cb) => {
    ipcRenderer.on('project-path', (_, path) => cb(path));
  },
  onRequestOpenFolder: (cb) => {
    ipcRenderer.on('request-open-folder', () => cb());
  },
  onNavNewChat: (cb) => {
    ipcRenderer.on('nav-new-chat', () => cb());
  },
  splashRetry: () => ipcRenderer.send('splash-retry'),
  splashExit: () => ipcRenderer.send('splash-exit'),
  splashChoosePython: () => ipcRenderer.send('splash-choose-python'),
  retryBackend: () => ipcRenderer.send('retry-backend'),
  getLLMProvider: () => ipcRenderer.invoke('get-llm-provider'),
  getLLMConfig: () => ipcRenderer.invoke('get-llm-config'),
  setLLMProvider: (p) => ipcRenderer.invoke('set-llm-provider', p),
  setLLMConfig: (cfg) => ipcRenderer.invoke('set-llm-config', cfg),
  restartBackend: () => ipcRenderer.send('restart-backend')
});
