import * as vscode from 'vscode';
import * as path from 'path';
import { VenCoderAPI, ChatMessage } from './api';
import * as Diff from 'diff';

export class ChatViewProvider implements vscode.WebviewViewProvider {
    private webview?: vscode.WebviewView;
    private messages: ChatMessage[] = [];
    private isStreaming = false;
    private currentMode: 'agent' | 'ask' | 'plan' = 'agent';

    constructor(
        private readonly extensionUri: vscode.Uri,
        private readonly api: VenCoderAPI
    ) {
        this.api.on('message', (message: ChatMessage) => {
            this.messages.push(message);
            this.sendToWebview('message', message);
        });

        this.api.on('streamingChunk', (chunk: string) => {
            if (this.messages.length > 0) {
                const lastMessage = this.messages[this.messages.length - 1];
                if (lastMessage.role === 'assistant') {
                    lastMessage.content += chunk;
                    this.sendToWebview('chunk', { id: lastMessage.id, chunk });
                }
            }
        });

        this.api.on('streamingEnd', () => {
            this.isStreaming = false;
            this.sendToWebview('streamingEnd', null);
        });
    }

    resolveWebviewView(webview: vscode.WebviewView): void {
        this.webview = webview;

        webview.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.extensionUri],
        };

        webview.webview.html = this.getHtml();

        webview.webview.onDidReceiveMessage(async (message) => {
            await this.handleMessage(message);
        });
    }

    private sendToWebview(type: string, data: any): void {
        this.webview?.webview.postMessage({ type, data });
    }

    private async handleMessage(message: any): Promise<void> {
        switch (message.type) {
            case 'send':
                await this.handleSendMessage(message.data);
                break;
            case 'clear':
                this.messages = [];
                this.sendToWebview('cleared', null);
                break;
            case 'mode':
                this.currentMode = message.data;
                this.sendToWebview('modeChanged', this.currentMode);
                break;
            case 'cancel':
                this.api.cancelRequest();
                this.isStreaming = false;
                break;
            case 'selectMode':
                await this.handleSelectMode(message.data);
                break;
            case 'openFile':
                await this.handleOpenFile(message.data);
                break;
            case 'runCommand':
                await this.handleRunCommand(message.data);
                break;
        }
    }

    private async handleSendMessage(data: { message: string; mode?: string }): Promise<void> {
        const mode = data.mode || this.currentMode;
        const userMessage: ChatMessage = {
            id: Date.now().toString(),
            role: 'user',
            content: data.message,
            timestamp: new Date().toISOString(),
        };

        this.messages.push(userMessage);
        this.sendToWebview('message', userMessage);

        const assistantMessage: ChatMessage = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
        };

        this.messages.push(assistantMessage);
        this.sendToWebview('message', assistantMessage);

        this.isStreaming = true;

        try {
            const response = await this.api.sendMessage(
                { message: data.message, mode: mode as 'agent' | 'ask' | 'plan' },
                (chunk) => {
                    this.sendToWebview('chunk', { id: assistantMessage.id, chunk });
                },
                (tool, args) => {
                    this.sendToWebview('toolCall', { tool, args });
                },
                (result) => {
                    this.sendToWebview('toolResult', result);
                }
            );

            assistantMessage.content = response;
            this.sendToWebview('messageUpdated', assistantMessage);
        } catch (error: any) {
            assistantMessage.content = `Error: ${error.message}`;
            this.sendToWebview('messageUpdated', assistantMessage);
        } finally {
            this.isStreaming = false;
            this.sendToWebview('streamingEnd', null);
        }
    }

    private async handleSelectMode(mode: string): Promise<void> {
        this.currentMode = mode as 'agent' | 'ask' | 'plan';
        this.sendToWebview('modeChanged', this.currentMode);
    }

    private async handleOpenFile(filePath: string): Promise<void> {
        const document = await vscode.workspace.openTextDocument(filePath);
        await vscode.window.showTextDocument(document);
    }

    private async handleRunCommand(command: string): Promise<void> {
        const terminal = vscode.window.activeTerminal || vscode.window.createTerminal('VenCoder');
        terminal.show();
        terminal.sendText(command);
    }

    private getHtml(): string {
        return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VenCoder Chat</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
        }
        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        .header {
            padding: 12px 16px;
            border-bottom: 1px solid var(--vscode-widget-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header h1 {
            margin: 0;
            font-size: 14px;
            font-weight: 600;
        }
        .mode-selector {
            display: flex;
            gap: 4px;
        }
        .mode-btn {
            padding: 4px 8px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            background: transparent;
            color: var(--vscode-foreground);
        }
        .mode-btn:hover {
            background: var(--vscode-toolbar-hoverBackground);
        }
        .mode-btn.active {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }
        .message {
            margin-bottom: 16px;
            padding: 12px;
            border-radius: 8px;
        }
        .message.user {
            background: rgba(0, 122, 204, 0.1);
            border-left: 3px solid #007acc;
        }
        .message.assistant {
            background: rgba(0, 200, 100, 0.1);
            border-left: 3px solid #00c864;
        }
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 11px;
            color: var(--vscode-foreground);
            opacity: 0.7;
        }
        .message-content {
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .message-content code {
            background: var(--vscode-textCodeBlock-background);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Fira Code', monospace;
            font-size: 12px;
        }
        .message-content pre {
            background: var(--vscode-textCodeBlock-background);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
        }
        .tool-call {
            background: rgba(255, 193, 7, 0.1);
            padding: 8px;
            border-radius: 4px;
            margin: 8px 0;
            font-size: 12px;
            font-family: monospace;
        }
        .input-area {
            padding: 12px 16px;
            border-top: 1px solid var(--vscode-widget-border);
        }
        .input-container {
            display: flex;
            gap: 8px;
        }
        .input-box {
            flex: 1;
            padding: 10px 12px;
            border: 1px solid var(--vscode-widget-border);
            border-radius: 6px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-family: inherit;
            font-size: 13px;
            resize: none;
        }
        .input-box:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }
        .send-btn {
            padding: 10px 16px;
            border: none;
            border-radius: 6px;
            background: #007acc;
            color: white;
            cursor: pointer;
            font-size: 13px;
        }
        .send-btn:hover {
            background: #005a9e;
        }
        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .clear-btn {
            padding: 10px;
            border: none;
            border-radius: 6px;
            background: transparent;
            color: var(--vscode-foreground);
            cursor: pointer;
        }
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--vscode-foreground);
            opacity: 0.5;
        }
        .diff-view {
            font-family: 'Fira Code', monospace;
            font-size: 12px;
            background: var(--vscode-textCodeBlock-background);
            border-radius: 6px;
            overflow: hidden;
        }
        .diff-line {
            padding: 2px 8px;
            display: flex;
        }
        .diff-line.added {
            background: rgba(0, 200, 100, 0.2);
        }
        .diff-line.removed {
            background: rgba(255, 0, 0, 0.2);
        }
        .diff-gutter {
            width: 40px;
            text-align: right;
            padding-right: 8px;
            color: var(--vscode-foreground);
            opacity: 0.5;
            user-select: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>VenCoder</h1>
            <div class="mode-selector">
                <button class="mode-btn" data-mode="agent">Agent</button>
                <button class="mode-btn" data-mode="ask">Ask</button>
                <button class="mode-btn" data-mode="plan">Plan</button>
            </div>
        </div>
        <div class="messages" id="messages">
            <div class="empty-state">
                <p>Start a conversation with VenCoder</p>
                <p style="font-size: 12px;">Type your message below or use Ctrl+Shift+V</p>
            </div>
        </div>
        <div class="input-area">
            <div class="input-container">
                <textarea class="input-box" id="input" placeholder="Ask VenCoder..." rows="1"></textarea>
                <button class="send-btn" id="sendBtn">Send</button>
                <button class="clear-btn" id="clearBtn" title="Clear chat">🗑️</button>
            </div>
        </div>
    </div>
    <script>
        const vscode = acquireVsCodeApi();
        const messagesContainer = document.getElementById('messages');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('sendBtn');
        const clearBtn = document.getElementById('clearBtn');
        const modeBtns = document.querySelectorAll('.mode-btn');

        let currentMode = 'agent';
        let isStreaming = false;

        modeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.mode;
                vscode.postMessage({ type: 'selectMode', data: mode });
            });
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        sendBtn.addEventListener('click', sendMessage);
        clearBtn.addEventListener('click', () => {
            vscode.postMessage({ type: 'clear' });
        });

        vscode.window.onDidReceiveMessage((message) => {
            switch (message.type) {
                case 'message':
                    appendMessage(message.data);
                    break;
                case 'chunk':
                    appendChunk(message.data.id, message.data.chunk);
                    break;
                case 'messageUpdated':
                    updateMessage(message.data);
                    break;
                case 'cleared':
                    messagesContainer.innerHTML = '';
                    break;
                case 'streamingEnd':
                    isStreaming = false;
                    sendBtn.disabled = false;
                    break;
                case 'toolCall':
                    appendToolCall(message.data);
                    break;
                case 'toolResult':
                    appendToolResult(message.data);
                    break;
                case 'modeChanged':
                    currentMode = message.data;
                    modeBtns.forEach(btn => {
                        btn.classList.toggle('active', btn.dataset.mode === currentMode);
                    });
                    break;
            }
        });

        function sendMessage() {
            const text = input.value.trim();
            if (!text || isStreaming) return;

            vscode.postMessage({ type: 'send', data: { message: text, mode: currentMode } });
            input.value = '';
            isStreaming = true;
            sendBtn.disabled = true;
        }

        function appendMessage(message) {
            const emptyState = messagesContainer.querySelector('.empty-state');
            if (emptyState) emptyState.remove();

            const div = document.createElement('div');
            div.className = 'message ' + message.role;
            div.id = 'msg-' + message.id;
            div.innerHTML = \`
                <div class="message-header">
                    <span>\${message.role === 'user' ? 'You' : 'VenCoder'}</span>
                    <span>\${new Date(message.timestamp).toLocaleTimeString()}</span>
                </div>
                <div class="message-content">\${formatContent(message.content)}</div>
            \`;
            messagesContainer.appendChild(div);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function appendChunk(id, chunk) {
            const msgDiv = document.getElementById('msg-' + id);
            if (msgDiv) {
                const contentDiv = msgDiv.querySelector('.message-content');
                contentDiv.innerHTML = formatContent(contentDiv.textContent + chunk);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        }

        function updateMessage(message) {
            const msgDiv = document.getElementById('msg-' + message.id);
            if (msgDiv) {
                const contentDiv = msgDiv.querySelector('.message-content');
                contentDiv.innerHTML = formatContent(message.content);
            }
        }

        function appendToolCall(data) {
            const lastMsg = messagesContainer.lastElementChild;
            if (lastMsg) {
                const toolDiv = document.createElement('div');
                toolDiv.className = 'tool-call';
                toolDiv.textContent = '🔧 ' + data.tool + '(' + JSON.stringify(data.args) + ')';
                lastMsg.querySelector('.message-content').appendChild(toolDiv);
            }
        }

        function appendToolResult(data) {
            const lastMsg = messagesContainer.lastElementChild;
            if (lastMsg) {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'tool-call';
                resultDiv.style.background = data.success ? 'rgba(0, 200, 100, 0.1)' : 'rgba(255, 0, 0, 0.1)';
                resultDiv.textContent = (data.success ? '✓ ' : '✗ ') + data.tool + ': ' + data.result;
                lastMsg.querySelector('.message-content').appendChild(resultDiv);
            }
        }

        function formatContent(content) {
            if (!content) return '';
            return content
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\`([^\`]+)\`/g, '<code>$1</code>')
                .replace(/\\n/g, '<br>');
        }
    </script>
</body>
</html>
        `;
    }
}
