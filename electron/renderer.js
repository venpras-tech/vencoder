const messagesEl = document.getElementById('messages');
const activityEl = document.getElementById('activity');
const form = document.getElementById('form');
const input = document.getElementById('input');
const submit = document.getElementById('submit');
const modelStatusEl = document.getElementById('model-status');
const modelNameEl = document.getElementById('model-name');
const modelDropdown = document.getElementById('model-dropdown');
const modelDropdownCurrent = document.getElementById('model-dropdown-current');
const modelChangeBtn = document.getElementById('model-change-btn');
const modelModal = document.getElementById('model-modal');
const modelModalClose = document.getElementById('model-modal-close');
const modelModalSave = document.getElementById('model-modal-save');
const modelSelect = document.getElementById('model-select');
const btnIndex = document.getElementById('btn-index');
const btnRetry = document.getElementById('btn-retry');
const btnCancel = document.getElementById('btn-cancel');
const projectPathBtn = document.getElementById('project-path');
const projectPathText = document.getElementById('project-path-text');
const historyListEl = document.getElementById('history-list');
const navNewChat = document.getElementById('nav-new-chat');
const connectingBanner = document.getElementById('connecting-banner');
const connectingText = document.getElementById('connecting-text');
const connectingRetry = document.getElementById('connecting-retry');

let baseUrl = '';
let messageHistory = [];
let historyIndex = -1;
let currentModelName = 'gpt-oss:20b';
let currentChatAbortController = null;
let currentConversationId = null;
let conversationsList = [];

function setProjectPathDisplay(pathStr) {
  if (projectPathText) projectPathText.textContent = pathStr || 'No folder selected';
}

function setModelStatus(connected) {
  if (modelStatusEl) modelStatusEl.classList.toggle('error', !connected);
}

function setModelName(name) {
  currentModelName = name || 'gpt-oss:20b';
  modelNameEl.textContent = currentModelName;
  if (modelDropdownCurrent) modelDropdownCurrent.textContent = currentModelName + ' – Ollama';
}

function addActivity(text, type = 'status') {
  if (!activityEl) return;
  const item = document.createElement('div');
  item.className = 'activity-item activity-' + type;
  const label = document.createElement('span');
  label.className = 'activity-label';
  label.textContent = type === 'tool' ? 'Tool' : type === 'error' ? 'Error' : type === 'index' ? 'Index' : 'Status';
  const body = document.createElement('span');
  body.className = 'activity-body';
  body.textContent = text;
  item.appendChild(label);
  item.appendChild(body);
  activityEl.appendChild(item);
  activityEl.scrollTop = activityEl.scrollHeight;
}

function clearActivity() {
  if (activityEl) activityEl.innerHTML = '';
}

function formatHistoryDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const dDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  if (dDate.getTime() === today.getTime()) return 'Today';
  if (dDate.getTime() === yesterday.getTime()) return 'Yesterday';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function renderHistoryList() {
  if (!historyListEl) return;
  const byDate = {};
  conversationsList.forEach((c) => {
    const key = formatHistoryDate(c.created_at);
    if (!byDate[key]) byDate[key] = [];
    byDate[key].push(c);
  });
  const order = ['Today', 'Yesterday'];
  const keys = Object.keys(byDate).sort((a, b) => {
    const ai = order.indexOf(a);
    const bi = order.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return new Date(byDate[b][0].created_at) - new Date(byDate[a][0].created_at);
  });
  historyListEl.innerHTML = '';
  keys.forEach((label) => {
    const group = document.createElement('div');
    group.className = 'history-group';
    const heading = document.createElement('div');
    heading.className = 'history-group-label';
    heading.textContent = label;
    group.appendChild(heading);
    byDate[label].forEach((c) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'nav-item history-item' + (c.id === currentConversationId ? ' active' : '');
      item.dataset.id = String(c.id);
      item.textContent = c.title || 'New chat';
      item.title = c.title || 'New chat';
      group.appendChild(item);
    });
    historyListEl.appendChild(group);
  });
}

async function fetchHistory() {
  try {
    const r = await fetch(baseUrl + '/history');
    if (!r.ok) return;
    const data = await r.json();
    conversationsList = data.conversations || [];
    renderHistoryList();
  } catch (_) {}
}

function clearMessages() {
  if (messagesEl) messagesEl.innerHTML = '';
  messageHistory = [];
  historyIndex = -1;
}

function setActiveConversation(id) {
  currentConversationId = id;
  if (historyListEl) {
    historyListEl.querySelectorAll('.history-item').forEach((el) => {
      el.classList.toggle('active', Number(el.dataset.id) === id);
    });
  }
  if (navNewChat) navNewChat.classList.toggle('active', id == null);
}

async function loadConversation(id) {
  try {
    const r = await fetch(baseUrl + '/history/' + id);
    if (!r.ok) return;
    const data = await r.json();
    const messages = data.messages || [];
    clearMessages();
    messages.forEach((m) => appendMessage(m.role, m.content));
    setActiveConversation(id);
  } catch (_) {}
}

function timeStr() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function appendMessage(role, content) {
  if (!messagesEl) return null;
  const wrap = document.createElement('div');
  wrap.className = 'msg-wrap ' + role;
  const time = document.createElement('div');
  time.className = 'msg-time';
  time.textContent = timeStr();
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = content;
  wrap.appendChild(time);
  wrap.appendChild(div);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  messageHistory.push({ role, content });
  historyIndex = messageHistory.length;
  return div;
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function computeLineDiff(oldStr, newStr) {
  const oldLines = (oldStr || '').split(/\n/);
  const newLines = (newStr || '').split(/\n/);
  const n = oldLines.length;
  const m = newLines.length;
  const dp = Array(n + 1).fill(null).map(() => Array(m + 1).fill(0));
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }
  const result = [];
  let i = n, j = m;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.push({ type: 'same', line: oldLines[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: 'add', line: newLines[j - 1] });
      j--;
    } else {
      result.push({ type: 'remove', line: oldLines[i - 1] });
      i--;
    }
  }
  return result.reverse();
}

function renderDiffHtml(path, oldText, newText) {
  const diff = computeLineDiff(oldText, newText);
  const title = '<div class="reply-block-title">File: ' + escapeHtml(path) + '</div>';
  const legend = '<div class="diff-legend">' +
    '<span class="diff-legend-remove"></span> Deleted ' +
    '<span class="diff-legend-add"></span> Added ' +
    '<span class="diff-legend-same"></span> Unchanged</div>';
  let body = '<div class="diff-view-unified"><div class="diff-lines">';
  let oldNum = 0, newNum = 0;
  for (const entry of diff) {
    if (entry.type === 'same') {
      oldNum++;
      newNum++;
      body += '<div class="diff-line diff-line-same">' +
        '<span class="diff-num diff-num-old">' + oldNum + '</span>' +
        '<span class="diff-num diff-num-new">' + newNum + '</span>' +
        '<span class="diff-line-content">' + escapeHtml(entry.line) + '</span></div>';
    } else if (entry.type === 'remove') {
      oldNum++;
      body += '<div class="diff-line diff-line-remove">' +
        '<span class="diff-num diff-num-old">' + oldNum + '</span>' +
        '<span class="diff-num diff-num-new"></span>' +
        '<span class="diff-line-content">' + escapeHtml(entry.line) + '</span></div>';
    } else {
      newNum++;
      body += '<div class="diff-line diff-line-add">' +
        '<span class="diff-num diff-num-old"></span>' +
        '<span class="diff-num diff-num-new">' + newNum + '</span>' +
        '<span class="diff-line-content">' + escapeHtml(entry.line) + '</span></div>';
    }
  }
  body += '</div></div>';
  return title + legend + body;
}

function getOrCreateAssistantBubble() {
  if (!messagesEl) return null;
  const last = messagesEl.lastElementChild;
  if (last && last.classList.contains('assistant-wrap')) {
    const msg = last.querySelector('.msg.assistant');
    const stepsEl = last.querySelector('.reply-steps');
    const blocksEl = last.querySelector('.reply-blocks');
    if (msg && stepsEl) return { bubble: msg, steps: stepsEl, blocks: blocksEl };
  }
  const wrap = document.createElement('div');
  wrap.className = 'msg-wrap assistant-wrap';
  const time = document.createElement('div');
  time.className = 'msg-time';
  time.textContent = timeStr();
  const stepsEl = document.createElement('div');
  stepsEl.className = 'reply-steps';
  stepsEl.setAttribute('aria-live', 'polite');
  const blocksEl = document.createElement('div');
  blocksEl.className = 'reply-blocks';
  const div = document.createElement('div');
  div.className = 'msg assistant streaming';
  div.textContent = '';
  wrap.appendChild(time);
  wrap.appendChild(stepsEl);
  wrap.appendChild(blocksEl);
  wrap.appendChild(div);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { bubble: div, steps: stepsEl, blocks: blocksEl };
}
function addStep(stepsEl, text, detail, isDone = false) {
  const item = document.createElement('div');
  item.className = 'reply-step' + (isDone ? ' reply-step-done' : '');
  const icon = document.createElement('span');
  icon.className = 'reply-step-icon';
  icon.textContent = isDone ? '✓' : '…';
  const body = document.createElement('span');
  body.className = 'reply-step-body';
  body.textContent = text;
  item.appendChild(icon);
  item.appendChild(body);
  if (detail) {
    const preview = document.createElement('div');
    preview.className = 'reply-step-preview';
    preview.textContent = detail;
    item.appendChild(preview);
  }
  stepsEl.appendChild(item);
  stepsEl.scrollTop = stepsEl.scrollHeight;
}

async function ensureBackendUrl() {
  if (window.electronAPI && window.electronAPI.getBackendUrl) {
    baseUrl = await window.electronAPI.getBackendUrl();
  } else {
    baseUrl = 'http://127.0.0.1:8765';
  }
}

async function checkHealth() {
  try {
    const r = await fetch(baseUrl + '/health');
    if (r.ok) {
      const data = await r.json();
      setModelStatus(data.ollama === true);
      return true;
    }
  } catch (_) {}
  setModelStatus(false);
  return false;
}

if (form && input && submit) {
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  appendMessage('user', text);
  submit.disabled = true;
  input.disabled = true;
  clearActivity();

  let bubble, steps, blocks;
  try {
    const out = getOrCreateAssistantBubble();
    if (!out) {
      submit.disabled = false;
      input.disabled = false;
      return;
    }
    bubble = out.bubble;
    steps = out.steps || null;
    blocks = out.blocks || null;
  } catch (err) {
    console.error(err);
    submit.disabled = false;
    input.disabled = false;
    return;
  }
  bubble.textContent = '';
  bubble.classList.add('streaming');
  if (steps) {
    steps.innerHTML = '';
    steps.hidden = false;
  }
  if (blocks) blocks.innerHTML = '';

  currentChatAbortController = new AbortController();
  if (btnCancel) btnCancel.hidden = false;

  try {
    const r = await fetch(baseUrl + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        conversation_id: currentConversationId || undefined
      }),
      signal: currentChatAbortController.signal
    });
    if (!r.ok) throw new Error(r.statusText);
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let streamingPhase = false;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'phase') {
              if (data.phase === 'processing' && steps) addStep(steps, 'Processing your message…');
              else if (data.phase === 'streaming') {
                if (!streamingPhase && steps) addStep(steps, 'Writing reply…');
                streamingPhase = true;
              }
            } else if (data.type === 'token' && data.content) {
              if (!streamingPhase) {
                if (steps) addStep(steps, 'Writing reply…');
                streamingPhase = true;
              }
              bubble.textContent += data.content;
              if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
            } else if (data.type === 'tool_start' && data.tool) {
              if (steps) addStep(steps, 'Using tool: ' + data.tool);
              addActivity('Calling tool: ' + data.tool, 'status');
            } else if (data.type === 'status' && data.content) {
              addActivity(data.content, 'status');
            } else if (data.type === 'tool_done') {
              const preview = data.preview ? (String(data.preview).slice(0, 200) + (String(data.preview).length > 200 ? '…' : '')) : '';
              if (steps) addStep(steps, 'Done: ' + data.tool, preview || null, true);
              addActivity('Done: ' + data.tool + (preview ? ' — ' + preview : ''), 'tool');
            } else if (data.type === 'file_edit' && blocks) {
              const block = document.createElement('div');
              block.className = 'reply-block reply-block-diff';
              const path = String(data.path || '');
              const oldText = String(data.old ?? '');
              const newText = String(data.new ?? '');
              block.innerHTML = renderDiffHtml(path, oldText, newText);
              blocks.appendChild(block);
              if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
            } else if (data.type === 'shell_run' && blocks) {
              const block = document.createElement('div');
              block.className = 'reply-block reply-block-shell';
              const cmd = String(data.command || '');
              const stdout = String(data.stdout ?? '');
              const stderr = String(data.stderr ?? '');
              const exitCode = data.exit_code != null ? Number(data.exit_code) : null;
              let outHtml = '<div class="reply-block-title">Shell</div>';
              outHtml += '<div class="shell-section"><div class="shell-label">Command</div><pre class="shell-command">' + escapeHtml(cmd) + '</pre></div>';
              if (stdout) outHtml += '<div class="shell-section"><div class="shell-label">stdout</div><pre class="shell-output">' + escapeHtml(stdout) + '</pre></div>';
              if (stderr) outHtml += '<div class="shell-section"><div class="shell-label">stderr</div><pre class="shell-output shell-stderr">' + escapeHtml(stderr) + '</pre></div>';
              if (exitCode != null) outHtml += '<div class="shell-exit">Exit code: ' + escapeHtml(String(exitCode)) + '</div>';
              block.innerHTML = outHtml;
              blocks.appendChild(block);
              if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
            } else if (data.type === 'error') {
              if (steps) addStep(steps, 'Error: ' + data.content, null, true);
              addActivity(data.content, 'error');
              bubble.textContent += '\n[Error: ' + data.content + ']';
            } else if (data.type === 'conversation' && data.id != null) {
              currentConversationId = data.id;
              conversationsList.unshift({
                id: data.id,
                title: data.title || 'New chat',
                created_at: new Date().toISOString()
              });
              renderHistoryList();
            } else if (data.type === 'conversation_title' && data.id != null && data.title) {
              const c = conversationsList.find((x) => x.id === data.id);
              if (c) c.title = data.title;
              const btn = historyListEl.querySelector('.history-item[data-id="' + data.id + '"]');
              if (btn) btn.textContent = data.title;
            }
          } catch (_) {}
        }
      }
    }
    if (steps && steps.children.length) steps.hidden = false;
  } catch (err) {
    if (err.name === 'AbortError') {
      if (steps) addStep(steps, 'Cancelled', null, true);
      addActivity('Request cancelled', 'status');
      bubble.textContent += (bubble.textContent ? '\n\n' : '') + '[Cancelled]';
    } else {
      if (steps) addStep(steps, 'Error: ' + err.message, null, true);
      addActivity(err.message, 'error');
      bubble.textContent = (bubble.textContent || '') + (bubble.textContent ? '\n\n' : '') + 'Error: ' + err.message;
    }
  } finally {
    currentChatAbortController = null;
    if (btnCancel) btnCancel.hidden = true;
  }

  bubble.classList.remove('streaming');
  submit.disabled = false;
  input.disabled = false;
});
}

if (btnCancel) btnCancel.addEventListener('click', () => {
  if (currentChatAbortController) currentChatAbortController.abort();
});

if (input) input.addEventListener('keydown', (e) => {
  if (e.ctrlKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    e.preventDefault();
    if (messageHistory.length === 0) return;
    if (e.key === 'ArrowUp') {
      historyIndex = Math.max(0, historyIndex - 1);
    } else {
      historyIndex = Math.min(messageHistory.length, historyIndex + 1);
    }
    if (historyIndex >= 0 && historyIndex < messageHistory.length) {
      const m = messageHistory[historyIndex];
      if (m.role === 'user') input.value = m.content;
    } else {
      input.value = '';
    }
  }
});

if (projectPathBtn) projectPathBtn.addEventListener('click', async () => {
  if (!window.electronAPI || !window.electronAPI.openFolder) return;
  const chosen = await window.electronAPI.openFolder();
  if (chosen) {
    window.electronAPI.setProjectPath(chosen);
    setProjectPathDisplay(chosen);
  }
});

window.electronAPI?.onRequestOpenFolder?.(async () => {
  if (!window.electronAPI?.openFolder) return;
  const chosen = await window.electronAPI.openFolder();
  if (chosen) {
    window.electronAPI.setProjectPath(chosen);
    setProjectPathDisplay(chosen);
  }
});

window.electronAPI?.onProjectPath?.((pathStr) => {
  setProjectPathDisplay(pathStr);
  currentConversationId = null;
  clearMessages();
  fetchHistory();
});

if (navNewChat) {
  navNewChat.addEventListener('click', (e) => {
    e.preventDefault();
    currentConversationId = null;
    clearMessages();
    setActiveConversation(null);
  });
}

historyListEl?.addEventListener('click', (e) => {
  const item = e.target.closest('.history-item');
  if (!item) return;
  const id = Number(item.dataset.id);
  if (!id) return;
  loadConversation(id);
});

if (modelStatusEl) modelStatusEl.addEventListener('click', (e) => {
  e.stopPropagation();
  const isHidden = modelDropdown.hidden;
  modelDropdown.hidden = !isHidden;
  if (!isHidden) return;
  modelDropdownCurrent.textContent = currentModelName + ' – Ollama';
});

if (modelChangeBtn) modelChangeBtn.addEventListener('click', () => {
  modelDropdown.hidden = true;
  openModelModal();
});

document.addEventListener('click', () => {
  modelDropdown.hidden = true;
});

if (modelDropdown) modelDropdown.addEventListener('click', (e) => e.stopPropagation());

async function openModelModal() {
  modelModal.hidden = false;
  try {
    const r = await fetch(baseUrl + '/models');
    const data = await r.json();
    const models = data.models || [];
    modelSelect.innerHTML = '';
    models.forEach((m) => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      if (m === currentModelName) opt.selected = true;
      modelSelect.appendChild(opt);
    });
    if (models.length && !currentModelName) {
      currentModelName = models[0];
      modelSelect.selectedIndex = 0;
    }
  } catch (_) {
    modelSelect.innerHTML = '<option value="">No models available</option>';
  }
}

function closeModelModal() {
  modelModal.hidden = true;
}

if (modelModalClose) modelModalClose.addEventListener('click', closeModelModal);

if (modelModalSave) modelModalSave.addEventListener('click', async () => {
  const model = modelSelect.value;
  if (!model) return;
  try {
    const r = await fetch(baseUrl + '/model', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model })
    });
    if (r.ok) {
      const data = await r.json();
      setModelName(data.model);
      closeModelModal();
    }
  } catch (_) {}
});

if (modelModal) modelModal.addEventListener('click', (e) => {
  if (e.target === modelModal) closeModelModal();
});

if (btnRetry) btnRetry.addEventListener('click', async () => {
  btnRetry.disabled = true;
  const ok = await checkHealth();
  if (ok) {
    try {
      const r = await fetch(baseUrl + '/model');
      if (r.ok) {
        const data = await r.json();
        setModelName(data.model);
      }
    } catch (_) {}
  }
  btnRetry.disabled = false;
});

if (btnIndex) btnIndex.addEventListener('click', async () => {
  btnIndex.disabled = true;
  await ensureBackendUrl();
  addActivity('Indexing workspace…', 'status');
  try {
    const r = await fetch(baseUrl + '/index', { method: 'POST' });
    const data = await r.json();
    if (data.indexed !== undefined) {
      addActivity(`Indexed ${data.indexed} files`, 'index');
      const healthRes = await fetch(baseUrl + '/health');
      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setModelStatus(healthData.ollama === true);
      }
    } else throw new Error(data.detail || 'Index failed');
  } catch (err) {
    const msg = err.message === 'Failed to fetch' ? 'Backend not reachable. Ensure the app backend is running.' : err.message;
    addActivity(msg, 'error');
    setModelStatus(false);
  }
  btnIndex.disabled = false;
});

const BACKEND_CONNECT_TIMEOUT_MS = 45000;
const BACKEND_POLL_INTERVAL_MS = 2000;

function showConnectingBanner(connecting) {
  if (!connectingBanner) return;
  if (connecting) {
    connectingBanner.hidden = false;
    if (connectingText) connectingText.textContent = 'Starting backend…';
    if (connectingRetry) connectingRetry.hidden = true;
  } else {
    connectingBanner.hidden = true;
  }
}

function showBackendFailedBanner() {
  if (!connectingBanner) return;
  connectingBanner.hidden = false;
  if (connectingText) connectingText.textContent = 'Backend could not start.';
  if (connectingRetry) connectingRetry.hidden = false;
}

async function init() {
  await ensureBackendUrl();
  if (window.electronAPI?.getProjectPath) {
    const p = await window.electronAPI.getProjectPath();
    setProjectPathDisplay(p);
  }
  setActiveConversation(null);
  showConnectingBanner(true);
  let ok = await checkHealth();
  if (ok) {
    showConnectingBanner(false);
    fetchHistory();
    if (submit) submit.disabled = false;
    if (input) input.disabled = false;
    try {
      const r = await fetch(baseUrl + '/model');
      if (r.ok) {
        const data = await r.json();
        setModelName(data.model);
      }
    } catch (_) {}
    return;
  }
  const startTime = Date.now();
  const interval = setInterval(async () => {
    if (Date.now() - startTime >= BACKEND_CONNECT_TIMEOUT_MS) {
      clearInterval(interval);
      showBackendFailedBanner();
      return;
    }
    ok = await checkHealth();
    if (ok) {
      clearInterval(interval);
      showConnectingBanner(false);
      if (submit) submit.disabled = false;
      if (input) input.disabled = false;
      fetchHistory();
      const res = await fetch(baseUrl + '/model');
      if (res.ok) {
        const data = await res.json();
        setModelName(data.model);
      }
    }
  }, BACKEND_POLL_INTERVAL_MS);
}

if (connectingRetry) {
  connectingRetry.addEventListener('click', () => {
    if (connectingText) connectingText.textContent = 'Starting backend…';
    connectingRetry.hidden = true;
    showConnectingBanner(true);
    window.electronAPI?.retryBackend?.();
    const startTime = Date.now();
    const interval = setInterval(async () => {
      if (Date.now() - startTime >= BACKEND_CONNECT_TIMEOUT_MS) {
        clearInterval(interval);
        showBackendFailedBanner();
        return;
      }
      const ok = await checkHealth();
      if (ok) {
        clearInterval(interval);
        showConnectingBanner(false);
        if (submit) submit.disabled = false;
        if (input) input.disabled = false;
        fetchHistory();
        const res = await fetch(baseUrl + '/model');
        if (res.ok) {
          const data = await res.json();
          setModelName(data.model);
        }
      }
    }, BACKEND_POLL_INTERVAL_MS);
  });
}

try {
  init();
} catch (err) {
  console.error('Init failed', err);
  if (connectingBanner) {
    connectingBanner.hidden = false;
    if (connectingText) connectingText.textContent = 'Load error: ' + (err.message || String(err));
  }
}
