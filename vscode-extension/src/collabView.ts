import * as vscode from 'vscode';
import { VenCoderAPI } from './api';
import WebSocket from 'ws';

interface CollabUser {
    id: string;
    name: string;
    color: string;
    cursor?: { line: number; column: number };
    isTyping?: boolean;
}

interface CollabMessage {
    type: string;
    data: any;
}

export class CollabViewProvider implements vscode.WebviewViewProvider {
    private webview?: vscode.WebviewView;
    private ws?: WebSocket;
    private roomId?: string;
    private userName: string;
    private users: Map<string, CollabUser> = new Map();

    constructor(
        private readonly extensionUri: vscode.Uri,
        private readonly api: VenCoderAPI
    ) {
        this.userName = 'User';
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

        vscode.window.onDidChangeTextEditorSelection((event) => {
            const selection = event.selections[0];
            if (selection) {
                this.sendCursorPosition(selection);
            }
        });
    }

    private sendToWebview(type: string, data: any): void {
        this.webview?.webview.postMessage({ type, data });
    }

    private async handleMessage(message: any): Promise<void> {
        switch (message.type) {
            case 'createRoom':
                await this.createRoom(message.data.name);
                break;
            case 'joinRoom':
                await this.joinRoom(message.data.roomId, message.data.name);
                break;
            case 'leaveRoom':
                await this.leaveRoom();
                break;
            case 'sendChat':
                await this.sendChat(message.data.message);
                break;
            case 'inviteUser':
                await this.inviteUser(message.data.email);
                break;
        }
    }

    private async createRoom(name: string): Promise<void> {
        this.roomId = 'room-' + Date.now().toString();
        await this.connect(this.roomId, this.userName);
        this.sendToWebview('roomCreated', { roomId: this.roomId, name });
        vscode.window.showInformationMessage(`Collaboration room created: ${this.roomId}`);
    }

    private async joinRoom(roomId: string, name: string): Promise<void> {
        this.roomId = roomId;
        this.userName = name;
        await this.connect(roomId, name);
        this.sendToWebview('roomJoined', { roomId });
    }

    private async leaveRoom(): Promise<void> {
        if (this.ws) {
            this.ws.close();
            this.ws = undefined;
        }
        this.roomId = undefined;
        this.users.clear();
        this.sendToWebview('roomLeft', null);
    }

    private async connect(roomId: string, name: string): Promise<void> {
        const config = vscode.workspace.getConfiguration('vencoder');
        const serverUrl = config.get<string>('collabServer', 'ws://localhost:8766');

        try {
            this.ws = new WebSocket(serverUrl);

            this.ws.on('open', () => {
                this.send({ type: 'join', data: { room_id: roomId, name } });
            });

            this.ws.on('message', (data: WebSocket.Data) => {
                try {
                    const message: CollabMessage = JSON.parse(data.toString());
                    this.handleWsMessage(message);
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', e);
                }
            });

            this.ws.on('close', () => {
                this.sendToWebview('disconnected', null);
            });

            this.ws.on('error', (error) => {
                vscode.window.showErrorMessage('Collaboration connection error: ' + error.message);
            });
        } catch (error: any) {
            vscode.window.showErrorMessage('Failed to connect to collaboration server: ' + error.message);
        }
    }

    private send(message: CollabMessage): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }

    private handleWsMessage(message: CollabMessage): void {
        switch (message.type) {
            case 'user_list':
                this.users.clear();
                for (const user of message.data.users) {
                    this.users.set(user.id, user);
                }
                this.sendToWebview('usersUpdated', Array.from(this.users.values()));
                break;
            case 'chat':
                this.sendToWebview('chatReceived', message.data);
                this.showNotification(`${message.data.user_name}: ${message.data.message}`);
                break;
            case 'cursor':
                if (message.data.user_id) {
                    const user = this.users.get(message.data.user_id);
                    if (user) {
                        user.cursor = message.data.position;
                        this.highlightUserCursor(user);
                    }
                }
                break;
            case 'system':
                this.showNotification(message.data.message);
                break;
            case 'error':
                vscode.window.showErrorMessage(message.data.message);
                break;
        }
    }

    private async sendChat(message: string): Promise<void> {
        this.send({ type: 'chat', data: { message } });
    }

    private sendCursorPosition(position: vscode.Selection): void {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        this.send({
            type: 'cursor',
            data: {
                position: {
                    line: position.active.line + 1,
                    column: position.active.character + 1,
                },
            },
        });
    }

    private highlightUserCursor(user: CollabUser): void {
        if (!user.cursor) return;

        const decoration = vscode.window.createTextEditorDecorationType({
            before: {
                contentText: ' ',
                backgroundColor: user.color,
                border: `2px solid ${user.color}`,
            },
            overviewRulerColor: user.color,
            overviewRulerLane: vscode.OverviewRulerLane.Full,
        });

        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const startPos = new vscode.Position(user.cursor.line - 1, user.cursor.column - 1);
            editor.setDecorations(decoration, [
                new vscode.Range(startPos, startPos),
            ]);
        }
    }

    private async inviteUser(email: string): Promise<void> {
        if (!this.roomId) return;

        await vscode.env.clipboard.writeText(
            `Join my VenCoder collaboration room!\nRoom ID: ${this.roomId}\n\nUse command: VenCoder: Join Room`
        );

        vscode.window.showInformationMessage(`Room link copied! Share with ${email}`);
    }

    private showNotification(message: string): void {
        this.sendToWebview('notification', message);
    }

    private getHtml(): string {
        return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VenCoder Collaboration</title>
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
        }
        .header h1 {
            margin: 0;
            font-size: 14px;
            font-weight: 600;
        }
        .room-info {
            padding: 8px 16px;
            background: rgba(0, 122, 204, 0.1);
            border-bottom: 1px solid var(--vscode-widget-border);
            font-size: 12px;
        }
        .room-info .room-id {
            font-family: monospace;
            background: var(--vscode-textCodeBlock-background);
            padding: 2px 6px;
            border-radius: 4px;
        }
        .users {
            padding: 12px 16px;
            border-bottom: 1px solid var(--vscode-widget-border);
        }
        .users h2 {
            margin: 0 0 8px 0;
            font-size: 11px;
            text-transform: uppercase;
            color: var(--vscode-foreground);
            opacity: 0.7;
        }
        .user-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .user-badge {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
        }
        .user-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .chat {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 12px 16px;
        }
        .chat-message {
            margin-bottom: 12px;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
        }
        .chat-message.own {
            background: rgba(0, 122, 204, 0.1);
        }
        .chat-message.other {
            background: var(--vscode-textCodeBlock-background);
        }
        .chat-message .sender {
            font-weight: 600;
            font-size: 11px;
            margin-bottom: 4px;
        }
        .chat-input {
            padding: 12px 16px;
            border-top: 1px solid var(--vscode-widget-border);
        }
        .chat-input-container {
            display: flex;
            gap: 8px;
        }
        .chat-input-box {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid var(--vscode-widget-border);
            border-radius: 6px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-size: 13px;
        }
        .chat-send-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            background: #007acc;
            color: white;
            cursor: pointer;
        }
        .lobby {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            padding: 24px;
            text-align: center;
        }
        .lobby h2 {
            margin: 0 0 16px 0;
            font-size: 18px;
        }
        .lobby p {
            color: var(--vscode-foreground);
            opacity: 0.7;
            margin: 0 0 24px 0;
        }
        .lobby-btn {
            padding: 12px 24px;
            margin: 8px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .lobby-btn.primary {
            background: #007acc;
            color: white;
        }
        .lobby-btn.secondary {
            background: transparent;
            border: 1px solid var(--vscode-widget-border);
            color: var(--vscode-foreground);
        }
        .hidden {
            display: none !important;
        }
        .invite-section {
            padding: 12px 16px;
            border-top: 1px solid var(--vscode-widget-border);
        }
        .invite-input {
            width: 100%;
            padding: 8px 12px;
            margin-bottom: 8px;
            border: 1px solid var(--vscode-widget-border);
            border-radius: 6px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
        }
        .notification {
            position: fixed;
            bottom: 60px;
            left: 50%;
            transform: translateX(-50%);
            padding: 8px 16px;
            background: var(--vscode-notification-background);
            border: 1px solid var(--vscode-notification-border);
            border-radius: 6px;
            font-size: 12px;
            animation: slideUp 0.3s ease;
        }
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateX(-50%) translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateX(-50%) translateY(0);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Collaboration</h1>
        </div>

        <div class="lobby" id="lobby">
            <h2>Real-time Collaboration</h2>
            <p>Work together with your team in real-time</p>
            <button class="lobby-btn primary" id="createRoomBtn">Create Room</button>
            <button class="lobby-btn secondary" id="joinRoomBtn">Join Room</button>
        </div>

        <div class="room-info hidden" id="roomInfo">
            <strong>Room ID:</strong> <span class="room-id" id="roomIdDisplay"></span>
        </div>

        <div class="users hidden" id="usersSection">
            <h2>Participants</h2>
            <div class="user-list" id="userList"></div>
        </div>

        <div class="chat hidden" id="chatSection">
            <div class="chat-messages" id="chatMessages"></div>
            <div class="chat-input">
                <div class="chat-input-container">
                    <input type="text" class="chat-input-box" id="chatInput" placeholder="Type a message...">
                    <button class="chat-send-btn" id="chatSendBtn">Send</button>
                </div>
            </div>
        </div>

        <div class="invite-section hidden" id="inviteSection">
            <input type="email" class="invite-input" id="inviteEmail" placeholder="Enter email to invite...">
            <button class="lobby-btn secondary" id="inviteBtn" style="width: 100%;">Copy Invite Link</button>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const lobby = document.getElementById('lobby');
        const roomInfo = document.getElementById('roomInfo');
        const usersSection = document.getElementById('usersSection');
        const chatSection = document.getElementById('chatSection');
        const inviteSection = document.getElementById('inviteSection');
        const roomIdDisplay = document.getElementById('roomIdDisplay');
        const userList = document.getElementById('userList');
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const chatSendBtn = document.getElementById('chatSendBtn');
        const inviteEmail = document.getElementById('inviteEmail');
        const inviteBtn = document.getElementById('inviteBtn');

        let currentRoomId = null;

        document.getElementById('createRoomBtn').addEventListener('click', () => {
            vscode.postMessage({ type: 'createRoom', data: { name: 'My Room' } });
        });

        document.getElementById('joinRoomBtn').addEventListener('click', async () => {
            const roomId = await vscode.window.showInputBox({
                prompt: 'Enter room ID to join',
                placeHolder: 'room-123456',
            });
            if (roomId) {
                vscode.postMessage({ type: 'joinRoom', data: { roomId, name: 'User' } });
            }
        });

        chatSendBtn.addEventListener('click', sendChat);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChat();
        });

        inviteBtn.addEventListener('click', () => {
            vscode.postMessage({ type: 'inviteUser', data: { email: inviteEmail.value } });
        });

        function sendChat() {
            const message = chatInput.value.trim();
            if (!message) return;
            vscode.postMessage({ type: 'sendChat', data: { message } });
            chatInput.value = '';
        }

        vscode.window.onDidReceiveMessage((message) => {
            switch (message.type) {
                case 'roomCreated':
                case 'roomJoined':
                    currentRoomId = message.data.roomId;
                    roomIdDisplay.textContent = currentRoomId;
                    lobby.classList.add('hidden');
                    roomInfo.classList.remove('hidden');
                    usersSection.classList.remove('hidden');
                    chatSection.classList.remove('hidden');
                    inviteSection.classList.remove('hidden');
                    break;
                case 'roomLeft':
                    currentRoomId = null;
                    lobby.classList.remove('hidden');
                    roomInfo.classList.add('hidden');
                    usersSection.classList.add('hidden');
                    chatSection.classList.add('hidden');
                    inviteSection.classList.add('hidden');
                    userList.innerHTML = '';
                    chatMessages.innerHTML = '';
                    break;
                case 'usersUpdated':
                    userList.innerHTML = message.data.map(user => \`
                        <div class="user-badge" style="background: \${user.color}20; border: 1px solid \${user.color}">
                            <span class="user-dot" style="background: \${user.color}"></span>
                            <span>\${user.name}</span>
                        </div>
                    \`).join('');
                    break;
                case 'chatReceived':
                    const isOwn = message.data.user_id === 'self';
                    chatMessages.innerHTML += \`
                        <div class="chat-message \${isOwn ? 'own' : 'other'}">
                            <div class="sender" style="color: \${message.data.user_color}">\${message.data.user_name}</div>
                            <div>\${message.data.message}</div>
                        </div>
                    \`;
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                    break;
                case 'notification':
                    showNotification(message.data);
                    break;
            }
        });

        function showNotification(text) {
            const notification = document.createElement('div');
            notification.className = 'notification';
            notification.textContent = text;
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 3000);
        }
    </script>
</body>
</html>
        `;
    }
}
