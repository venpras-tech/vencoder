const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  openDirectory: () => ipcRenderer.invoke('open-directory'),
  readDirectory: (path) => ipcRenderer.invoke('read-directory', path),
  readFile: (path) => ipcRenderer.invoke('read-file', path),
  writeFile: (path, content) => ipcRenderer.invoke('write-file', path, content),
  getLLMConfig: () => ipcRenderer.invoke('get-llm-config'),
  setLLMConfig: (config) => ipcRenderer.invoke('set-llm-config', config),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  onBackendReady: (callback) => {
    ipcRenderer.on('backend-ready', callback);
    return () => ipcRenderer.removeListener('backend-ready', callback);
  },
});
