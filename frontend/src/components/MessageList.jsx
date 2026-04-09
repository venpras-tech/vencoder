import { useEffect, useRef } from 'react';
import './MessageList.css';

function MessageList({ messages }) {
  return (
    <div className="messages">
      {messages.map((message, index) => (
        <Message key={index} message={message} />
      ))}
    </div>
  );
}

function Message({ message }) {
  const { role, content, streaming } = message;
  const contentRef = useRef(null);

  useEffect(() => {
    if (contentRef.current && role === 'assistant') {
      // Apply markdown rendering
      contentRef.current.innerHTML = renderMarkdown(content);
    }
  }, [content, role]);

  const timeStr = () => {
    const d = new Date();
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className={`msg-wrap ${role}`}>
      <div className="msg-header">
        <span className="msg-time">{timeStr()}</span>
      </div>
      <div className={`msg ${role} ${streaming ? 'streaming' : ''}`} ref={contentRef}>
        {role === 'user' ? content : null}
      </div>
    </div>
  );
}

function renderMarkdown(text) {
  if (!text) return '';
  
  const escapeHtml = (s) => {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  };

  const parts = [];
  const codeBlockRe = /```(\w*)\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let m;

  while ((m = codeBlockRe.exec(text)) !== null) {
    const before = text.slice(lastIndex, m.index);
    if (before) {
      const escaped = escapeHtml(before).replace(/\n/g, '<br>');
      parts.push(`<span class="md-text">${escaped}</span>`);
    }
    const lang = (m[1] || 'plaintext').toLowerCase();
    const code = escapeHtml(m[2]);
    parts.push(
      `<div class="code-block"><div class="code-block-header"><span class="code-block-lang">${lang}</span><button type="button" class="code-block-copy" title="Copy">Copy</button></div><pre><code class="language-${lang}">${code}</code></pre></div>`
    );
    lastIndex = m.index + m[0].length;
  }

  if (lastIndex < text.length) {
    const rest = text.slice(lastIndex);
    const escaped = escapeHtml(rest).replace(/\n/g, '<br>');
    parts.push(`<span class="md-text">${escaped}</span>`);
  }

  return parts.join('') || escapeHtml(text).replace(/\n/g, '<br>');
}

export default MessageList;
