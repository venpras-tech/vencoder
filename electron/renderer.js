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
const projectPathPageBtn = document.getElementById('project-path-page');
const projectPathTextPage = document.getElementById('project-path-text-page');
const historyListEl = document.getElementById('history-list');
const navNewChat = document.getElementById('nav-new-chat');
const navChat = document.getElementById('nav-chat');
const chatSub = document.getElementById('chat-sub');
const navChatHistory = document.getElementById('nav-chat-history');
const historyPanel = document.getElementById('history-panel');
const historySelectAll = document.getElementById('history-select-all');
const btnHistorySave = document.getElementById('btn-history-save');
const btnHistoryDelete = document.getElementById('btn-history-delete');
const historyLoadMoreWrap = document.getElementById('history-load-more-wrap');
const btnHistoryLoadMore = document.getElementById('btn-history-load-more');
const logsContent = document.getElementById('logs-content');
const btnRefreshLogs = document.getElementById('btn-refresh-logs');
const logPathInput = document.getElementById('log-path-input');
const btnLogPathBrowse = document.getElementById('btn-log-path-browse');
const btnLogPathApply = document.getElementById('btn-log-path-apply');
const connectingBanner = document.getElementById('connecting-banner');
const connectingText = document.getElementById('connecting-text');
const connectingRetry = document.getElementById('connecting-retry');
const bottomBar = document.getElementById('bottom-bar');
const chatWelcomeEl = document.getElementById('chat-welcome');
const projectTreeEl = document.getElementById('project-tree');
const projectEditorPlaceholder = document.getElementById('project-editor-placeholder');
const projectEditorContainer = document.getElementById('project-editor-container');
const contextSelectorEl = document.getElementById('context-selector');
const contextListEl = document.getElementById('context-list');

let baseUrl = '';
let contextPaths = [];
let contextState = {
  codebase: false,
  docs: [],
  git: null,
  web: '',
  past_chats: false,
  browser: false,
  code: []
};
let currentPage = 'home';
let messageHistory = [];
let historyIndex = -1;
let currentModelName = 'gpt-oss:20b';
let currentChatAbortController = null;
let currentConversationId = null;
let conversationsList = [];
let historyTotal = 0;
let selectedChatIds = new Set();

function setProjectPathDisplay(pathStr) {
  const text = pathStr || 'No folder selected';
  if (projectPathText) projectPathText.textContent = text;
  if (projectPathTextPage) projectPathTextPage.textContent = text;
}

function addContextPath(path) {
  if (!path || contextPaths.includes(path)) return;
  contextPaths.push(path);
  renderContextList();
  updateContextTypeButtons();
}

function removeContextPath(path) {
  contextPaths = contextPaths.filter((p) => p !== path);
  renderContextList();
  updateContextTypeButtons();
}

function hasAnyContext() {
  return contextPaths.length > 0 ||
    contextState.code.length > 0 ||
    contextState.codebase ||
    contextState.docs.length > 0 ||
    contextState.git ||
    (contextState.web && contextState.web.trim()) ||
    contextState.past_chats ||
    contextState.browser;
}

function buildContextPayload() {
  const ctx = {};
  if (contextPaths.length) ctx.files = [...contextPaths];
  if (contextState.code.length) ctx.code = contextState.code;
  if (contextState.codebase) ctx.codebase = true;
  if (contextState.docs.length) ctx.docs = [...contextState.docs];
  if (contextState.git) ctx.git = contextState.git;
  if (contextState.web && contextState.web.trim()) ctx.web = contextState.web.trim();
  if (contextState.past_chats) ctx.past_chats = true;
  if (contextState.browser) ctx.browser = true;
  return Object.keys(ctx).length ? ctx : undefined;
}

function renderContextList() {
  if (!contextListEl || !contextSelectorEl) return;
  if (!hasAnyContext()) {
    contextSelectorEl.hidden = true;
    contextListEl.innerHTML = '';
    return;
  }
  contextSelectorEl.hidden = false;
  contextListEl.innerHTML = '';
  contextPaths.forEach((path) => {
    const chip = document.createElement('div');
    chip.className = 'context-chip';
    chip.dataset.type = 'files';
    const label = document.createElement('span');
    label.className = 'context-chip-label';
    label.textContent = path;
    label.title = path;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.title = 'Remove from context';
    btn.addEventListener('click', () => removeContextPath(path));
    chip.appendChild(label);
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  });
  contextState.code.forEach((seg, i) => {
    const chip = document.createElement('div');
    chip.className = 'context-chip';
    chip.dataset.type = 'code';
    const label = document.createElement('span');
    label.className = 'context-chip-label';
    label.textContent = seg.path + (seg.startLine ? `:${seg.startLine}-${seg.endLine}` : '');
    label.title = seg.path;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.addEventListener('click', () => {
      contextState.code = contextState.code.filter((_, idx) => idx !== i);
      renderContextList();
    });
    chip.appendChild(label);
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  });
  contextState.docs.forEach((url, i) => {
    const chip = document.createElement('div');
    chip.className = 'context-chip';
    chip.dataset.type = 'docs';
    const label = document.createElement('span');
    label.className = 'context-chip-label';
    label.textContent = url;
    label.title = url;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.addEventListener('click', () => {
      contextState.docs.splice(i, 1);
      renderContextList();
    });
    chip.appendChild(label);
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  });
  if (contextState.codebase) {
    const chip = document.createElement('div');
    chip.className = 'context-chip context-chip-tag';
    chip.textContent = '@Codebase';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.addEventListener('click', () => {
      contextState.codebase = false;
      renderContextList();
      updateContextTypeButtons();
    });
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  }
  if (contextState.web) {
    const chip = document.createElement('div');
    chip.className = 'context-chip';
    chip.textContent = '@Web: ' + contextState.web;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.addEventListener('click', () => {
      contextState.web = '';
      renderContextList();
      updateContextPanels();
    });
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  }
  if (contextState.git) {
    const chip = document.createElement('div');
    chip.className = 'context-chip context-chip-tag';
    chip.textContent = '@Git';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.addEventListener('click', () => {
      contextState.git = null;
      renderContextList();
      updateContextTypeButtons();
    });
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  }
  if (contextState.past_chats) {
    const chip = document.createElement('div');
    chip.className = 'context-chip context-chip-tag';
    chip.textContent = '@Past Chats';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.addEventListener('click', () => {
      contextState.past_chats = false;
      renderContextList();
      updateContextTypeButtons();
    });
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  }
  if (contextState.browser) {
    const chip = document.createElement('div');
    chip.className = 'context-chip context-chip-tag';
    chip.textContent = '@Browser';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'context-chip-remove';
    btn.textContent = '×';
    btn.addEventListener('click', () => {
      contextState.browser = false;
      renderContextList();
      updateContextTypeButtons();
    });
    chip.appendChild(btn);
    contextListEl.appendChild(chip);
  }
}

function updateContextTypeButtons() {
  document.querySelectorAll('.context-type-btn').forEach((btn) => {
    const t = btn.dataset.type;
    btn.classList.toggle('active',
      (t === 'files' && contextPaths.length > 0) ||
      (t === 'code' && contextState.code.length > 0) ||
      (t === 'codebase' && contextState.codebase) ||
      (t === 'docs' && contextState.docs.length > 0) ||
      (t === 'git' && contextState.git) ||
      (t === 'web' && !!contextState.web) ||
      (t === 'past_chats' && contextState.past_chats) ||
      (t === 'browser' && contextState.browser));
  });
}

function updateContextPanels() {
  const panels = document.getElementById('context-panels');
  if (!panels) return;
  panels.innerHTML = '';
  const addPanel = (id, html) => {
    const p = document.createElement('div');
    p.className = 'context-panel';
    p.id = 'context-panel-' + id;
    p.innerHTML = html;
    panels.appendChild(p);
  };
  if (contextState.web) {
    addPanel('web', '<span class="context-panel-label">Web search:</span> ' + contextState.web);
  }
  if (contextState.git) {
    addPanel('git', '<span class="context-panel-label">Git:</span> ' + (contextState.git.diff ? 'diff' : 'log') + (contextState.git.ref ? ' ' + contextState.git.ref : ''));
  }
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
  if (!conversationsList.length) {
    historyListEl.innerHTML = '<div class="history-empty">No conversations yet</div>';
    if (historySelectAll) historySelectAll.checked = false;
    if (historyLoadMoreWrap) historyLoadMoreWrap.hidden = true;
    return;
  }
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
      const wrap = document.createElement('label');
      wrap.className = 'history-item-wrap' + (c.id === currentConversationId ? ' active' : '');
      wrap.dataset.id = String(c.id);
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'history-item-cb';
      cb.dataset.id = String(c.id);
      if (selectedChatIds.has(c.id)) cb.checked = true;
      const span = document.createElement('span');
      span.className = 'history-item-text';
      span.textContent = c.title || 'New chat';
      span.title = c.title || 'New chat';
      wrap.appendChild(cb);
      wrap.appendChild(span);
      group.appendChild(wrap);
    });
    historyListEl.appendChild(group);
  });
  if (historySelectAll) {
    historySelectAll.checked = conversationsList.length > 0 && conversationsList.every((c) => selectedChatIds.has(c.id));
  }
  if (historyLoadMoreWrap) {
    historyLoadMoreWrap.hidden = !(historyTotal > conversationsList.length);
  }
}

function getSelectedChatIds() {
  const ids = [];
  historyListEl?.querySelectorAll('.history-item-cb:checked').forEach((el) => {
    const id = Number(el.dataset.id);
    if (id) ids.push(id);
  });
  return ids;
}

function updateSelectedFromCheckboxes() {
  selectedChatIds.clear();
  historyListEl?.querySelectorAll('.history-item-cb:checked').forEach((el) => {
    const id = Number(el.dataset.id);
    if (id) selectedChatIds.add(id);
  });
}

async function fetchHistory(append = false) {
  try {
    const offset = append ? conversationsList.length : 0;
    const r = await fetch(baseUrl + '/history?limit=100&offset=' + offset);
    if (!r.ok) return;
    const data = await r.json();
    const items = data.conversations || [];
    historyTotal = data.total ?? items.length;
    if (append) {
      conversationsList.push(...items);
    } else {
      conversationsList = items;
    }
    renderHistoryList();
  } catch (_) {}
}

function clearMessages() {
  if (messagesEl) messagesEl.innerHTML = '';
  messageHistory = [];
  historyIndex = -1;
  updateChatWelcome();
}

function updateChatWelcome() {
  if (!chatWelcomeEl) return;
  const hasMessages = messagesEl && messagesEl.children.length > 0;
  chatWelcomeEl.hidden = hasMessages;
}

function setActiveConversation(id) {
  currentConversationId = id;
  if (historyListEl) {
    historyListEl.querySelectorAll('.history-item-wrap').forEach((el) => {
      el.classList.toggle('active', Number(el.dataset.id) === id);
    });
  }
  if (navNewChat) navNewChat.classList.toggle('active', id == null);
}

function setHistoryPanelVisible(visible) {
  if (historyPanel) historyPanel.hidden = !visible;
  if (navChatHistory) navChatHistory.classList.toggle('active', visible);
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
  updateChatWelcome();
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
  updateChatWelcome();
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
        conversation_id: currentConversationId || undefined,
        context_paths: contextPaths.length ? contextPaths : undefined,
        context: buildContextPayload()
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
              const wrap = historyListEl.querySelector('.history-item-wrap[data-id="' + data.id + '"]');
              const span = wrap?.querySelector('.history-item-text');
              if (span) span.textContent = data.title;
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
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (form) form.requestSubmit();
    return;
  }
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

function openFolderHandler() {
  if (!window.electronAPI || !window.electronAPI.openFolder) return;
  return window.electronAPI.openFolder().then((chosen) => {
    if (chosen) {
      window.electronAPI.setProjectPath(chosen);
      setProjectPathDisplay(chosen);
    }
  });
}

if (projectPathBtn) projectPathBtn.addEventListener('click', openFolderHandler);
if (projectPathPageBtn) projectPathPageBtn.addEventListener('click', openFolderHandler);

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
  if (currentPage === 'project') loadProjectTree();
});

let projectSelectedPath = null;
let highlightJsLoaded = false;

async function ensureHighlightJs() {
  if (highlightJsLoaded) return;
  try {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '../node_modules/@highlightjs/cdn-assets/styles/github.min.css';
    document.head.appendChild(link);
    const script = document.createElement('script');
    script.src = '../node_modules/@highlightjs/cdn-assets/highlight.js';
    await new Promise((resolve, reject) => {
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
    highlightJsLoaded = true;
  } catch (_) {}
}

function renderProjectTreeItem(node, depth = 0, expanded = true) {
  const wrap = document.createElement('div');
  wrap.className = 'project-tree-item-wrap';
  const item = document.createElement('div');
  item.className = 'project-tree-item' + (projectSelectedPath === node.path ? ' selected' : '');
  item.dataset.path = node.path;
  item.dataset.type = node.type;
  item.style.paddingLeft = (16 + depth * 12) + 'px';
  const icon = document.createElement('span');
  icon.className = 'project-tree-item-icon';
  icon.textContent = node.type === 'folder' ? (expanded ? '▾' : '▸') : ' ';
  const name = document.createElement('span');
  name.className = 'project-tree-item-name';
  name.textContent = node.name;
  item.appendChild(icon);
  item.appendChild(name);
  wrap.appendChild(item);
  const children = document.createElement('div');
  children.className = 'project-tree-children';
  children.dataset.expanded = expanded ? '1' : '0';
  if (node.type === 'folder' && node.children && node.children.length) {
    node.children.forEach((c) => children.appendChild(renderProjectTreeItem(c, depth + 1, expanded)));
    wrap.appendChild(children);
  }
  return wrap;
}

async function loadProjectTree() {
  if (!projectTreeEl) return;
  projectTreeEl.innerHTML = '<div class="project-tree-loading">Loading…</div>';
  try {
    const r = await fetch(baseUrl + '/files/tree');
    if (!r.ok) throw new Error(r.statusText);
    const data = await r.json();
    projectTreeEl.innerHTML = '';
    (data.tree || []).forEach((node) => projectTreeEl.appendChild(renderProjectTreeItem(node)));
  } catch (err) {
    projectTreeEl.innerHTML = '<div class="project-tree-loading">Failed to load files</div>';
  }
}

function renderHighlightedCode(content, language, path) {
  if (!projectEditorContainer) return;
  projectEditorContainer.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'project-editor-header';
  const fileName = document.createElement('div');
  fileName.className = 'project-editor-filename';
  fileName.textContent = path || '';
  fileName.title = path || '';
  header.appendChild(fileName);
  if (path) {
    const addCtxBtn = document.createElement('button');
    addCtxBtn.type = 'button';
    addCtxBtn.className = 'btn-add-context';
    addCtxBtn.textContent = '@Files';
    addCtxBtn.title = 'Add full file to context';
    addCtxBtn.addEventListener('click', () => {
      addContextPath(path);
      setPage('chat');
    });
    const addCodeBtn = document.createElement('button');
    addCodeBtn.type = 'button';
    addCodeBtn.className = 'btn-add-context';
    addCodeBtn.textContent = '@Code';
    addCodeBtn.title = 'Add as code segment (optional line range)';
    addCodeBtn.addEventListener('click', () => {
      const range = prompt('Line range (e.g. 10-20, or leave empty for full file):');
      let startLine = 1, endLine = 99999;
      if (range && /^\d+-\d+$/.test(range.trim())) {
        const [s, e] = range.split('-').map(Number);
        startLine = s;
        endLine = e;
      }
      contextState.code.push({ path, startLine, endLine });
      renderContextList();
      updateContextTypeButtons();
      setPage('chat');
    });
    header.appendChild(addCtxBtn);
    header.appendChild(addCodeBtn);
  }
  projectEditorContainer.appendChild(header);
  const scrollWrap = document.createElement('div');
  scrollWrap.className = 'project-editor-scroll';
  const pre = document.createElement('pre');
  pre.className = 'project-editor-code';
  const code = document.createElement('code');
  code.className = 'language-' + (language || 'plaintext');
  code.textContent = content;
  pre.appendChild(code);
  scrollWrap.appendChild(pre);
  projectEditorContainer.appendChild(scrollWrap);
  if (window.hljs) {
    window.hljs.highlightElement(code);
  }
  projectEditorContainer.hidden = false;
  if (projectEditorPlaceholder) projectEditorPlaceholder.hidden = true;
}

async function loadFileInEditor(path) {
  projectSelectedPath = path;
  projectTreeEl?.querySelectorAll('.project-tree-item').forEach((el) => {
    el.classList.toggle('selected', el.dataset.path === path);
  });
  if (projectEditorPlaceholder) projectEditorPlaceholder.hidden = true;
  if (projectEditorContainer) projectEditorContainer.hidden = false;
  try {
    const r = await fetch(baseUrl + '/files/content?path=' + encodeURIComponent(path));
    if (!r.ok) throw new Error(r.statusText);
    const data = await r.json();
    const content = data.content || '';
    const language = data.language || 'plaintext';
    renderHighlightedCode(content, language, path);
  } catch (err) {
    if (projectEditorPlaceholder) {
      projectEditorPlaceholder.textContent = 'Error: ' + (err.message || String(err));
      projectEditorPlaceholder.hidden = false;
    }
    if (projectEditorContainer) {
      projectEditorContainer.hidden = true;
      projectEditorContainer.innerHTML = '';
    }
  }
}

projectTreeEl?.addEventListener('contextmenu', (e) => {
  const item = e.target.closest('.project-tree-item');
  if (!item || item.dataset.type !== 'file') return;
  e.preventDefault();
  addContextPath(item.dataset.path);
  addActivity('Added to context: ' + item.dataset.path, 'status');
});

document.getElementById('context-types')?.addEventListener('click', (e) => {
  const btn = e.target.closest('.context-type-btn');
  if (!btn) return;
  const t = btn.dataset.type;
  if (t === 'files') {
    setPage('project');
    return;
  }
  if (t === 'code') {
    const path = projectSelectedPath || prompt('File path (relative to workspace):');
    if (path) {
      const range = prompt('Line range (e.g. 10-20, or leave empty for full file):');
      let startLine = 1, endLine = 99999;
      if (range && /^\d+-\d+$/.test(range.trim())) {
        const [s, e] = range.split('-').map(Number);
        startLine = s;
        endLine = e;
      }
      contextState.code.push({ path: path.trim(), startLine, endLine });
      renderContextList();
      updateContextTypeButtons();
    }
    return;
  }
  if (t === 'codebase') {
    contextState.codebase = !contextState.codebase;
    renderContextList();
    updateContextTypeButtons();
    return;
  }
  if (t === 'docs') {
    const url = prompt('Documentation URL:');
    if (url && url.trim()) {
      contextState.docs.push(url.trim());
      renderContextList();
      updateContextTypeButtons();
    }
    return;
  }
  if (t === 'git') {
    const mode = prompt('Git: "log" or "diff" (default: log):') || 'log';
    const ref = prompt('Commit/ref (optional, e.g. HEAD~5):');
    contextState.git = { diff: mode.toLowerCase() === 'diff', ref: ref?.trim() || null, n: 5 };
    renderContextList();
    updateContextTypeButtons();
    updateContextPanels();
    return;
  }
  if (t === 'web') {
    const q = contextState.web || prompt('Web search query:');
    if (q !== null) {
      contextState.web = (q || '').trim();
      renderContextList();
      updateContextTypeButtons();
      updateContextPanels();
    }
    return;
  }
  if (t === 'past_chats') {
    contextState.past_chats = !contextState.past_chats;
    renderContextList();
    updateContextTypeButtons();
    return;
  }
  if (t === 'browser') {
    contextState.browser = !contextState.browser;
    addActivity('@Browser: Placeholder - browser context not yet implemented', 'status');
    renderContextList();
    updateContextTypeButtons();
    return;
  }
});

projectTreeEl?.addEventListener('click', (e) => {
  const item = e.target.closest('.project-tree-item');
  if (!item) return;
  if (item.dataset.type === 'file') {
    loadFileInEditor(item.dataset.path);
    return;
  }
  if (item.dataset.type === 'folder') {
    const wrap = item.closest('.project-tree-item-wrap');
    const children = wrap?.querySelector(':scope > .project-tree-children');
    if (children) {
      const expanded = children.dataset.expanded !== '1';
      children.dataset.expanded = expanded ? '1' : '0';
      children.hidden = !expanded;
      const icon = item.querySelector('.project-tree-item-icon');
      if (icon) icon.textContent = expanded ? '▼' : '▶';
    }
  }
});

async function loadLogs() {
  if (!logsContent) return;
  try {
    const text = window.electronAPI?.readLogs ? await window.electronAPI.readLogs() : 'Logs unavailable';
    logsContent.textContent = text || '(empty)';
  } catch (e) {
    logsContent.textContent = 'Error: ' + (e.message || String(e));
  }
}

function setPage(page) {
  currentPage = page;
  document.querySelectorAll('.side-nav-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.page === page);
  });
  document.querySelectorAll('.page-content').forEach((el) => {
    el.hidden = el.id !== 'page-' + page;
  });
  if (chatSub) chatSub.hidden = page !== 'chat';
  if (page !== 'chat') setHistoryPanelVisible(false);
  if (bottomBar) bottomBar.hidden = page !== 'chat';
  if (page === 'chat') updateChatWelcome();
  if (page === 'logs') loadLogs();
  if (page === 'settings') loadSettings();
  if (page === 'project') {
    ensureHighlightJs();
    loadProjectTree();
  }
}

async function loadSettings() {
  if (!logPathInput) return;
  try {
    const dir = window.electronAPI?.getLogDir ? await window.electronAPI.getLogDir() : null;
    logPathInput.value = dir || '';
    logPathInput.placeholder = dir ? '' : 'Default location';
  } catch (_) {
    logPathInput.value = '';
  }
}

async function saveLogPath(dir) {
  if (!window.electronAPI?.setLogDir) return;
  await window.electronAPI.setLogDir(dir || null);
  if (logPathInput) logPathInput.value = dir || '';
}

document.querySelectorAll('.side-nav-item').forEach((el) => {
  const page = el.dataset.page;
  if (page) el.addEventListener('click', () => setPage(page));
});

if (navNewChat) {
  navNewChat.addEventListener('click', (e) => {
    e.preventDefault();
    setPage('chat');
    currentConversationId = null;
    contextPaths = [];
    contextState = { codebase: false, docs: [], git: null, web: '', past_chats: false, browser: false, code: [] };
    renderContextList();
    updateContextTypeButtons();
    updateContextPanels();
    clearMessages();
    setActiveConversation(null);
    setHistoryPanelVisible(false);
  });
}

document.querySelectorAll('.chat-suggestion').forEach((btn) => {
  btn.addEventListener('click', () => {
    const prompt = btn.dataset.prompt;
    if (prompt && input) {
      input.value = prompt;
      input.focus();
    }
  });
});

if (navChatHistory) {
  navChatHistory.addEventListener('click', (e) => {
    e.preventDefault();
    setPage('chat');
    setHistoryPanelVisible(true);
    fetchHistory();
  });
}

if (btnRefreshLogs) btnRefreshLogs.addEventListener('click', loadLogs);

if (btnLogPathBrowse) {
  btnLogPathBrowse.addEventListener('click', async () => {
    if (!window.electronAPI?.openFolder) return;
    const chosen = await window.electronAPI.openFolder();
    if (chosen) {
      await saveLogPath(chosen);
    }
  });
}

if (btnLogPathApply) {
  btnLogPathApply.addEventListener('click', async () => {
    const val = logPathInput?.value?.trim() || '';
    await saveLogPath(val);
  });
}

if (logPathInput) {
  logPathInput.addEventListener('blur', async () => {
    const val = logPathInput.value?.trim() || '';
    if (window.electronAPI?.setLogDir) await window.electronAPI.setLogDir(val);
  });
}

historyListEl?.addEventListener('click', (e) => {
  if (e.target.classList.contains('history-item-cb')) {
    updateSelectedFromCheckboxes();
    if (historySelectAll) {
      historySelectAll.checked = conversationsList.length > 0 && conversationsList.every((c) => selectedChatIds.has(c.id));
    }
    return;
  }
  const wrap = e.target.closest('.history-item-wrap');
  if (!wrap) return;
  const id = Number(wrap.dataset.id);
  if (!id) return;
  loadConversation(id);
  setPage('chat');
});

if (historySelectAll) {
  historySelectAll.addEventListener('change', () => {
    const checked = historySelectAll.checked;
    historyListEl?.querySelectorAll('.history-item-cb').forEach((el) => {
      el.checked = checked;
      const id = Number(el.dataset.id);
      if (id) {
        if (checked) selectedChatIds.add(id);
        else selectedChatIds.delete(id);
      }
    });
  });
}

if (btnHistorySave) {
  btnHistorySave.addEventListener('click', async () => {
    updateSelectedFromCheckboxes();
    const ids = getSelectedChatIds();
    if (!ids.length) return;
    try {
      const r = await fetch(baseUrl + '/history/export?ids=' + ids.join(','));
      if (!r.ok) throw new Error(r.statusText);
      const data = await r.json();
      const content = JSON.stringify(data, null, 2);
      const name = ids.length === 1 ? 'chat-' + ids[0] + '.json' : 'chats-export.json';
      const saved = window.electronAPI?.saveFile ? await window.electronAPI.saveFile(name, content) : null;
      if (saved) addActivity('Saved to ' + saved, 'status');
    } catch (err) {
      addActivity('Save failed: ' + err.message, 'error');
    }
  });
}

if (btnHistoryDelete) {
  btnHistoryDelete.addEventListener('click', async () => {
    updateSelectedFromCheckboxes();
    const ids = getSelectedChatIds();
    if (!ids.length) return;
    try {
      const r = await fetch(baseUrl + '/history', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids })
      });
      if (!r.ok) throw new Error(r.statusText);
      const data = await r.json();
      ids.forEach((id) => selectedChatIds.delete(id));
      if (ids.includes(currentConversationId)) {
        currentConversationId = null;
        clearMessages();
        setActiveConversation(null);
      }
      await fetchHistory();
    } catch (err) {
      addActivity('Delete failed: ' + err.message, 'error');
    }
  });
}

if (btnHistoryLoadMore) {
  btnHistoryLoadMore.addEventListener('click', () => fetchHistory(true));
}

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
  btnIndex.classList.add('loading');
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
  btnIndex.classList.remove('loading');
});

const BACKEND_CONNECT_TIMEOUT_MS = 45000;
const BACKEND_POLL_INTERVAL_MS = 800;

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
  setPage('home');
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
