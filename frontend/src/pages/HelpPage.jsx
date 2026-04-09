import './HelpPage.css';

function HelpPage() {
  return (
    <div className="help-view">
      <h2 className="help-title">AI Dev Help</h2>

      <section className="help-section">
        <h3 className="help-section-title">Modes</h3>
        <p className="help-desc">Choose how the AI responds. Use the dropdown above the input.</p>
        <dl className="help-dl">
          <dt>Agent (Role)</dt>
          <dd>Default mode. Defines the task, clarifies when ambiguous, then implements. The AI asks 1–3 specific questions if the request is vague before coding. Uses file structure context to avoid hallucinations. Best for well-defined tasks.</dd>
          <dt>Ask (Clarify Needs)</dt>
          <dd>Read-only mode. Explores and answers without changes. Asks focused follow-ups when questions are vague. Use for learning, planning, and understanding code before modifying it.</dd>
          <dt>Plan (Step-by-Step Execution Plan)</dt>
          <dd>Creates a detailed Markdown plan before any code. Researches the codebase, asks clarifying questions, and produces a reviewable plan with file paths and numbered steps. Saves to <code>.ai-dev/plans/</code>. Use for complex, multi-file changes. <kbd>Shift+Tab</kbd> to switch quickly.</dd>
        </dl>
      </section>

      <section className="help-section">
        <h3 className="help-section-title">Slash Commands</h3>
        <p className="help-desc">Type in the chat input and press Enter:</p>
        <dl className="help-dl">
          <dt><kbd>/new</kbd> or <kbd>/n</kbd></dt>
          <dd>Start a new chat</dd>
          <dt><kbd>/models</kbd> or <kbd>/m</kbd></dt>
          <dd>Open Models page</dd>
          <dt><kbd>/index</kbd> or <kbd>/i</kbd></dt>
          <dd>Index workspace (opens Project and runs index)</dd>
          <dt><kbd>/clear</kbd></dt>
          <dd>Clear context chips</dd>
          <dt><kbd>/mode agent|ask|plan</kbd></dt>
          <dd>Switch agent mode</dd>
        </dl>
      </section>

      <section className="help-section">
        <h3 className="help-section-title">Context</h3>
        <p className="help-desc">Use the context buttons below the input to add context. Context appears as chips above the buttons.</p>
        <dl className="help-dl">
          <dt>@Files</dt>
          <dd>Include full file contents. Click to open Project, then right-click a file or use @Files on a selected file to add it. Paths are relative to the workspace root.</dd>
          <dt>@Code</dt>
          <dd>Include a code segment (file + optional line range). Use <code>10-20</code> for lines 10–20, or leave empty for the full file.</dd>
          <dt>@Codebase</dt>
          <dd>Semantic search over the workspace. Index first (Project → Index workspace). The AI gets relevant chunks based on your message.</dd>
          <dt>@Docs</dt>
          <dd>Fetch documentation from URLs. Enter one or more URLs; the AI receives the extracted text.</dd>
          <dt>@Git</dt>
          <dd>Include git log or diff. Choose log or diff mode and optionally a ref (e.g. <code>HEAD~5</code>).</dd>
          <dt>@Web</dt>
          <dd>Web search results for your query. Requires <code>ddgs</code> on the backend.</dd>
          <dt>@Past Chats</dt>
          <dd>Include recent messages from the current conversation as context.</dd>
          <dt>@Image</dt>
          <dd>Add an image for visual analysis. Uses the vision model to process. Describe regions or elements in your message.</dd>
        </dl>
      </section>

      <section className="help-section">
        <h3 className="help-section-title">Project</h3>
        <p className="help-desc">Browse files, add context, and index the workspace.</p>
        <ul className="help-ul">
          <li><strong>Workspace</strong> – Folder used for file operations and indexing. Change via the path button.</li>
          <li><strong>Index workspace</strong> – Build the semantic index for @Codebase. Run after opening a project or when files change.</li>
          <li><strong>File tree</strong> – Click files to view; right-click to add to context. Use @Files and @Code buttons in the editor header.</li>
        </ul>
      </section>

      <section className="help-section">
        <h3 className="help-section-title">Keyboard Shortcuts</h3>
        <dl className="help-dl">
          <dt><kbd>Enter</kbd></dt>
          <dd>Send message</dd>
          <dt><kbd>Shift+Enter</kbd></dt>
          <dd>New line in input</dd>
          <dt><kbd>Ctrl+Enter</kbd></dt>
          <dd>Send message (alternative)</dd>
          <dt><kbd>Ctrl+N</kbd></dt>
          <dd>New chat</dd>
          <dt><kbd>Ctrl+K</kbd></dt>
          <dd>Focus chat input</dd>
          <dt><kbd>Ctrl+Shift+H</kbd></dt>
          <dd>Toggle chat history panel</dd>
          <dt><kbd>Ctrl+1</kbd>–<kbd>5</kbd></dt>
          <dd>Switch pages (Home, Chat, Project, Models, Settings)</dd>
          <dt><kbd>Shift+Tab</kbd></dt>
          <dd>Switch to Plan mode</dd>
          <dt><kbd>Escape</kbd></dt>
          <dd>Cancel generation if in progress; otherwise close the chat history side panel</dd>
          <dt><kbd>Ctrl+↑</kbd> / <kbd>Ctrl+↓</kbd></dt>
          <dd>Navigate input history (previous/next user message)</dd>
        </dl>
      </section>

      <section className="help-section">
        <h3 className="help-section-title">Model & Backend</h3>
        <p className="help-desc">Click the model name in the status bar to change the Ollama model. Use a capable coding model (e.g. <code>codellama</code>, <code>qwen2.5-coder</code>, <code>deepseek-coder</code>) for best results. The green dot indicates Ollama is connected.</p>
      </section>
    </div>
  );
}

export default HelpPage;
