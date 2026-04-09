const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');

let mainWindow = null;
let backendProcess = null;

const isDev = process.env.NODE_ENV !== 'production';
const BACKEND_PORT = 8765;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    const indexPath = path.join(__dirname, 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startBackend() {
  const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
  const backendPath = path.join(__dirname, '..', 'backend', 'server.py');

  if (!fs.existsSync(backendPath)) {
    console.log('Backend server not found at:', backendPath);
    return;
  }

  backendProcess = spawn(pythonPath, [backendPath], {
    cwd: path.join(__dirname, '..'),
    stdio: ['pipe', 'pipe', 'pipe'],
    shell: true,
  });

  backendProcess.stdout.on('data', (data) => {
    console.log('Backend:', data.toString().trim());
  });

  backendProcess.stderr.on('data', (data) => {
    console.error('Backend Error:', data.toString().trim());
  });

  backendProcess.on('close', (code) => {
    console.log('Backend process exited with code', code);
    backendProcess = null;
  });
}

function waitForBackend(maxAttempts = 30, delay = 1000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const check = () => {
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/health`, (res) => {
        resolve(true);
      });

      req.on('error', () => {
        attempts++;
        if (attempts >= maxAttempts) {
          reject(new Error('Backend did not start'));
        } else {
          setTimeout(check, delay);
        }
      });

      req.end();
    };

    check();
  });
}

app.whenReady().then(async () => {
  createWindow();

  startBackend();

  try {
    await waitForBackend();
    console.log('Backend is ready');
    mainWindow?.webContents.send('backend-ready');
  } catch (err) {
    console.error('Failed to start backend:', err.message);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

ipcMain.handle('get-backend-url', () => {
  return `http://127.0.0.1:${BACKEND_PORT}`;
});

ipcMain.handle('open-directory', async () => {
  const { dialog } = require('electron');
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('read-directory', async (event, dirPath) => {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    return entries.map((entry) => ({
      name: entry.name,
      path: path.join(dirPath, entry.name),
      isDirectory: entry.isDirectory(),
    }));
  } catch (err) {
    console.error('Failed to read directory:', err);
    return [];
  }
});

ipcMain.handle('read-file', async (event, filePath) => {
  try {
    return fs.readFileSync(filePath, 'utf-8');
  } catch (err) {
    console.error('Failed to read file:', err);
    return '';
  }
});

ipcMain.handle('write-file', async (event, filePath, content) => {
  try {
    fs.writeFileSync(filePath, content, 'utf-8');
    return true;
  } catch (err) {
    console.error('Failed to write file:', err);
    return false;
  }
});

ipcMain.handle('get-llm-config', async () => {
  try {
    const configPath = path.join(app.getPath('userData'), 'llm-config.json');
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    }
  } catch (err) {
    console.error('Failed to get LLM config:', err);
  }
  return {};
});

ipcMain.handle('set-llm-config', async (event, config) => {
  try {
    const configPath = path.join(app.getPath('userData'), 'llm-config.json');
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
    return true;
  } catch (err) {
    console.error('Failed to set LLM config:', err);
    return false;
  }
});

ipcMain.handle('restart-backend', async () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
  startBackend();
  try {
    await waitForBackend();
    return true;
  } catch {
    return false;
  }
});
