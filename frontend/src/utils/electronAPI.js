export const electronAPI = {
  getBackendUrl: async () => 'http://127.0.0.1:8765',

  openDirectory: async () => null,

  openFolder: async () => null,

  readDirectory: async () => [],

  readFile: async () => '',

  writeFile: async () => false,

  setModel: async () => false,

  getLLMConfig: async () => ({}),

  setLLMConfig: async () => false,

  getMcpSettings: async () => ({}),

  restartBackend: async () => false,

  showSaveDialog: async () => null,

  showOpenDialog: async () => null,
};
