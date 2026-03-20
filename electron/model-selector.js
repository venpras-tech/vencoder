(function () {
  const PROVIDERS = ['Built-in', 'Ollama', 'LM Studio', 'OpenAI', 'Anthropic', 'Google'];
  const PROVIDER_NEEDS_BASE = ['Ollama', 'LM Studio'];
  const PROVIDER_NEEDS_KEY = ['OpenAI', 'Anthropic', 'Google'];
  const PROVIDER_LOCAL_PARAMS = ['Built-in', 'Ollama'];

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

  const MODEL_DESCRIPTIONS = {
    'qwen2.5-0.5b': 'Compact instruction-tuned model for fast inference on low-resource devices.',
    'qwen2.5-1.5b': 'Lightweight Qwen model suitable for quick tasks and limited hardware.',
    'qwen2.5-3b': 'Balanced Qwen model for general coding and chat on modest hardware.',
    'llama-3.2-1b': 'Meta\'s smallest Llama 3.2, ideal for edge and mobile deployment.',
    'llama-3.2-3b': 'Efficient Llama 3.2 for coding and reasoning on consumer hardware.',
    'phi-3.5-mini': 'Microsoft Phi-3.5, strong reasoning in a small footprint.',
    'qwen3.5-4b': 'Capable Qwen3.5 for coding assistance and general tasks.',
    'qwen3.5-9b': 'Larger Qwen3.5 for complex coding and multi-step reasoning.'
  };

  const FALLBACK_SUGGESTED = [
    { id: 'qwen2.5-0.5b-q4', name: 'Qwen2.5 0.5B (Q4)', repo: 'Qwen/Qwen2.5-0.5B-Instruct-GGUF', file: 'qwen2.5-0.5b-instruct-q4_k_m.gguf', size_gb: 0.5, tier: 'low', params: '0.5B' },
    { id: 'qwen2.5-1.5b-q4', name: 'Qwen2.5 1.5B (Q4)', repo: 'Qwen/Qwen2.5-1.5B-Instruct-GGUF', file: 'qwen2.5-1.5b-instruct-q4_k_m.gguf', size_gb: 1.1, tier: 'low', params: '1.5B' },
    { id: 'qwen2.5-3b-q4', name: 'Qwen2.5 3B (Q4)', repo: 'Qwen/Qwen2.5-3B-Instruct-GGUF', file: 'qwen2.5-3b-instruct-q4_k_m.gguf', size_gb: 2.0, tier: 'low', params: '3B' },
    { id: 'llama-3.2-1b-q8', name: 'Llama 3.2 1B (Q8)', repo: 'hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF', file: 'Llama-3.2-1B-Instruct-Q8_0.gguf', size_gb: 1.2, tier: 'low', params: '1B' },
    { id: 'llama-3.2-3b-q4', name: 'Llama 3.2 3B (Q4)', repo: 'bartowski/Llama-3.2-3B-Instruct-GGUF', file: 'Llama-3.2-3B-Instruct-Q4_K_M.gguf', size_gb: 2.0, tier: 'medium', params: '3B' },
    { id: 'phi-3.5-mini-q4', name: 'Phi-3.5 Mini (Q4)', repo: 'MaziyarPanahi/Phi-3.5-mini-instruct-GGUF', file: 'Phi-3.5-mini-instruct.Q4_K_M.gguf', size_gb: 2.3, tier: 'medium', params: '3.8B' },
    { id: 'qwen3.5-4b-q4', name: 'Qwen3.5 4B (Q4)', repo: 'unsloth/Qwen3.5-4B-GGUF', file: 'Qwen3.5-4B-Q4_K_M.gguf', size_gb: 2.7, tier: 'medium', params: '4B' },
    { id: 'qwen3.5-9b-q4', name: 'Qwen3.5 9B (Q4)', repo: 'lmstudio-community/Qwen3.5-9B-GGUF', file: 'Qwen3.5-9B-Q4_K_M.gguf', size_gb: 5.5, tier: 'high', params: '9B' }
  ];

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

  async function cancelBuiltinDownload(filename) {
    const base = await getBackendUrl();
    if (!base) return;
    try {
      await fetch(`${base}/builtin/download-cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
        signal: AbortSignal.timeout(5000)
      });
    } catch (_) {}
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

  function showModelToast(message, type) {
    const toast = document.getElementById('download-toast');
    const text = document.getElementById('download-toast-text');
    const icon = toast ? toast.querySelector('.download-toast-icon') : null;
    if (!toast || !text) return;
    text.textContent = message;
    if (icon) icon.textContent = type === 'error' ? '\u2715' : (type === 'info' ? '\u2139' : '\u2713');
    toast.classList.toggle('download-toast-error', type === 'error');
    toast.classList.toggle('download-toast-info', type === 'info');
    toast.hidden = false;
    clearTimeout(showModelToast._tid);
    showModelToast._tid = setTimeout(function() { toast.hidden = true; }, 3000);
  }

  async function downloadBuiltinModel(repoId, filename, onProgress, signal) {
    const base = await getBackendUrl();
    if (!base) throw new Error('Backend not ready');
    const r = await fetch(`${base}/builtin/download-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_id: repoId, filename }),
      signal: signal || AbortSignal.timeout(600000)
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
    return a && a.getLLMConfig ? a.getLLMConfig() : Promise.resolve({ provider: 'Built-in', model: '', baseUrl: '', apiKey: '' });
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
    if (btn) {
      const text = model ? `${provider || 'Model'}: ${model}` : 'Switch model';
      btn.title = text;
    }
    const sideNav = document.getElementById('side-nav-model');
    if (sideNav) sideNav.textContent = model ? `Model: ${model} · ${provider || 'Built-in'}` : 'Model: —';
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
    const modelBuiltinProviderDesc = document.getElementById('model-builtin-provider-desc');
    const modelsPrompt = document.getElementById('model-models-prompt');
    const fieldBaseUrl = document.getElementById('model-field-base-url');
    const fieldApiKey = document.getElementById('model-field-api-key');
    const fieldLocalParams = document.getElementById('model-field-local-params');
    const inputBaseUrl = document.getElementById('model-base-url');
    const inputApiKey = document.getElementById('model-api-key');
    const inputNumCtx = document.getElementById('model-num-ctx');
    const inputRepeatPenalty = document.getElementById('model-repeat-penalty');

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
      pollModel();
      const cfg = await getConfig();
      currentProvider = cfg.provider || 'Built-in';
      currentModel = cfg.model || '';
      inputBaseUrl.value = cfg.baseUrl || '';
      inputApiKey.value = cfg.apiKey ? '***' : '';
      if (inputNumCtx) inputNumCtx.value = (cfg.numCtx === undefined || cfg.numCtx === null) ? '' : String(cfg.numCtx);
      if (inputRepeatPenalty) inputRepeatPenalty.value = (cfg.repeatPenalty === undefined || cfg.repeatPenalty === null) ? '' : String(cfg.repeatPenalty);

      providersList.querySelectorAll('.model-provider-item').forEach(b => {
        b.classList.toggle('active', b.dataset.provider === currentProvider);
      });

      fieldBaseUrl.hidden = !PROVIDER_NEEDS_BASE.includes(currentProvider);
      fieldApiKey.hidden = !PROVIDER_NEEDS_KEY.includes(currentProvider);
      if (fieldLocalParams) fieldLocalParams.hidden = !PROVIDER_LOCAL_PARAMS.includes(currentProvider);

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
              const item = Array.from(modelBuiltinList.querySelectorAll('.model-builtin-card')).find(function(el) { return el.dataset.file === file; });
              if (item) {
                const wrap = item.querySelector('.model-builtin-download-wrap');
                const progressEl = wrap ? wrap.querySelector('[data-progress]') : null;
                const btn = wrap ? wrap.querySelector('.model-builtin-download') : null;
                const cancelBtn = wrap ? wrap.querySelector('[data-cancel]') : null;
                if (progressEl && btn) {
                  progressEl.hidden = false;
                  btn.hidden = true;
                  if (cancelBtn) cancelBtn.hidden = false;
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
          let suggested = suggestedData.suggested || [];
          if (suggested.length === 0) {
            const tier = sysInfo.tier || 'medium';
            const ramGb = sysInfo.ram_gb || 8;
            suggested = FALLBACK_SUGGESTED.map(function(m) {
              const stem = (m.file || '').replace(/\.gguf$/i, '');
              const installed = models.indexOf(stem) >= 0;
              const rec = m.tier === tier || (m.size_gb <= ramGb * 0.5) || (m.size_gb <= ramGb);
              return { ...m, installed, recommended: rec };
            }).sort(function(a, b) {
              return (a.recommended === b.recommended ? 0 : (a.recommended ? -1 : 1)) || (a.size_gb - b.size_gb);
            });
          }
          const llamaCppAvailable = suggestedData.llama_cpp_available !== false;
          if (modelBuiltinSystem) {
            modelBuiltinSystem.hidden = false;
            var sysText = 'Your system: ' + sysInfo.ram_gb + ' GB RAM — suggested for ' + sysInfo.tier + ' tier';
            if (!llamaCppAvailable) sysText += '. First download will install llama-cpp-python (required)';
            modelBuiltinSystem.textContent = sysText;
          }
          if (modelBuiltinProviderDesc) modelBuiltinProviderDesc.hidden = false;
          const folderSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
          const deleteSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';
          const checkSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
          if (modelBuiltinList) {
            modelBuiltinList.innerHTML = suggested.map(function(s) {
              const stem = s.file.replace(/\.gguf$/i, '');
              const installed = s.installed;
              const dl = downloadStatus[s.file];
              const isDownloading = dl && !dl.error && (dl.progress !== undefined ? dl.progress < 1 : !dl.ok);
              const showDownloadUI = !installed || isDownloading;
              const pctVal = (dl && dl.progress !== undefined) ? Math.round(dl.progress * 100) : 0;
              const rec = s.recommended ? '<span class="model-builtin-recommended">Recommended</span>' : '';
              const tierLabel = (s.tier || '').charAt(0).toUpperCase() + (s.tier || '').slice(1);
              const tierBadge = s.tier ? '<span class="model-builtin-tier">' + tierLabel + '</span>' : '';
              const descKey = stem.replace(/-q[48]_[km]$/i, '').replace(/-instruct$/i, '');
              const desc = MODEL_DESCRIPTIONS[descKey] || (s.params + ' parameters. ' + (s.size_gb || '') + ' GB.');
              const source = (s.repo || '').split('/')[0] || 'Hugging Face';
              const cancelSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>';
              var actions = '';
              if (installed && !isDownloading) {
                var isActive = stem === currentModel;
                var useCls = 'model-builtin-btn model-builtin-use' + (isActive ? ' model-builtin-use-active' : '');
                var useBtn = '<button type="button" class="' + useCls + '" data-use data-stem="' + stem + '">Use</button>';
                actions = '<div class="model-builtin-card-actions">' +
                  '<button type="button" class="model-builtin-icon-btn" data-open-folder title="Open folder">' + folderSvg + '</button>' +
                  '<button type="button" class="model-builtin-icon-btn" data-delete title="Delete model">' + deleteSvg + '</button>' +
                  useBtn + '</div>';
              } else {
                var progressHidden = !isDownloading;
                var cancelHidden = !isDownloading;
                var downloadHidden = isDownloading;
                actions = '<div class="model-builtin-download-wrap">' +
                  '<div class="model-download-progress" data-progress' + (progressHidden ? ' hidden' : '') + '>' +
                  '<div class="model-download-progress-track"><div class="model-download-progress-bar" style="width:' + pctVal + '%"></div></div>' +
                  '<span class="model-download-progress-text">' + pctVal + '%</span></div>' +
                  '<button type="button" class="model-builtin-btn model-builtin-cancel" data-cancel title="Cancel download"' + (cancelHidden ? ' hidden' : '') + '>' + cancelSvg + ' Cancel</button>' +
                  '<button type="button" class="model-builtin-btn model-builtin-download" data-download' + (downloadHidden ? ' hidden' : '') + '>Download</button></div>';
              }
              const repoTitle = (s.repo || '') ? 'Source: ' + s.repo + '/' + (s.file || '') : '';
              const safeTitle = (repoTitle || '').replace(/"/g, '&#34;');
              return '<div class="model-builtin-card" data-repo="' + (s.repo || '') + '" data-file="' + (s.file || '') + '" data-stem="' + stem + '"' + (safeTitle ? ' title="' + safeTitle + '"' : '') + '>' +
                '<div class="model-builtin-card-header">' +
                '<span class="model-builtin-card-icon">' + brainSvg + '</span>' +
                '<div class="model-builtin-card-title-row">' +
                '<span class="model-builtin-name">' + s.name + '</span>' +
                '</div>' +
                '<span class="model-builtin-card-size">' + (s.size_gb || '') + ' GB</span>' +
                '</div>' +
                '<div class="model-builtin-chip-row">' + tierBadge + rec + '</div>' +
                '<div class="model-builtin-card-source">Source: ' + source + '</div>' +
                '<p class="model-builtin-card-desc">' + desc + '</p>' +
                '<div class="model-builtin-card-footer">' + actions + '</div>' +
                '</div>';
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
                var item = btn.closest('.model-builtin-card');
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
            var downloadAbortMap = {};
            modelBuiltinList.querySelectorAll('[data-cancel]').forEach(function(btn) {
              btn.addEventListener('click', async function(e) {
                e.stopImmediatePropagation();
                if (!confirm('Are you sure you want to cancel? Any partially downloaded content will be removed.')) return;
                var item = btn.closest('.model-builtin-card');
                var file = item.dataset.file;
                await cancelBuiltinDownload(file);
                var ac = downloadAbortMap[file];
                if (ac) ac.abort();
                delete downloadAbortMap[file];
                for (var i = 0; i < 3; i++) {
                  await new Promise(function(r) { setTimeout(r, 400 + i * 300); });
                  try {
                    await deleteBuiltinModel(file);
                    break;
                  } catch (_) {}
                }
                var wrap = btn.closest('.model-builtin-download-wrap');
                var progressEl = wrap ? wrap.querySelector('[data-progress]') : null;
                var downloadBtn = wrap ? wrap.querySelector('.model-builtin-download') : null;
                if (progressEl) progressEl.hidden = true;
                btn.hidden = true;
                if (downloadBtn) downloadBtn.hidden = false;
                updateDownloadStatusBar({});
                var bar = document.getElementById('download-status-bar');
                if (bar) bar.hidden = true;
                showModelToast('Download cancelled', 'info');
                await loadModels();
              });
            });
            modelBuiltinList.querySelectorAll('.model-builtin-download').forEach(function(btn) {
              btn.addEventListener('click', async function(e) {
                e.stopImmediatePropagation();
                var item = btn.closest('.model-builtin-card');
                var repo = item.dataset.repo;
                var file = item.dataset.file;
                var stem = item.dataset.stem;
                var wrap = btn.closest('.model-builtin-download-wrap');
                var progressEl = wrap ? wrap.querySelector('[data-progress]') : null;
                var cancelBtn = wrap ? wrap.querySelector('[data-cancel]') : null;
                var ac = new AbortController();
                downloadAbortMap[file] = ac;
                btn.hidden = true;
                if (progressEl) progressEl.hidden = false;
                if (cancelBtn) cancelBtn.hidden = false;
                updateDownloadStatusBar({ [file]: { progress: 0, downloaded: 0, total: 1 } });
                if (!downloadPollId) downloadPollId = setInterval(downloadPollTick, 1500);
                function onProgress(pct, downloaded, total) {
                  if (!progressEl) return;
                  var bar = progressEl.querySelector('.model-download-progress-bar');
                  var text = progressEl.querySelector('.model-download-progress-text');
                  var pctVal = Math.round(pct * 100);
                  if (bar) bar.style.width = pctVal + '%';
                  if (text) text.textContent = pctVal + '%';
                }
                try {
                  var result = await downloadBuiltinModel(repo, file, onProgress, ac.signal);
                  delete downloadAbortMap[file];
                  if (!result || !result.ok) {
                    if (progressEl) progressEl.hidden = true;
                    if (cancelBtn) cancelBtn.hidden = true;
                    btn.hidden = false;
                    var bar = document.getElementById('download-status-bar');
                    if (bar) bar.hidden = true;
                    updateDownloadStatusBar({});
                    showModelToast('Download incomplete', 'info');
                    await loadModels();
                    return;
                  }
                  models.push(stem);
                  var opt = createOption(stem, stem === currentModel);
                  if (modelSelect) modelSelect.appendChild(opt);
                  var bar = document.getElementById('download-status-bar');
                  if (bar) bar.hidden = true;
                  showDownloadCompleteToast(stem, false);
                  await loadModels();
                } catch (err) {
                  delete downloadAbortMap[file];
                  if (err.name === 'AbortError') {
                    await cancelBuiltinDownload(file);
                  }
                  btn.hidden = false;
                  btn.disabled = false;
                  if (progressEl) progressEl.hidden = true;
                  if (cancelBtn) cancelBtn.hidden = true;
                  var bar = document.getElementById('download-status-bar');
                  if (bar) bar.hidden = true;
                  updateDownloadStatusBar({});
                  if (err.name === 'AbortError') {
                    showModelToast('Download cancelled', 'info');
                  } else {
                    modelsPrompt.textContent = 'Download failed: ' + (err.message || '');
                    modelsPrompt.style.color = '#dc2626';
                    showDownloadCompleteToast(err.message || 'model', true);
                  }
                  await loadModels();
                }
              });
            });
            modelBuiltinList.querySelectorAll('.model-builtin-use').forEach(function(btn) {
              btn.addEventListener('click', async function(e) {
                e.stopImmediatePropagation();
                var stem = btn.dataset.stem;
                if (stem === currentModel) {
                  currentModel = '';
                  if (modelSelect) modelSelect.value = '';
                } else {
                  selectAndUse(stem);
                }
                var ok = await setConfig({ provider: currentProvider, model: currentModel });
                if (ok) {
                  try {
                    await patchModel(currentModel);
                    updateInlineLabel(currentModel, currentProvider);
                    showModelToast(currentModel ? 'Model set to ' + currentModel : 'Model unloaded', 'success');
                  } catch (err) {
                    modelsPrompt.textContent = 'Failed to switch: ' + (err.message || '');
                    modelsPrompt.style.color = '#dc2626';
                    showModelToast('Failed: ' + (err.message || ''), 'error');
                  }
                } else {
                  showModelToast('Failed to save config', 'error');
                }
                await loadModels();
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
          if (modelBuiltinWrap) modelBuiltinWrap.hidden = true;
          if (modelBuiltinProviderDesc) modelBuiltinProviderDesc.hidden = true;
          if (modelBuiltinSystem) { modelBuiltinSystem.hidden = true; modelBuiltinSystem.textContent = ''; }
          if (modelBuiltinList) modelBuiltinList.innerHTML = '';
          if (modelFieldSelect) modelFieldSelect.hidden = false;
          const data = await fetchModels(currentProvider);
          models = data.models || [];
          var ph = createOption('', false);
          ph.textContent = models.length ? '— Select model —' : '— No models found —';
          modelSelect.appendChild(ph);
          models.forEach(function(m) { modelSelect.appendChild(createOption(m, m === currentModel)); });
          modelSelect.disabled = false;
          var noModelsMsg = 'No models found.';
          if (currentProvider === 'LM Studio') noModelsMsg += ' Start LM Studio and load a model.';
          else if (currentProvider === 'Ollama') noModelsMsg += ' Start Ollama.';
          else noModelsMsg += ' Add API keys for cloud providers.';
          modelsPrompt.textContent = models.length ? 'Select a model (' + models.length + ' available)' : noModelsMsg;
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
      const newNumCtx = (PROVIDER_LOCAL_PARAMS.includes(newProvider) && inputNumCtx) ? (inputNumCtx.value.trim() === '' ? '' : parseInt(inputNumCtx.value, 10)) : undefined;
      const newRepeatPenalty = (PROVIDER_LOCAL_PARAMS.includes(newProvider) && inputRepeatPenalty) ? (inputRepeatPenalty.value.trim() === '' ? '' : parseFloat(inputRepeatPenalty.value)) : undefined;
      const localParamsChanged = PROVIDER_LOCAL_PARAMS.includes(newProvider) && (
        (newNumCtx !== undefined && String(newNumCtx) !== String(cfg.numCtx ?? '')) ||
        (newRepeatPenalty !== undefined && String(newRepeatPenalty) !== String(cfg.repeatPenalty ?? ''))
      );

      const updates = { provider: newProvider, model: newModel };
      if (PROVIDER_NEEDS_BASE.includes(newProvider) && newBaseUrl) updates.baseUrl = newBaseUrl;
      if (PROVIDER_NEEDS_KEY.includes(newProvider) && newApiKey && newApiKey !== '***') updates.apiKey = newApiKey;
      if (PROVIDER_LOCAL_PARAMS.includes(newProvider) && inputNumCtx) {
        updates.numCtx = inputNumCtx.value.trim() === '' ? '' : parseInt(inputNumCtx.value, 10);
      }
      if (PROVIDER_LOCAL_PARAMS.includes(newProvider) && inputRepeatPenalty) {
        updates.repeatPenalty = inputRepeatPenalty.value.trim() === '' ? '' : parseFloat(inputRepeatPenalty.value);
      }

      const ok = await setConfig(updates);
      if (!ok) return;

      if (providerChanged || keysChanged || localParamsChanged) {
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
        if (fieldLocalParams) fieldLocalParams.hidden = !PROVIDER_LOCAL_PARAMS.includes(currentProvider);
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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModelSelector);
  } else {
    initModelSelector();
  }
})();
