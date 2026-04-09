import { useEffect, useRef, useState } from 'react';
import { useApp } from '../context/AppContext';
import MessageList from '../components/MessageList';
import ActivityPanel from '../components/ActivityPanel';
import './ChatPage.css';

const welcomeSuggestions = [
  { label: 'Add a login form', prompt: 'Add a login form to the app' },
  { label: 'Find auth logic', prompt: 'Find where authentication is handled' },
  { label: 'Run tests and fix failures', prompt: 'Run the test suite and fix any failures' },
];

function ChatPage() {
  const { messages, activityLog } = useApp();
  const [activityCollapsed, setActivityCollapsed] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const applySuggestion = (prompt) => {
    window.dispatchEvent(new CustomEvent('vencoder-prefill-composer', { detail: prompt }));
  };

  return (
    <div className="chat-content">
      <ActivityPanel
        logs={activityLog}
        collapsed={activityCollapsed}
        onToggle={() => setActivityCollapsed(!activityCollapsed)}
      />
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <p className="chat-welcome-text">
              Ask your coding agent to explore, edit, or run code in your workspace.
            </p>
            <div className="chat-welcome-suggestions">
              {welcomeSuggestions.map(({ label, prompt }) => (
                <button
                  key={prompt}
                  type="button"
                  className="chat-suggestion"
                  onClick={() => applySuggestion(prompt)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <MessageList messages={messages} />
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

export default ChatPage;
