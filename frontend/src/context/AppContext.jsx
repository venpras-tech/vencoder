import { createContext, useContext, useReducer, useCallback, useEffect, useState, useRef } from 'react';

const AppContext = createContext(null);

const INITIAL_CONTEXT_STATE = {
  codebase: false,
  docs: [],
  git: null,
  web: '',
  past_chats: false,
  browser: false,
  code: [],
  visual: null,
};

const initialState = {
  currentPage: 'home',
  sidebarCollapsed: localStorage.getItem('sidebar-collapsed') === '1',
  theme: localStorage.getItem('app-theme') || 'system',
  modelName: '',
  modelProvider: 'Ollama',
  backendConnected: false,
  backendUrl: 'http://127.0.0.1:8765',
  projectPath: null,
  conversations: [],
  currentConversationId: null,
  messages: [],
  contextPaths: [],
  contextState: { ...INITIAL_CONTEXT_STATE },
  historyPanelOpen: false,
  currentMode: 'agent',
  isProcessing: false,
  activityLog: [],
  logs: {
    backend: [],
    agent: [],
    app: [],
    ui: [],
  },
  logsType: 'backend',
};

function reducer(state, action) {
  switch (action.type) {
    case 'SET_PAGE':
      return { ...state, currentPage: action.payload };
    case 'TOGGLE_SIDEBAR':
      const collapsed = !state.sidebarCollapsed;
      localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0');
      return { ...state, sidebarCollapsed: collapsed };
    case 'SET_THEME':
      localStorage.setItem('app-theme', action.payload);
      return { ...state, theme: action.payload };
    case 'SET_MODEL_INFO':
      return {
        ...state,
        modelName: action.payload.name || '',
        modelProvider: action.payload.provider || 'Ollama',
      };
    case 'SET_BACKEND_CONNECTED':
      return { ...state, backendConnected: action.payload };
    case 'SET_BACKEND_URL':
      return { ...state, backendUrl: action.payload };
    case 'SET_PROJECT_PATH':
      return { ...state, projectPath: action.payload };
    case 'SET_CONVERSATIONS':
      return { ...state, conversations: action.payload };
    case 'SET_CURRENT_CONVERSATION':
      return { ...state, currentConversationId: action.payload };
    case 'SET_MESSAGES':
      return { ...state, messages: action.payload };
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.payload] };
    case 'UPDATE_LAST_MESSAGE': {
      const messages = [...state.messages];
      if (messages.length === 0) return state;
      const last = messages[messages.length - 1];
      const p = action.payload;
      if (typeof p === 'function') {
        messages[messages.length - 1] = p(last);
      } else {
        const next = { ...last };
        for (const [key, val] of Object.entries(p)) {
          if (key === 'content' && typeof val === 'function') {
            next.content = val(last.content ?? '');
          } else {
            next[key] = val;
          }
        }
        messages[messages.length - 1] = next;
      }
      return { ...state, messages };
    }
    case 'ADD_CONTEXT_PATH':
      if (state.contextPaths.includes(action.payload)) return state;
      return { ...state, contextPaths: [...state.contextPaths, action.payload] };
    case 'REMOVE_CONTEXT_PATH':
      return {
        ...state,
        contextPaths: state.contextPaths.filter((p) => p !== action.payload),
      };
    case 'SET_CONTEXT_STATE':
      return { ...state, contextState: { ...state.contextState, ...action.payload } };
    case 'SET_MODE':
      return { ...state, currentMode: action.payload };
    case 'SET_PROCESSING':
      return { ...state, isProcessing: action.payload };
    case 'ADD_ACTIVITY':
      return {
        ...state,
        activityLog: [
          ...state.activityLog.slice(-99),
          { text: action.payload.text, type: action.payload.type, timestamp: new Date() },
        ],
      };
    case 'CLEAR_ACTIVITY':
      return { ...state, activityLog: [] };
    case 'SET_LOGS':
      return {
        ...state,
        logs: { ...state.logs, [action.payload.type]: action.payload.lines },
      };
    case 'SET_LOGS_TYPE':
      return { ...state, logsType: action.payload };
    case 'CLEAR_CONTEXT':
      return {
        ...state,
        contextPaths: [],
        contextState: { ...INITIAL_CONTEXT_STATE },
      };
    case 'TOGGLE_HISTORY_PANEL':
      return { ...state, historyPanelOpen: !state.historyPanelOpen };
    case 'SET_HISTORY_PANEL':
      return { ...state, historyPanelOpen: action.payload };
    default:
      return state;
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [baseUrl, setBaseUrl] = useState(initialState.backendUrl);
  const [composerDraft, setComposerDraft] = useState('');
  const chatAbortRef = useRef(null);

  useEffect(() => {
    const theme = state.theme;
    const isHC = theme === 'high-contrast';
    const isDark = isHC || theme === 'dark' || (
      theme !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches
    );
    document.documentElement.classList.toggle('theme-dark', isDark);
    document.documentElement.classList.toggle('theme-contrast', isHC);
    document.documentElement.dataset.theme = theme;
  }, [state.theme]);

  useEffect(() => {
    async function initBackendUrl() {
      if (window.electronAPI?.getBackendUrl) {
        const url = await window.electronAPI.getBackendUrl();
        setBaseUrl(url);
        dispatch({ type: 'SET_BACKEND_URL', payload: url });
      }
    }
    initBackendUrl();
  }, []);

  useEffect(() => {
    const onProjectPath = (e) => {
      const d = e.detail;
      if (typeof d === 'string') {
        dispatch({ type: 'SET_PROJECT_PATH', payload: d });
      }
    };
    window.addEventListener('project-path', onProjectPath);
    return () => window.removeEventListener('project-path', onProjectPath);
  }, []);

  useEffect(() => {
    if (!window.electronAPI?.getProjectPath) return;
    window.electronAPI.getProjectPath().then((p) => {
      if (typeof p === 'string' && p.length && p !== '.') {
        dispatch({ type: 'SET_PROJECT_PATH', payload: p });
      }
    });
  }, []);

  const setPage = useCallback((page) => {
    dispatch({ type: 'SET_PAGE', payload: page });
  }, []);

  const toggleSidebar = useCallback(() => {
    dispatch({ type: 'TOGGLE_SIDEBAR' });
  }, []);

  const setTheme = useCallback((theme) => {
    dispatch({ type: 'SET_THEME', payload: theme });
  }, []);

  const setModelInfo = useCallback((name, provider) => {
    dispatch({ type: 'SET_MODEL_INFO', payload: { name, provider } });
  }, []);

  const setBackendConnected = useCallback((connected) => {
    dispatch({ type: 'SET_BACKEND_CONNECTED', payload: connected });
  }, []);

  const setProjectPath = useCallback((path) => {
    dispatch({ type: 'SET_PROJECT_PATH', payload: path });
  }, []);

  const setConversations = useCallback((convs) => {
    dispatch({ type: 'SET_CONVERSATIONS', payload: convs });
  }, []);

  const setCurrentConversation = useCallback((id) => {
    dispatch({ type: 'SET_CURRENT_CONVERSATION', payload: id });
  }, []);

  const setMessages = useCallback((msgs) => {
    dispatch({ type: 'SET_MESSAGES', payload: msgs });
  }, []);

  const addMessage = useCallback((msg) => {
    dispatch({ type: 'ADD_MESSAGE', payload: msg });
  }, []);

  const updateLastMessage = useCallback((update) => {
    dispatch({ type: 'UPDATE_LAST_MESSAGE', payload: update });
  }, []);

  const addContextPath = useCallback((path) => {
    dispatch({ type: 'ADD_CONTEXT_PATH', payload: path });
  }, []);

  const removeContextPath = useCallback((path) => {
    dispatch({ type: 'REMOVE_CONTEXT_PATH', payload: path });
  }, []);

  const setContextState = useCallback((update) => {
    dispatch({ type: 'SET_CONTEXT_STATE', payload: update });
  }, []);

  const setMode = useCallback((mode) => {
    dispatch({ type: 'SET_MODE', payload: mode });
  }, []);

  const setProcessing = useCallback((processing) => {
    dispatch({ type: 'SET_PROCESSING', payload: processing });
  }, []);

  const addActivity = useCallback((text, type = 'status') => {
    dispatch({ type: 'ADD_ACTIVITY', payload: { text, type } });
  }, []);

  const clearActivity = useCallback(() => {
    dispatch({ type: 'CLEAR_ACTIVITY' });
  }, []);

  const setLogs = useCallback((type, lines) => {
    dispatch({ type: 'SET_LOGS', payload: { type, lines } });
  }, []);

  const setLogsType = useCallback((type) => {
    dispatch({ type: 'SET_LOGS_TYPE', payload: type });
  }, []);

  const toggleHistoryPanel = useCallback(() => {
    dispatch({ type: 'TOGGLE_HISTORY_PANEL' });
  }, []);

  const setHistoryPanelOpen = useCallback((open) => {
    dispatch({ type: 'SET_HISTORY_PANEL', payload: open });
  }, []);

  const clearContext = useCallback(() => {
    dispatch({ type: 'CLEAR_CONTEXT' });
  }, []);

  const newChatSession = useCallback(() => {
    dispatch({ type: 'SET_MESSAGES', payload: [] });
    dispatch({ type: 'SET_CURRENT_CONVERSATION', payload: null });
    dispatch({ type: 'CLEAR_ACTIVITY' });
    setComposerDraft('');
  }, []);

  const value = {
    ...state,
    baseUrl,
    composerDraft,
    setComposerDraft,
    chatAbortRef,
    setPage,
    toggleSidebar,
    setTheme,
    setModelInfo,
    setBackendConnected,
    setProjectPath,
    setConversations,
    setCurrentConversation,
    setMessages,
    addMessage,
    updateLastMessage,
    addContextPath,
    removeContextPath,
    setContextState,
    setMode,
    setProcessing,
    addActivity,
    clearActivity,
    setLogs,
    setLogsType,
    toggleHistoryPanel,
    setHistoryPanelOpen,
    clearContext,
    newChatSession,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
