import { useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import ContextSelector from './ContextSelector';
import './BottomBar.css';

function ChatComposer({ variant = 'bottom' }) {
  const {
    composerDraft,
    setComposerDraft,
    currentMode,
    setMode,
    isProcessing,
    setProcessing,
    addMessage,
    updateLastMessage,
    baseUrl,
    setModelInfo,
    addActivity,
    clearActivity,
    contextPaths,
    contextState,
    chatAbortRef,
    messages,
    clearContext,
    newChatSession,
  } = useApp();

  const navigate = useNavigate();
  const location = useLocation();
  const textareaRef = useRef(null);
  const inputHistIdxRef = useRef(null);

  const userInputHistory = useMemo(
    () => messages.filter((m) => m.role === 'user' && (m.content || '').trim()).map((m) => m.content),
    [messages],
  );

  const placeholders = useMemo(
    () => ({
      agent: 'Ask or request file changes… Enter to send · Shift+Enter new line',
      ask: 'Ask a question or explore the codebase… Enter to send · Shift+Enter new line',
      plan: 'Describe the change for a plan (Shift+Tab)… Enter to send · Shift+Enter new line',
    }),
    [],
  );

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 140) + 'px';
    }
  }, [composerDraft]);

  useEffect(() => {
    const onPrefill = (e) => {
      const text = e.detail;
      if (typeof text === 'string' && text) {
        setComposerDraft(text);
        requestAnimationFrame(() => {
          textareaRef.current?.focus();
          textareaRef.current?.setSelectionRange(text.length, text.length);
        });
      }
    };
    window.addEventListener('vencoder-prefill-composer', onPrefill);
    return () => window.removeEventListener('vencoder-prefill-composer', onPrefill);
  }, [setComposerDraft]);

  useEffect(() => {
    if (location.pathname !== '/chat') return;
    const p = sessionStorage.getItem('homePrompt');
    if (!p) return;
    sessionStorage.removeItem('homePrompt');
    setComposerDraft(p);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(p.length, p.length);
    });
  }, [location.pathname, setComposerDraft]);

  useEffect(() => {
    const onFocusComposer = () => {
      requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (el) {
          el.focus();
          const len = el.value.length;
          el.setSelectionRange(len, len);
        }
      });
    };
    window.addEventListener('vencoder-focus-composer', onFocusComposer);
    return () => window.removeEventListener('vencoder-focus-composer', onFocusComposer);
  }, []);

  const buildContextPayload = useCallback(() => {
    const ctx = {};
    if (contextPaths.length) ctx.files = [...contextPaths];
    if (contextState.code.length) ctx.code = contextState.code;
    if (contextState.codebase) ctx.codebase = true;
    if (contextState.docs.length) ctx.docs = [...contextState.docs];
    if (contextState.git) ctx.git = contextState.git;
    if (contextState.web && contextState.web.trim()) ctx.web = contextState.web.trim();
    if (contextState.past_chats) ctx.past_chats = true;
    if (contextState.browser) ctx.browser = true;
    if (contextState.visual?.image) ctx.visual = contextState.visual;
    return Object.keys(ctx).length ? ctx : undefined;
  }, [contextPaths, contextState]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const text = composerDraft.trim();
    if (!text) return;

    if (text.startsWith('/')) {
      handleSlashCommand(text);
      setComposerDraft('');
      return;
    }

    const fromHome = location.pathname === '/';
    if (fromHome) {
      navigate('/chat');
    }

    setComposerDraft('');
    inputHistIdxRef.current = null;
    addMessage({ role: 'user', content: text });
    setProcessing(true);
    clearActivity();

    const ac = new AbortController();
    chatAbortRef.current = ac;

    try {
      addMessage({ role: 'assistant', content: '', streaming: true });

      const r = await fetch(baseUrl + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          context_paths: contextPaths.length ? contextPaths : undefined,
          context: buildContextPayload(),
          mode: currentMode,
        }),
        signal: ac.signal,
      });

      if (!r.ok) {
        throw new Error(r.statusText);
      }

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

              if (data.type === 'model' && data.model) {
                setModelInfo(data.model, data.provider || 'Ollama');
              }

              if (data.type === 'token' && data.content) {
                if (!streamingPhase) {
                  streamingPhase = true;
                }
                updateLastMessage({ content: (c) => (c || '') + data.content });
              }

              if (data.type === 'status' && data.content) {
                addActivity(data.content, 'status');
              }

              if (data.type === 'error') {
                addActivity(data.content, 'error');
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        addActivity('Request cancelled', 'status');
        updateLastMessage({ content: (c) => (c || '') + '\n[Cancelled]' });
      } else {
        addActivity(err.message, 'error');
        updateLastMessage({ content: (c) => (c || '') + '\n[Error: ' + err.message + ']' });
      }
    } finally {
      setProcessing(false);
      if (chatAbortRef.current === ac) {
        chatAbortRef.current = null;
      }
      updateLastMessage({ streaming: false });
    }
  };

  const handleCancel = () => {
    chatAbortRef.current?.abort();
  };

  const handleSlashCommand = (cmd) => {
    const c = cmd.toLowerCase();
    if (c === '/new' || c === '/n') {
      newChatSession();
      navigate('/chat');
      return;
    }
    if (c === '/models' || c === '/m') {
      navigate('/models');
      return;
    }
    if (c === '/index' || c === '/i') {
      navigate('/project');
      return;
    }
    if (c === '/clear') {
      clearContext();
      return;
    }
    const modeMatch = cmd.match(/^\/mode\s+(agent|ask|plan)$/i);
    if (modeMatch) {
      setMode(modeMatch[1].toLowerCase());
    }
  };

  const openContextSelector = () => {
    window.dispatchEvent(new CustomEvent('vencoder-open-context-selector'));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Tab' && e.shiftKey) {
      e.preventDefault();
      setMode('plan');
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      inputHistIdxRef.current = null;
      handleSubmit(e);
      return;
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      e.preventDefault();
      const uh = userInputHistory;
      if (uh.length === 0) return;
      let idx = inputHistIdxRef.current;
      if (e.key === 'ArrowUp') {
        if (idx === null) idx = uh.length;
        idx = Math.max(0, idx - 1);
      } else {
        if (idx === null) idx = -1;
        idx = Math.min(uh.length, idx + 1);
      }
      inputHistIdxRef.current = idx;
      if (idx >= 0 && idx < uh.length) {
        setComposerDraft(uh[idx]);
      } else {
        setComposerDraft('');
        inputHistIdxRef.current = uh.length;
      }
      return;
    }
    if (e.key === '@' || (e.key === '2' && e.shiftKey)) {
      openContextSelector();
    }
  };

  const showStatusRow = variant === 'bottom' || isProcessing;

  const body = (
    <>
      {showStatusRow ? (
        <div className="status-bar status-bar-top" role="status" aria-live="polite" aria-atomic="true">
          {isProcessing ? <span className="backend-status">Processing…</span> : <span className="backend-status" aria-hidden="true" />}
        </div>
      ) : null}
      <div className="input-row-wrap">
        <form className="input-wrap" onSubmit={handleSubmit} aria-busy={isProcessing}>
          <div className={`chat-input-box ${isProcessing ? 'processing' : ''}`}>
            <div className="chat-input-main">
              <textarea
                ref={textareaRef}
                value={composerDraft}
                onChange={(e) => {
                  inputHistIdxRef.current = null;
                  setComposerDraft(e.target.value);
                }}
                onKeyDown={handleKeyDown}
                rows={1}
                placeholder={placeholders[currentMode] || placeholders.agent}
                aria-label="Chat message"
                disabled={isProcessing}
              />
            </div>
            <ContextSelector />
            <div className="chat-input-footer">
              <div className="chat-input-icons">
                <select
                  className="mode-select mode-select-inline"
                  value={currentMode}
                  onChange={(e) => setMode(e.target.value)}
                  title="Agent: implement changes. Ask: explore only. Plan: create Markdown plan"
                >
                  <option value="agent">Agent</option>
                  <option value="ask">Ask</option>
                  <option value="plan">Plan</option>
                </select>
                <button
                  type="button"
                  className="chat-icon-btn chat-icon-model"
                  title="Models – choose AI model"
                  onClick={() => navigate('/models')}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
                    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
                  </svg>
                </button>
                <button
                  type="button"
                  className="chat-icon-btn chat-icon-at"
                  onClick={openContextSelector}
                  title="Context – Add more context"
                >
                  @
                </button>
              </div>
              <div className="chat-input-actions">
                {isProcessing ? (
                  <button
                    type="button"
                    className="chat-icon-btn btn-cancel"
                    onClick={handleCancel}
                    title="Cancel request"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="6" y="6" width="12" height="12" />
                    </svg>
                  </button>
                ) : (
                  <button type="submit" className="chat-icon-btn btn-send" title="Send">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M22 2L11 13" />
                      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          </div>
        </form>
      </div>
    </>
  );

  if (variant === 'home') {
    return <div className="chat-composer chat-composer--home">{body}</div>;
  }

  return body;
}

export default ChatComposer;
