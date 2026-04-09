import { invoke } from '@tauri-apps/api/core';

export const tauriAPI = {
  getBackendUrl: async () => {
    try {
      return await invoke('get_backend_url');
    } catch {
      return 'http://127.0.0.1:8765';
    }
  },

  openDirectory: async () => {
    try {
      return await invoke('open_folder');
    } catch {
      return null;
    }
  },

  openFolder: async () => {
    try {
      return await invoke('open_folder');
    } catch {
      return null;
    }
  },

  openFile: async () => {
    try {
      return await invoke('open_file');
    } catch {
      return null;
    }
  },

  openImage: async () => {
    try {
      return await invoke('open_image');
    } catch {
      return null;
    }
  },

  readDirectory: async (path) => {
    try {
      const tree = await invoke('get_file_tree');
      return tree.tree || [];
    } catch {
      return [];
    }
  },

  getFileContent: async (relPath) => {
    try {
      return await invoke('get_file_content', { relPath });
    } catch {
      return null;
    }
  },

  readFile: async (relPath) => {
    try {
      const data = await invoke('get_file_content', { relPath });
      if (data && typeof data.content === 'string') return data.content;
      return '';
    } catch {
      return '';
    }
  },

  setModel: async ({ provider, model, baseUrl, apiKey }) => {
    try {
      await invoke('set_llm_config', {
        cfg: {
          provider,
          model,
          baseUrl: baseUrl || '',
          apiKey: apiKey || '',
        },
      });
      return true;
    } catch {
      return false;
    }
  },

  getProjectPath: async () => {
    try {
      return await invoke('get_project_path');
    } catch {
      return null;
    }
  },

  setProjectPath: async (path) => {
    try {
      await invoke('set_project_path', { path });
      return true;
    } catch {
      return false;
    }
  },

  getLLMConfig: async () => {
    try {
      return await invoke('get_llm_config');
    } catch {
      return {};
    }
  },

  setLLMConfig: async (config) => {
    try {
      return await invoke('set_llm_config', { cfg: config });
    } catch {
      return false;
    }
  },

  getLLMProvider: async () => {
    try {
      return await invoke('get_llm_provider');
    } catch {
      return 'Built-in';
    }
  },

  setLLMProvider: async (provider) => {
    try {
      return await invoke('set_llm_provider', { provider });
    } catch {
      return false;
    }
  },

  getTheme: async () => {
    try {
      return await invoke('get_theme');
    } catch {
      return 'system';
    }
  },

  setTheme: async (theme) => {
    try {
      return await invoke('set_theme', { theme });
    } catch {
      return false;
    }
  },

  getLogPath: async () => {
    try {
      return await invoke('get_log_path');
    } catch {
      return '';
    }
  },

  getLogDir: async () => {
    try {
      return await invoke('get_log_dir');
    } catch {
      return null;
    }
  },

  setLogDir: async (dir) => {
    try {
      return await invoke('set_log_dir', { dir });
    } catch {
      return false;
    }
  },

  readLogs: async (logType) => {
    try {
      return await invoke('read_logs', { logType });
    } catch {
      return '';
    }
  },

  restartBackend: async () => {
    try {
      await invoke('restart_backend');
      return true;
    } catch {
      return false;
    }
  },

  retryBackend: async () => {
    try {
      await invoke('retry_backend');
      return true;
    } catch {
      return false;
    }
  },

  openPath: async (path) => {
    try {
      await invoke('open_path', { path });
      return true;
    } catch {
      return false;
    }
  },

  saveFile: async (content, defaultName) => {
    try {
      return await invoke('save_file', { defaultName, content });
    } catch {
      return null;
    }
  },
};

if (typeof window !== 'undefined') {
  window.tauriAPI = tauriAPI;
}
