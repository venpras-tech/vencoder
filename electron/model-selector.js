(function () {
  const PROVIDERS = ['Ollama', 'LM Studio', 'Built-in', 'OpenAI', 'Anthropic', 'Google'];
  const PROVIDER_NEEDS_BASE = ['Ollama', 'LM Studio'];
  const PROVIDER_NEEDS_KEY = ['OpenAI', 'Anthropic', 'Google'];

  let backendUrl = '';

  function api() {
    return window.electronAPI || (window.__TAURI__ && window.__TAURI__.core ? { getBackendUrl: () => Promise.resolve('') } : null);
  }

  async function getBackendUrl() {
    const a = api();
    if (!a || !a.getBackendUrl) return '';
    if (backendUrl) return backendUrl;
    backendUrl = await a.getBackendUrl();
    return backendUrl;
  }

  async function fetchModels(provider) {
    const base = await getBackendUrl();
    if (!base) return { provider, models: [] };
    const q = provider ? `?provider=${encodeURIComponent(provider)}` : '';
    const r = await fetch(`${base}/models${q}`, { signal: AbortSignal.timeout(10000) });
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  }

  async function fetchBuiltinSuggested() {
    const base = await getBackendUrl();
    if (!base) return { suggested: [] };
    const r = await fetch(`${base}/builtin/suggested-models`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return { suggested: [] };
    return r.json();
  }

  async function fetchBuiltinSystemInfo() {
    const base = await getBackendUrl();
    if (!base) return { ram_gb: 8, tier: 'medium' };
    const r = await fetch(`${base}/builtin/system-info`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return { ram_gb: 8, tier: 'medium' };
    return r.json();
  }

  async function fetchBuiltinModelsDir() {
    const base = await getBackendUrl();
    if (!base) return null;
    const r = await fetch(`${base}/builtin/models-dir`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return null;
    const j = await r.json();
    return j.path || null;
  }

  async function fetchBuiltinDownloadStatus() {
    const base = await getBackendUrl();
    if (!base) return {};
    const r = await fetch(`${base}/builtin/download-status`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return {};
    const j = await r.json();
    return j.downloads || {};
  }

  function modelNameFromFile(file) {
    return (file || '').replace(/\.gguf$/i, '');
  }

  function updateDownloadStatusBar(st) {
    const bar = document.getElementById('download-status-bar');
    const text = document.getElementById('download-status-text');
    const progressBar = document.getElementById('download-status-progress-bar');
    if (!bar || !text || !progressBar) return;
    const files = Object.keys(st || {});
    const active = files.filter(function(f) {
      const d = st[f];
      return d && !d.error && !d.ok && d.progress !== undefined && d.progress < 1;
    });
    if (active.length === 0) {
      bar.hidden = true;
      return;
    }
    const first = st[active[0]];
    const pct = Math.round((first.progress || 0) * 100);
    const name = modelNameFromFile(active[0]);
    text.textContent = active.length > 1
      ? 'Downloading ' + active.length + ' models… ' + name + ' (' + pct + '%)'
      : 'Downloading ' + name + '… ' + pct + '%';
    progressBar.style.width = pct + '%';
    bar.hidden = false;
  }

  function showDownloadCompleteToast(modelName, isError) {
    const toast = document.getElementById('download-toast');
    const text = document.getElementById('download-toast-text');
    const icon = toast ? toast.querySelector('.download-toast-icon') : null;
    if (!toast || !text) return;
    text.textContent = isError ? 'Download failed: ' + (modelName || 'model') : (modelName || 'Model') + ' downloaded successfully';
    if (icon) icon.textContent = isError ? '\u2715' : '\u2713';
    toast.classList.toggle('download-toast-error', !!isError);
    toast.hidden = false;
    clearTimeout(showDownloadCompleteToast._tid);
    showDownloadCompleteToast._tid = setTimeout(function() {
      toast.hidden = true;
    }, 4000);
  }

  async function downloadBuiltinModel(repoId, filename, onProgress) {
    const base = await getBackendUrl();
    if (!base) throw new Error('Backend not ready');
    const r = await fetch(`${base}/builtin/download-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_id: repoId, filename }),
      signal: AbortSignal.timeout(600000)
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.detail || r.statusText);
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let lastResult = null;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const obj = JSON.parse(line);
          lastResult = obj;
          if (obj.error) throw new Error(obj.error);
          if (obj.progress !== undefined && onProgress) onProgress(obj.progress, obj.downloaded, obj.total);
        } catch (e) {
          if (e instanceof SyntaxError) continue;
          throw e;
        }
      }
    }
    if (buf.trim()) {
      const obj = JSON.parse(buf);
      lastResult = obj;
      if (obj.error) throw new Error(obj.error);
    }
    return lastResult || { ok: false };
  }

  async function deleteBuiltinModel(filename) {
    const base = await getBackendUrl();
    if (!base) throw new Error('Backend not ready');
    const r = await fetch(`${base}/builtin/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
      signal: AbortSignal.timeout(10000)
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.detail || r.statusText);
    }
    return r.json();
  }

  async function fetchCurrentModel() {
    const base = await getBackendUrl();
    if (!base) return { provider: '', model: '' };
    const r = await fetch(`${base}/model`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return { provider: '', model: '' };
    return r.json();
  }

  async function patchModel(model) {
    const base = await getBackendUrl();
    if (!base) throw new Error('Backend not ready');
    const r = await fetch(`${base}/model`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
      signal: AbortSignal.timeout(5000)
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.detail || r.statusText);
    }
    return r.json();
  }

  function getConfig() {
    const a = api();
    return a && a.getLLMConfig ? a.getLLMConfig() : Promise.resolve({ provider: 'Ollama', model: '', baseUrl: '', apiKey: '' });
  }

  function setConfig(cfg) {
    const a = api();
    return a && a.setLLMConfig ? a.setLLMConfig(cfg) : Promise.resolve(false);
  }

  function restartBackend() {
    const a = api();
    if (a && a.restartBackend) a.restartBackend();
  }

  function updateInlineLabel(model, provider) {
    const btn = document.getElementById('btn-model');
    if (!btn) return;
    const text = model ? `${provider || 'Model'}: ${model}` : 'Switch model';
    btn.title = text;
  }

  function navigateToModelsPage() {
    const nav = document.querySelector('.side-nav-item[data-page="models"]');
    if (nav) nav.click();
  }

  function initModelSelector() {
    const btnModel = document.getElementById('btn-model');
    const btnSave = document.getElementById('model-modal-save');
    const btnRefresh = document.getElementById('model-refresh');
    const providersList = document.getElementById('model-providers-list');
    const modelSelect = document.getElementById('model-select');
    const modelFieldSelect = document.getElementById('model-field-select');
    const modelBuiltinWrap = document.getElementById('model-builtin-wrap');
    const modelBuiltinSystem = document.getElementById('model-builtin-system');
    const modelBuiltinList = document.getElementById('model-builtin-list');
    const modelsPrompt = document.getElementById('model-models-prompt');
    const fieldBaseUrl = document.getElementById('model-field-base-url');
    const fieldApiKey = document.getElementById('model-field-api-key');
    const inputBaseUrl = document.getElementById('model-base-url');
    const inputApiKey = document.getElementById('model-api-key');

    if (!providersList || !btnModel) return;

    let currentProvider = 'Ollama';
    let currentModel = '';
    let models = [];
    let isLoading = false;
    let downloadPollId = null;

    function showModelsPage() {
      loadConfigAndModels();
      navigateToModelsPage();
    }

    async function loadConfigAndModels() {
      const cfg = await getConfig();
      currentProvider = cfg.provider || 'Ollama';
      currentModel = cfg.model || '';
      inputBaseUrl.value = cfg.baseUrl || '';
      inputApiKey.value = cfg.apiKey ? '***' : '';

      providersList.querySelectorAll('.model-provider-item').forEach(b => {
        b.classList.toggle('active', b.dataset.provider === currentProvider);
      });

      fieldBaseUrl.hidden = !PROVIDER_NEEDS_BASE.includes(currentProvider);
      fieldApiKey.hidden = !PROVIDER_NEEDS_KEY.includes(currentProvider);

      await loadModels();
    }

    function createOption(value, selected) {
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = value;
      opt.selected = selected;
      return opt;
    }

    async function downloadPollTick() {
      try {
        const st = await fetchBuiltinDownloadStatus();
        updateDownloadStatusBar(st);
        let hasActive = false;
        let needsRefresh = false;
        var completedModel = null;
        var completedError = false;
        for (const file in st) {
          const d = st[file];
          if (d.error) {
            needsRefresh = true;
            completedModel = modelNameFromFile(file);
            completedError = true;
            continue;
          }
          if (d.ok) {
            needsRefresh = true;
            completedModel = (d.model || modelNameFromFile(file));
            continue;
          }
          if (d.progress !== undefined && d.progress < 1) {
            hasActive = true;
            if (modelBuiltinList && currentProvider === 'Built-in') {
              const item = Array.from(modelBuiltinList.querySelectorAll('.model-builtin-item')).find(function(el) { return el.dataset.file === file; });
              if (item) {
                const wrap = item.querySelector('.model-builtin-download-wrap');
                const progressEl = wrap ? wrap.querySelector('[data-progress]') : null;
                const btn = wrap ? wrap.querySelector('.model-builtin-download') : null;
                if (progressEl && btn) {
                  progressEl.hidden = false;
                  btn.style.display = 'none';
                  btn.disabled = true;
                  const pctVal = Math.round((d.progress || 0) * 100);
                  const bar = progressEl.querySelector('.model-download-progress-bar');
                  const text = progressEl.querySelector('.model-download-progress-text');
                  if (bar) bar.style.width = pctVal + '%';
                  if (text) text.textContent = pctVal + '%';
                }
              }
            }
          }
        }
        if (!hasActive) {
          if (downloadPollId) clearInterval(downloadPollId);
          downloadPollId = null;
          const bar = document.getElementById('download-status-bar');
          if (bar) bar.hidden = true;
          if (needsRefresh) {
            showDownloadCompleteToast(completedModel, completedError);
            await loadModels();
          }
        }
      } catch (_) {}
    }

    function selectAndUse(stem) {
      currentModel = stem;
      if (modelSelect) {
        modelSelect.value = stem;
        const opt = Array.from(modelSelect.options).find(o => o.value === stem);
        if (!opt) modelSelect.appendChild(createOption(stem, true));
        else opt.selected = true;
      }
    }

    async function loadModels() {
      if (isLoading) return;
      isLoading = true;
      modelsPrompt.textContent = 'Loading models…';
      modelSelect.innerHTML = '';
      modelSelect.disabled = true;
      if (btnRefresh) btnRefresh.disabled = true;
      if (modelFieldSelect) modelFieldSelect.hidden = false;
      if (modelBuiltinWrap) modelBuiltinWrap.hidden = true;

      try {
        modelsPrompt.style.color = '';
        if (currentProvider === 'Built-in') {
          const [installedData, suggestedData, sysInfo, modelsDir, downloadStatus] = await Promise.all([
            fetchModels(currentProvider),
            fetchBuiltinSuggested(),
            fetchBuiltinSystemInfo(),
            fetchBuiltinModelsDir(),
            fetchBuiltinDownloadStatus()
          ]);
          models = installedData.models || [];
          const suggested = suggestedData.suggested || [];
          const llamaCppAvailable = suggestedData.llama_cpp_available !== false;
          if (modelBuiltinSystem) {
            var sysText = 'Your system: ' + sysInfo.ram_gb + ' GB RAM — suggested for ' + sysInfo.tier + ' tier';
            if (!llamaCppAvailable) sysText += '. First download will install llama-cpp-python (required)';
            modelBuiltinSystem.textContent = sysText;
          }
          const folderSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
          const deleteSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';
          if (modelBuiltinList) {
            modelBuiltinList.innerHTML = suggested.map(function(s) {
              const stem = s.file.replace(/\.gguf$/, '');
              const installed = s.installed;
              const dl = downloadStatus[s.file];
              const isDownloading = dl && !dl.error && (dl.progress !== undefined ? dl.progress < 1 : !dl.ok);
              const pctVal = (dl && dl.progress !== undefined) ? Math.round(dl.progress * 100) : 0;
              const rec = s.recommended ? ' <span class="model-builtin-recommended">Recommended</span>' : '';
              const modelIcon = '<span class="model-builtin-icon">' + brainSvg + '</span>';
              var actions = '';
              if (installed) {
                actions = '<div class="model-builtin-actions">' +
                  '<button type="button" class="model-builtin-icon-btn" data-open-folder title="Open folder">' + folderSvg + '</button>' +
                  '<button type="button" class="model-builtin-icon-btn" data-delete title="Delete model">' + deleteSvg + '</button>' +
                  '<button type="button" class="model-builtin-btn model-builtin-use" data-use>Use</button></div>';
              } else {
                const showProgress = isDownloading;
                const showBtn = !isDownloading;
                actions = '<div class="model-builtin-download-wrap">' +
                  '<div class="model-download-progress" data-progress ' + (showProgress ? '' : 'hidden') + '>' +
                  '<div class="model-download-progress-track"><div class="model-download-progress-bar" style="width:' + pctVal + '%"></div></div>' +
                  '<span class="model-download-progress-text">' + pctVal + '%</span></div>' +
                  '<button type="button" class="model-builtin-btn model-builtin-download" data-download ' + (showBtn ? '' : 'style="display:none" disabled') + '>↓ Download</button></div>';
              }
              return '<div class="model-builtin-item" data-repo="' + s.repo + '" data-file="' + s.file + '" data-stem="' + stem + '">' +
                modelIcon + '<div class="model-builtin-info"><span class="model-builtin-name">' + s.name + '</span>' +
                '<span class="model-builtin-meta">' + s.params + ' · ' + s.size_gb + ' GB</span>' + rec + '</div>' + actions + '</div>';
            }).join('');
            modelBuiltinList.querySelectorAll('[data-open-folder]').forEach(function(btn) {
              btn.addEventListener('click', function(e) {
                e.stopImmediatePropagation();
                var a = api();
                if (modelsDir && a && a.openPath) a.openPath(modelsDir);
              });
            });
            modelBuiltinList.querySelectorAll('[data-delete]').forEach(function(btn) {
              btn.addEventListener('click', async function(e) {
                e.stopImmediatePropagation();
                var item = btn.closest('.model-builtin-item');
                var file = item.dataset.file;
                var stem = item.dataset.stem;
                if (!confirm('Delete model "' + stem + '"? This cannot be undone.')) return;
                btn.disabled = true;
                try {
                  await deleteBuiltinModel(file);
                  models = models.filter(function(m) { return m !== stem; });
                  var opt = modelSelect ? Array.from(modelSelect.options).find(function(o) { return o.value === stem; }) : null;
                  if (opt) opt.remove();
                  await loadModels();
                } catch (err) {
                  btn.disabled = false;
                  modelsPrompt.textContent = 'Delete failed: ' + (err.message || '');
                  modelsPrompt.style.color = '#dc2626';
                }
              });
            });
            modelBuiltinList.querySelectorAll('.model-builtin-download').forEach(function(btn) {
              btn.addEventListener('click', async function(e) {
                e.stopImmediatePropagation();
                var item = btn.closest('.model-builtin-item');
                var repo = item.dataset.repo;
                var file = item.dataset.file;
                var stem = item.dataset.stem;
                var wrap = btn.closest('.model-builtin-download-wrap');
                var progressEl = wrap ? wrap.querySelector('[data-progress]') : null;
                btn.disabled = true;
                if (progressEl) {
                  progressEl.hidden = false;
                  btn.style.display = 'none';
                } else {
                  btn.textContent = llamaCppAvailable ? 'Downloading…' : 'Installing deps…';
                }
                updateDownloadStatusBar({ [file]: { progress: 0, downloaded: 0, total: 1 } });
                if (!downloadPollId) {
                  downloadPollId = setInterval(downloadPollTick, 1500);
                }
                function onProgress(pct, downloaded, total) {
                  if (!progressEl) return;
                  var bar = progressEl.querySelector('.model-download-progress-bar');
                  var text = progressEl.querySelector('.model-download-progress-text');
                  var pctVal = Math.round(pct * 100);
                  if (bar) bar.style.width = pctVal + '%';
                  if (text) text.textContent = pctVal + '%';
                }
                try {
                  await downloadBuiltinModel(repo, file, onProgress);
                  models.push(stem);
                  var opt = createOption(stem, stem === currentModel);
                  if (modelSelect) modelSelect.appendChild(opt);
                  var bar = document.getElementById('download-status-bar');
                  if (bar) bar.hidden = true;
                  showDownloadCompleteToast(stem, false);
                  await loadModels();
                } catch (err) {
                  btn.disabled = false;
                  btn.style.display = '';
                  if (progressEl) {
                    progressEl.hidden = true;
                  }
                  btn.textContent = '↓ Download';
                  modelsPrompt.textContent = 'Download failed: ' + (err.message || '');
                  modelsPrompt.style.color = '#dc2626';
                  var bar = document.getElementById('download-status-bar');
                  if (bar) bar.hidden = true;
                  showDownloadCompleteToast(err.message || 'model', true);
                }
              });
            });
            modelBuiltinList.querySelectorAll('.model-builtin-use').forEach(function(btn) {
              btn.addEventListener('click', function(e) {
                e.stopImmediatePropagation();
                selectAndUse(btn.closest('.model-builtin-item').dataset.stem);
              });
            });
          }
          if (modelFieldSelect) modelFieldSelect.hidden = true;
          if (modelBuiltinWrap) modelBuiltinWrap.hidden = false;
          modelsPrompt.textContent = 'Suggested models for your system. Download to use with local llama.cpp.';
          if (downloadPollId) clearInterval(downloadPollId);
          downloadPollId = null;
          const hasActiveDownloads = Object.keys(downloadStatus).some(function(f) {
            const d = downloadStatus[f];
            return d && !d.error && !d.ok && d.progress !== undefined && d.progress < 1;
          });
          updateDownloadStatusBar(downloadStatus);
          if (hasActiveDownloads && !downloadPollId) {
            downloadPollId = setInterval(downloadPollTick, 1500);
          }
        } else {
          if (downloadPollId) { clearInterval(downloadPollId); downloadPollId = null; }
          const data = await fetchModels(currentProvider);
          models = data.models || [];
          var ph = createOption('', false);
          ph.textContent = models.length ? '— Select model —' : '— No models found —';
          modelSelect.appendChild(ph);
          models.forEach(function(m) { modelSelect.appendChild(createOption(m, m === currentModel)); });
          modelSelect.disabled = false;
          modelsPrompt.textContent = models.length ? 'Select a model (' + models.length + ' available)' : 'No models found. Start Ollama/LM Studio or add API keys.';
        }
      } catch (e) {
        modelsPrompt.textContent = 'Failed to load models: ' + (e.message || 'Network error');
        modelsPrompt.style.color = '#dc2626';
        modelSelect.disabled = false;
      } finally {
        isLoading = false;
        if (btnRefresh) btnRefresh.disabled = false;
      }
    }

    async function saveAndClose() {
      const newProvider = currentProvider;
      const newModel = currentProvider === 'Built-in' ? currentModel : modelSelect.value;
      const newBaseUrl = inputBaseUrl.value.trim();
      const newApiKey = inputApiKey.value;
      const cfg = await getConfig();
      const providerChanged = newProvider !== (cfg.provider || 'Ollama');
      const keysChanged = (newBaseUrl !== (cfg.baseUrl || '')) || (PROVIDER_NEEDS_KEY.includes(newProvider) && newApiKey && newApiKey !== '***');

      const updates = { provider: newProvider, model: newModel };
      if (PROVIDER_NEEDS_BASE.includes(newProvider) && newBaseUrl) updates.baseUrl = newBaseUrl;
      if (PROVIDER_NEEDS_KEY.includes(newProvider) && newApiKey && newApiKey !== '***') updates.apiKey = newApiKey;

      const ok = await setConfig(updates);
      if (!ok) return;

      if (providerChanged || keysChanged) {
        restartBackend();
        setTimeout(() => {
          updateInlineLabel(newModel, newProvider);
        }, 2000);
      } else if (newModel) {
        try {
          await patchModel(newModel);
          currentModel = newModel;
          updateInlineLabel(newModel, newProvider);
        } catch (e) {
          modelsPrompt.textContent = 'Failed to switch: ' + (e.message || '');
          modelsPrompt.style.color = '#dc2626';
          return;
        }
      }

    }

    const brainSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>';
    const navModels = document.querySelector('.side-nav-item[data-page="models"]');
    if (navModels) navModels.addEventListener('click', () => loadConfigAndModels());
    if (btnModel) btnModel.addEventListener('click', e => { e.stopImmediatePropagation(); showModelsPage(); });
    if (btnSave) btnSave.addEventListener('click', e => { e.stopImmediatePropagation(); saveAndClose(); });
    if (btnRefresh) btnRefresh.addEventListener('click', e => { e.stopImmediatePropagation(); loadModels(); });

    providersList.querySelectorAll('.model-provider-item').forEach(b => {
      b.addEventListener('click', async (e) => {
        e.stopImmediatePropagation();
        currentProvider = b.dataset.provider;
        providersList.querySelectorAll('.model-provider-item').forEach(x => x.classList.toggle('active', x === b));
        fieldBaseUrl.hidden = !PROVIDER_NEEDS_BASE.includes(currentProvider);
        fieldApiKey.hidden = !PROVIDER_NEEDS_KEY.includes(currentProvider);
        await loadModels();
      });
    });

    function pollModel() {
      fetchCurrentModel().then(({ provider, model }) => {
        updateInlineLabel(model, provider);
      }).catch(() => {});
    }

    if (typeof window.addEventListener === 'function') {
      window.addEventListener('backend-url', () => { backendUrl = ''; pollModel(); });
    }
    pollModel();
    setInterval(pollModel, 15000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModelSelector);
  } else {
    initModelSelector();
  }
})();
