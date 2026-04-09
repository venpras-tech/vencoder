import { useState, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import './HistoryPanel.css';

function HistoryPanel() {
  const {
    conversations,
    setConversations,
    currentConversationId,
    setCurrentConversation,
    baseUrl,
    historyPanelOpen,
  } = useApp();
  const [selectedIds, setSelectedIds] = useState(new Set());

  const fetchHistory = useCallback(async () => {
    try {
      const r = await fetch(baseUrl + '/history?limit=100');
      if (r.ok) {
        const data = await r.json();
        setConversations(data.conversations || []);
      }
    } catch {
      console.error('Failed to fetch history');
    }
  }, [baseUrl, setConversations]);

  useEffect(() => {
    if (historyPanelOpen) {
      fetchHistory();
    }
  }, [historyPanelOpen, fetchHistory]);

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedIds(new Set(conversations.map((c) => c.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelect = (id) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedIds(newSet);
  };

  const handleConversationClick = (id) => {
    setCurrentConversation(id);
  };

  const handleDelete = async () => {
    const ids = Array.from(selectedIds);
    for (const id of ids) {
      try {
        await fetch(`${baseUrl}/history/${id}`, { method: 'DELETE' });
      } catch {
        console.error('Failed to delete conversation', id);
      }
    }
    setConversations(conversations.filter((c) => !selectedIds.has(c.id)));
    setSelectedIds(new Set());
  };

  const handleExport = async (format) => {
    const ids = Array.from(selectedIds);
    const data = conversations.filter((c) => ids.includes(c.id));
    const content = format === 'json'
      ? JSON.stringify(data, null, 2)
      : data.map((c) => `# ${c.title}\n\n`).join('---\n\n');

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-history.${format === 'json' ? 'json' : 'md'}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatDate = (iso) => {
    const d = new Date(iso);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const dDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());

    if (dDate.getTime() === today.getTime()) return 'Today';
    if (dDate.getTime() === yesterday.getTime()) return 'Yesterday';
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const groupedConversations = conversations.reduce((acc, conv) => {
    const key = formatDate(conv.created_at);
    if (!acc[key]) acc[key] = [];
    acc[key].push(conv);
    return acc;
  }, {});

  const groupOrder = ['Today', 'Yesterday'];
  const sortedKeys = Object.keys(groupedConversations).sort((a, b) => {
    const ai = groupOrder.indexOf(a);
    const bi = groupOrder.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return new Date(groupedConversations[b][0].created_at) - new Date(groupedConversations[a][0].created_at);
  });

  return (
    <div className="history-panel-wrap" hidden={!historyPanelOpen}>
      <aside className="history-panel">
        <div className="history-panel-header">
          <h3 className="history-panel-title">Chat history</h3>
          <div className="history-panel-actions">
            <label className="history-check-wrap">
              <input
                type="checkbox"
                className="history-select-all"
                checked={conversations.length > 0 && selectedIds.size === conversations.length}
                onChange={handleSelectAll}
              />
              <span className="history-check-label">Select</span>
            </label>
            <div className="history-export-wrap">
              <button
                type="button"
                className="btn-history-save"
                onClick={() => handleExport('json')}
                disabled={selectedIds.size === 0}
              >
                Save JSON
              </button>
              <button
                type="button"
                className="btn-history-save btn-history-save-md"
                onClick={() => handleExport('md')}
                disabled={selectedIds.size === 0}
              >
                Save Markdown
              </button>
            </div>
            <button
              type="button"
              className="btn-history-delete"
              onClick={handleDelete}
              disabled={selectedIds.size === 0}
            >
              Delete
            </button>
          </div>
        </div>
        <div className="history-panel-list">
          {sortedKeys.length === 0 ? (
            <div className="history-empty">No conversations yet</div>
          ) : (
            sortedKeys.map((key) => (
              <div key={key} className="history-group">
                <div className="history-group-label">{key}</div>
                {groupedConversations[key].map((conv) => (
                  <label
                    key={conv.id}
                    className={`history-item-wrap ${conv.id === currentConversationId ? 'active' : ''}`}
                  >
                    <input
                      type="checkbox"
                      className="history-item-cb"
                      checked={selectedIds.has(conv.id)}
                      onChange={() => handleSelect(conv.id)}
                    />
                    <span
                      className="history-item-text"
                      onClick={() => handleConversationClick(conv.id)}
                    >
                      {conv.title || 'New chat'}
                    </span>
                  </label>
                ))}
              </div>
            ))
          )}
        </div>
      </aside>
      <div
        className="history-resize-handle"
        title="Drag to resize"
        aria-hidden="true"
      />
    </div>
  );
}

export default HistoryPanel;
