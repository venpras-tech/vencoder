const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  getProjectPath: () => ipcRenderer.invoke('get-project-path'),
  openFolder: () => ipcRenderer.invoke('open-folder'),
  setProjectPath: (p) => ipcRenderer.send('set-project-path', p),
  onProjectPath: (cb) => {
    ipcRenderer.on('project-path', (_, path) => cb(path));
  },
  onRequestOpenFolder: (cb) => {
    ipcRenderer.on('request-open-folder', () => cb());
  },
  splashRetry: () => ipcRenderer.send('splash-retry'),
  splashExit: () => ipcRenderer.send('splash-exit'),
  splashChoosePython: () => ipcRenderer.send('splash-choose-python'),
  retryBackend: () => ipcRenderer.send('retry-backend')
});
