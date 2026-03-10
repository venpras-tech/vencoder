const { app, BrowserWindow, ipcMain, dialog, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

function getLogPath() {
  try {
    let customDir = null;
    try {
      const settings = getAppSettings();
      customDir = settings.logPath;
    } catch (_) {}
    if (customDir && typeof customDir === 'string') {
      try {
        fs.mkdirSync(customDir, { recursive: true });
        return path.join(customDir, 'app.log');
      } catch (_) {}
    }
    if (app.isPackaged) {
      const dir = path.join(process.env.APPDATA || process.env.LOCALAPPDATA || process.cwd(), 'ai-codec');
      try { fs.mkdirSync(dir, { recursive: true }); } catch (_) {}
      return path.join(dir, 'app.log');
    }
    return path.join(__dirname, '..', 'app.log');
  } catch (_) {
    return path.join(process.cwd(), 'app.log');
  }
}

function log(level, ...args) {
  const msg = args.map((a) => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
  const line = `${new Date().toISOString()} [${level}] ${msg}\n`;
  try {
    fs.appendFileSync(getLogPath(), line);
  } catch (_) {}
  const out = level === 'ERROR' ? console.error : console.log;
  out(`[${level}]`, ...args);
}

function writeCrashLog(err) {
  try {
    const logPath = getLogPath();
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.appendFileSync(logPath, `${new Date().toISOString()} [CRASH] ${err.stack || err}\n`);
  } catch (_) {}
}

let projectPath;
try {
  projectPath = require('electron').app.isPackaged ? require('electron').app.getPath('documents') : path.join(__dirname, '..');
} catch (_) {
  projectPath = path.join(__dirname, '..');
}

const BACKEND_PORT = 8765;
const BACKEND_HOST = '127.0.0.1';
let backendProcess = null;
let mainWindow = null;
let splashWindow = null;
let isShuttingDown = false;

function getBackendDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  }
  return path.join(__dirname, '..', 'backend');
}

function getBundledPythonPath() {
  if (!app.isPackaged) return null;
  const pyExe = path.join(process.resourcesPath, 'python', 'python.exe');
  return fs.existsSync(pyExe) ? pyExe : null;
}

function getBackendPath() {
  const root = app.isPackaged ? app.getPath('documents') : path.join(__dirname, '..');
  const isWin = process.platform === 'win32';
  const py = isWin ? 'python' : 'python3';
  return { root, py };
}

const BACKEND_CONFIG_FILE = 'backend-config.json';
const APP_SETTINGS_FILE = 'app-settings.json';

function getAppSettings() {
  try {
    const cfgPath = path.join(app.getPath('userData'), APP_SETTINGS_FILE);
    if (fs.existsSync(cfgPath)) {
      return JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    }
  } catch (_) {}
  return {};
}

function setAppSettings(settings) {
  try {
    const cfgPath = path.join(app.getPath('userData'), APP_SETTINGS_FILE);
    const current = getAppSettings();
    fs.writeFileSync(cfgPath, JSON.stringify({ ...current, ...settings }), 'utf8');
  } catch (_) {}
}

function getSavedPythonPath() {
  if (!app.isPackaged) return null;
  try {
    const cfgPath = path.join(app.getPath('userData'), BACKEND_CONFIG_FILE);
    if (fs.existsSync(cfgPath)) {
      const data = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
      const p = data.pythonPath;
      if (p && typeof p === 'string' && fs.existsSync(p)) return p;
    }
  } catch (_) {}
  return null;
}

function setSavedPythonPath(p) {
  try {
    const cfgPath = path.join(app.getPath('userData'), BACKEND_CONFIG_FILE);
    fs.writeFileSync(cfgPath, JSON.stringify({ pythonPath: p }), 'utf8');
  } catch (_) {}
}

function findPythonWindows() {
  const saved = getSavedPythonPath();
  if (saved) return [saved];
  const candidates = [];
  const localAppData = process.env.LOCALAPPDATA || path.join(process.env.USERPROFILE || '', 'AppData', 'Local');
  const pyDir = path.join(localAppData, 'Programs', 'Python');
  if (fs.existsSync(pyDir)) {
    try {
      const versions = fs.readdirSync(pyDir).filter((n) => n.startsWith('Python'));
      versions.sort().reverse();
      for (const v of versions) {
        const exe = path.join(pyDir, v, 'python.exe');
        if (fs.existsSync(exe)) candidates.push(exe);
      }
    } catch (_) {}
  }
  const appData = process.env.APPDATA || path.join(process.env.USERPROFILE || '', 'AppData', 'Roaming');
  const pyDir2 = path.join(path.dirname(appData), 'Local', 'Programs', 'Python');
  if (fs.existsSync(pyDir2)) {
    try {
      const versions = fs.readdirSync(pyDir2).filter((n) => n.startsWith('Python'));
      versions.sort().reverse();
      for (const v of versions) {
        const exe = path.join(pyDir2, v, 'python.exe');
        if (fs.existsSync(exe) && !candidates.includes(exe)) candidates.push(exe);
      }
    } catch (_) {}
  }
  if (process.env.USERPROFILE && fs.existsSync(path.join(process.env.USERPROFILE, '..'))) {
    try {
      const root = path.resolve(process.env.USERPROFILE, '..', '..');
      const driveRoot = path.parse(root).root;
      const top = fs.readdirSync(driveRoot || root);
      for (const name of top) {
        if (name.startsWith('Python') && /Python\d+/.test(name)) {
          const exe = path.join(driveRoot || root, name, 'python.exe');
          if (fs.existsSync(exe) && !candidates.includes(exe)) candidates.push(exe);
        }
      }
    } catch (_) {}
  }
  return candidates;
}

function startBackend(workspaceRoot) {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
  const backendDir = getBackendDir();
  const backendDirExists = fs.existsSync(backendDir);
  log('INFO', 'startBackend', 'dir=', backendDir, 'exists=', backendDirExists);
  if (!backendDirExists) {
    log('ERROR', 'Backend directory missing:', backendDir);
    return;
  }
  const settings = getAppSettings();
  const env = {
    ...process.env,
    PYTHONPATH: backendDir,
    WORKSPACE_ROOT: workspaceRoot || projectPath
  };
  const provider = settings.llmProvider || 'Ollama';
  env.LLM_PROVIDER = provider === 'Built-in' ? 'builtin' : 'ollama';
  if (settings.llmModel) env.LLM_MODEL = settings.llmModel;
  if (app.isPackaged) {
    const bundled = getBundledPythonPath();
    if (bundled) {
      const pythonDir = path.dirname(bundled);
      env.PATH = pythonDir + path.delimiter + (env.PATH || '');
    }
  }
  const args = ['-m', 'uvicorn', 'server:app', '--host', BACKEND_HOST, '--port', String(BACKEND_PORT)];
  const isWin = process.platform === 'win32';

  function run(cmd, cmdArgs) {
    log('INFO', 'Spawning backend:', cmd, cmdArgs.join(' '));
    const proc = spawn(cmd, cmdArgs, {
      cwd: backendDir,
      env,
      stdio: ['ignore', 'pipe', 'pipe']
    });
    proc.stdout.on('data', (data) => {
      const s = data.toString().trim();
      log('INFO', '[backend]', s);
    });
    proc.stderr.on('data', (data) => {
      const s = data.toString().trim();
      log('INFO', '[backend stderr]', s);
    });
    proc.on('error', (err) => {
      log('ERROR', 'Backend spawn error:', err.message);
    });
        proc.on('exit', (code, sig) => {
          log('INFO', 'Backend exited', code, sig);
          if (!isShuttingDown && code !== 0 && sig !== 'SIGTERM') {
            log('INFO', 'Backend crashed, restarting in 2s...');
            setTimeout(() => startBackend(projectPath), 2000);
          }
        });
        return proc;
  }

  function tryOrderWinDev() {
    const tryOrder = ['python', 'py', 'python3'];
    let idx = 0;
    function tryNext() {
      if (idx >= tryOrder.length) return;
      const cmd = tryOrder[idx];
      const cmdArgs = cmd === 'py' ? ['-3', ...args] : args;
      log('INFO', 'Spawning backend (dev):', cmd, cmdArgs.join(' '));
      const proc = spawn(cmd, cmdArgs, {
        cwd: backendDir,
        env,
        stdio: ['ignore', 'pipe', 'pipe']
      });
      backendProcess = proc;
      proc.stdout.on('data', (d) => log('INFO', '[backend]', d.toString().trim()));
      proc.stderr.on('data', (d) => log('INFO', '[backend stderr]', d.toString().trim()));
      proc.on('error', (err) => {
        log('ERROR', 'Backend spawn error:', cmd, err.message);
        backendProcess = null;
        idx++;
        tryNext();
      });
      proc.on('exit', (code, sig) => {
        log('INFO', 'Backend exited', code, sig);
        if (!isShuttingDown && code !== 0 && sig !== 'SIGTERM') {
          log('INFO', 'Backend crashed, restarting in 2s...');
          setTimeout(() => startBackend(projectPath), 2000);
        }
      });
      idx++;
    }
    tryNext();
  }

  if (isWin) {
    if (app.isPackaged) {
      const bundled = getBundledPythonPath();
      const pyPaths = findPythonWindows();
      const tryOrder = [...(bundled ? [bundled] : []), ...pyPaths, 'python', 'py'];
      let idx = 0;
      function trySpawn() {
        if (idx >= tryOrder.length) return;
        const cmd = tryOrder[idx];
        const cmdArgs = (cmd === 'py' || (typeof cmd === 'string' && cmd.toLowerCase() === 'py')) ? ['-3', ...args] : args;
        log('INFO', 'Spawning backend (packaged):', cmd, cmdArgs.join(' '));
        const proc = spawn(cmd, cmdArgs, {
          cwd: backendDir,
          env,
          stdio: ['ignore', 'pipe', 'pipe']
        });
        backendProcess = proc;
        proc.stdout.on('data', (d) => log('INFO', '[backend]', d.toString().trim()));
        proc.stderr.on('data', (d) => log('INFO', '[backend stderr]', d.toString().trim()));
        proc.on('error', (err) => {
          log('ERROR', 'Backend spawn error:', cmd, err.message);
          backendProcess = null;
          idx++;
          trySpawn();
        });
        proc.on('exit', (c, s) => {
          log('INFO', 'Backend exited', c, s);
          if (!isShuttingDown && c !== 0 && s !== 'SIGTERM') {
            log('INFO', 'Backend crashed, restarting in 2s...');
            setTimeout(() => startBackend(projectPath), 2000);
          }
        });
        idx++;
      }
      trySpawn();
    } else {
      tryOrderWinDev();
    }
  } else {
    const { py } = getBackendPath();
    backendProcess = run(py, args);
  }
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

function waitForBackend(timeoutMs) {
  const http = require('http');
  const start = Date.now();
  timeoutMs = timeoutMs || (app.isPackaged ? 30000 : 15000);
  return new Promise((resolve) => {
    function attempt() {
      const req = http.get(`http://${BACKEND_HOST}:${BACKEND_PORT}/health`, (res) => {
        res.resume();
        resolve(true);
      });
      req.on('error', () => {
        if (Date.now() - start >= timeoutMs) return resolve(false);
        setTimeout(attempt, 400);
      });
      req.setTimeout(3000, () => {
        req.destroy();
        if (Date.now() - start >= timeoutMs) return resolve(false);
        setTimeout(attempt, 400);
      });
    }
    attempt();
  });
}

function showSplash(message, showRetry = false) {
  const html = `
    <!DOCTYPE html>
    <html><head><meta charset="UTF-8"></head>
    <body style="margin:0;font-family:'Segoe UI',sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;background:#f5f5f5;">
      <p id="msg" style="font-size:14px;color:#525252;">${message}</p>
      <div id="btns" style="margin-top:16px;display:${showRetry ? 'flex' : 'none'};gap:10px;">
        <button id="retry" style="padding:8px 16px;cursor:pointer;">Retry</button>
        <button id="choose-python" style="padding:8px 16px;cursor:pointer;">Choose Python…</button>
        <button id="exit" style="padding:8px 16px;cursor:pointer;">Exit</button>
      </div>
    </body></html>
  `;
  if (!splashWindow || splashWindow.isDestroyed()) {
    splashWindow = new BrowserWindow({
      width: 380,
      height: 160,
      resizable: false,
      frame: true,
      show: false,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js')
      }
    });
    splashWindow.setMenu(null);
    splashWindow.on('closed', () => {
      splashWindow = null;
      if (!mainWindow || mainWindow.isDestroyed()) app.quit();
    });
  }
  splashWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
  splashWindow.once('ready-to-show', () => splashWindow.show());
  const showTimeout = setTimeout(() => {
    if (splashWindow && !splashWindow.isDestroyed() && !splashWindow.isVisible()) {
      splashWindow.show();
      log('INFO', 'Splash shown (timeout fallback)');
    }
  }, 2000);
  splashWindow.webContents.once('did-finish-load', () => {
    clearTimeout(showTimeout);
    splashWindow.webContents.executeJavaScript(`
      var r = document.getElementById('retry'); var c = document.getElementById('choose-python'); var e = document.getElementById('exit');
      if (r && window.electronAPI && window.electronAPI.splashRetry) r.onclick = function() { window.electronAPI.splashRetry(); };
      if (c && window.electronAPI && window.electronAPI.splashChoosePython) c.onclick = function() { window.electronAPI.splashChoosePython(); };
      if (e && window.electronAPI && window.electronAPI.splashExit) e.onclick = function() { window.electronAPI.splashExit(); };
    `).catch(() => {});
  });
  return splashWindow;
}

function updateSplashMessage(message, showRetry = false) {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.executeJavaScript(`
      document.getElementById('msg').textContent = ${JSON.stringify(message)};
      var btns = document.getElementById('btns');
      if (btns) btns.style.display = ${showRetry ? "'flex'" : "'none'"};
    `).catch(() => {});
  }
}

function closeSplash() {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.close();
    splashWindow = null;
  }
}

function updateWindowTitle() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    const folderName = projectPath ? path.basename(projectPath) : '';
    mainWindow.setTitle(folderName ? `AI Codec – ${folderName}` : 'AI Codec');
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 720,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });
  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.send('backend-url', `http://${BACKEND_HOST}:${BACKEND_PORT}`);
    mainWindow.webContents.send('project-path', projectPath);
    updateWindowTitle();
  });
  mainWindow.webContents.on('did-fail-load', (event, code, desc) => {
    log('ERROR', 'Main window failed to load', code, desc);
  });

  const menu = Menu.buildFromTemplate([
    {
      label: 'File',
      submenu: [
        {
          label: 'New Chat',
          accelerator: 'CmdOrCtrl+N',
          click: () => mainWindow.webContents.send('nav-new-chat')
        },
        {
          label: 'Open Folder…',
          accelerator: 'CmdOrCtrl+O',
          click: () => mainWindow.webContents.send('request-open-folder')
        },
        { type: 'separator' },
        { role: 'quit', label: 'Exit' }
      ]
    },
    { role: 'editMenu' },
    { role: 'viewMenu' },
    { role: 'windowMenu' },
    { role: 'help' }
  ]);
  Menu.setApplicationMenu(menu);
}

app.whenReady().then(async () => {
  try {
    log('INFO', 'App ready', app.isPackaged ? 'packaged' : 'dev');
    if (app.isPackaged) {
      const backendDir = getBackendDir();
      const bundledPy = getBundledPythonPath();
      log('INFO', 'resourcesPath', process.resourcesPath, 'backendDir', backendDir, 'bundledPython', bundledPy || 'none');
    }
    showSplash('Loading application…', false);
    startBackend(projectPath);
    createWindow();
    const showMain = () => {
      updateSplashMessage('Opening window…', false);
      mainWindow.show();
      closeSplash();
    };
    mainWindow.once('ready-to-show', showMain);
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
        log('INFO', 'Main window ready-to-show timeout, showing anyway');
        showMain();
      }
    }, 15000);
  } catch (err) {
    writeCrashLog(err);
    log('ERROR', 'Startup failed', err.stack || err);
    try {
      const { dialog } = require('electron');
      dialog.showErrorBox('Startup Error', (err.message || String(err)) + '\n\nCheck app.log in %APPDATA%\\ai-codec');
    } catch (_) {}
    app.quit();
  }
});

process.on('uncaughtException', (err) => {
  writeCrashLog(err);
  try { log('ERROR', 'uncaughtException', err.stack || err); } catch (_) {}
  try {
    require('electron').dialog.showErrorBox('Fatal Error', (err.message || String(err)) + '\n\nCheck %APPDATA%\\ai-codec\\app.log');
  } catch (_) {}
  process.exit(1);
});

process.on('unhandledRejection', (reason, p) => {
  writeCrashLog(reason instanceof Error ? reason : new Error(String(reason)));
  try { log('ERROR', 'unhandledRejection', String(reason)); } catch (_) {}
});

ipcMain.on('splash-retry', async () => {
  if (!splashWindow || splashWindow.isDestroyed()) return;
  updateSplashMessage('Starting backend…', false);
  startBackend(projectPath);
  const ok = await waitForBackend();
  if (ok) {
    closeSplash();
    createWindow();
  } else {
    updateSplashMessage('Backend could not start. Use Python 3.10–3.13 (3.14 has ChromaDB issues). Run "pip install -r requirements.txt" in the backend folder. Or use Choose Python… to pick a compatible Python.', true);
  }
});

ipcMain.on('splash-exit', () => {
  closeSplash();
  app.quit();
});

ipcMain.on('splash-choose-python', async () => {
  if (!splashWindow || splashWindow.isDestroyed()) return;
  updateSplashMessage('Starting backend…', false);
  const win = splashWindow;
  const result = await dialog.showOpenDialog(win, {
    title: 'Select Python executable',
    defaultPath: process.env.LOCALAPPDATA || '',
    filters: [{ name: 'Executable', extensions: ['exe'] }, { name: 'All', extensions: ['*'] }],
    properties: ['openFile']
  });
  if (result.canceled || !result.filePaths.length) {
    updateSplashMessage('Backend could not start. Use Python 3.10–3.13 (3.14 has ChromaDB issues). Run "pip install -r requirements.txt" in the backend folder. Or use Choose Python… to pick a compatible Python.', true);
    return;
  }
  const pythonPath = result.filePaths[0];
  setSavedPythonPath(pythonPath);
  startBackend(projectPath);
  const ok = await waitForBackend();
  if (ok) {
    closeSplash();
    createWindow();
  } else {
    updateSplashMessage('Backend could not start with the selected Python. Use Python 3.10–3.13. Install deps: pip install -r requirements.txt in the backend folder.', true);
  }
});

app.on('window-all-closed', () => {
  stopBackend();
  app.quit();
});

app.on('before-quit', () => {
  isShuttingDown = true;
  stopBackend();
});

ipcMain.handle('get-backend-url', () => `http://${BACKEND_HOST}:${BACKEND_PORT}`);
ipcMain.handle('get-project-path', () => projectPath);

ipcMain.handle('get-log-path', () => getLogPath());

ipcMain.handle('get-log-dir', () => {
  const settings = getAppSettings();
  return settings.logPath || null;
});

ipcMain.handle('get-theme', () => {
  const settings = getAppSettings();
  const t = settings.theme;
  return (t === 'light' || t === 'dark' || t === 'system') ? t : 'system';
});

ipcMain.handle('set-theme', (_, theme) => {
  if (theme === 'light' || theme === 'dark' || theme === 'system') {
    setAppSettings({ theme });
    return true;
  }
  return false;
});

ipcMain.handle('set-log-dir', (_, dirPath) => {
  if (typeof dirPath === 'string') {
    const trimmed = dirPath.trim();
    setAppSettings({ logPath: trimmed || null });
    return true;
  }
  return false;
});

const LOG_READ_MAX_BYTES = 2 * 1024 * 1024;

ipcMain.handle('read-logs', (_, logType) => {
  try {
    const p = logType === 'backend'
      ? path.join(projectPath || '.', 'logs', 'server.log')
      : getLogPath();
    if (fs.existsSync(p)) {
      const stat = fs.statSync(p);
      if (stat.size > LOG_READ_MAX_BYTES) {
        const buf = Buffer.alloc(LOG_READ_MAX_BYTES);
        const fd = fs.openSync(p, 'r');
        fs.readSync(fd, buf, 0, buf.length, stat.size - buf.length);
        fs.closeSync(fd);
        const s = buf.toString('utf8', 0, buf.length);
        const nl = s.indexOf('\n');
        return '... (showing last 2MB)\n\n' + (nl >= 0 ? s.slice(nl + 1) : s);
      }
      return fs.readFileSync(p, 'utf8');
    }
    return '';
  } catch (e) {
    return `Error reading logs: ${e.message}`;
  }
});

ipcMain.handle('open-folder', async () => {
  const win = BrowserWindow.getFocusedWindow();
  const result = await dialog.showOpenDialog(win || mainWindow, {
    properties: ['openDirectory']
  });
  if (result.canceled || !result.filePaths.length) return null;
  return result.filePaths[0];
});

ipcMain.handle('open-file', async () => {
  const win = BrowserWindow.getFocusedWindow();
  const result = await dialog.showOpenDialog(win || mainWindow, {
    title: 'Select file to add to context',
    defaultPath: projectPath || undefined,
    properties: ['openFile']
  });
  if (result.canceled || !result.filePaths.length) return null;
  return result.filePaths[0];
});

ipcMain.handle('open-image', async () => {
  const win = BrowserWindow.getFocusedWindow();
  const result = await dialog.showOpenDialog(win || mainWindow, {
    title: 'Select image for visual context',
    defaultPath: projectPath || undefined,
    filters: [
      { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'] },
      { name: 'All', extensions: ['*'] }
    ],
    properties: ['openFile']
  });
  if (result.canceled || !result.filePaths.length) return null;
  try {
    const buf = fs.readFileSync(result.filePaths[0]);
    return buf.toString('base64');
  } catch (e) {
    log('ERROR', 'open-image read failed', e);
    return null;
  }
});

ipcMain.handle('save-file', async (_, defaultName, content) => {
  const win = BrowserWindow.getFocusedWindow();
  const result = await dialog.showSaveDialog(win || mainWindow, {
    defaultPath: defaultName || 'chat-export.json'
  });
  if (result.canceled || !result.filePath) return null;
  fs.writeFileSync(result.filePath, content, 'utf8');
  return result.filePath;
});

ipcMain.on('retry-backend', () => {
  startBackend(projectPath);
});

ipcMain.handle('get-llm-provider', () => {
  const s = getAppSettings();
  return s.llmProvider || 'Ollama';
});

ipcMain.handle('set-llm-provider', (_, provider) => {
  if (provider === 'Ollama' || provider === 'Built-in') {
    setAppSettings({ llmProvider: provider });
    return true;
  }
  return false;
});

ipcMain.handle('set-llm-config', (_, cfg) => {
  if (cfg && typeof cfg === 'object') {
    const updates = {};
    if (cfg.provider === 'Ollama' || cfg.provider === 'Built-in') updates.llmProvider = cfg.provider;
    if (typeof cfg.model === 'string') updates.llmModel = cfg.model;
    if (Object.keys(updates).length) {
      setAppSettings(updates);
      return true;
    }
  }
  return false;
});

ipcMain.on('restart-backend', () => {
  stopBackend();
  startBackend(projectPath);
});

ipcMain.on('set-project-path', (_, newPath) => {
  if (!newPath || newPath === projectPath) return;
  projectPath = newPath;
  stopBackend();
  startBackend(projectPath);
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('project-path', projectPath);
    updateWindowTitle();
  }
});

ipcMain.on('request-open-folder', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('request-open-folder');
  }
});
