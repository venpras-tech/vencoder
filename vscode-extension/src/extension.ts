import * as vscode from 'vscode';
import { ChatViewProvider } from './chatView';
import { CollabViewProvider } from './collabView';
import { VenCoderAPI } from './api';
import { registerCommands } from './commands';
import { StatusBarManager } from './statusBar';

let chatViewProvider: ChatViewProvider | undefined;
let collabViewProvider: CollabViewProvider | undefined;
let statusBarManager: StatusBarManager | undefined;
let vencoderApi: VenCoderAPI | undefined;

export function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('vencoder');
    const serverUrl = config.get<string>('serverUrl', 'http://localhost:8765');
    
    vencoderApi = new VenCoderAPI(serverUrl);
    statusBarManager = new StatusBarManager();
    
    chatViewProvider = new ChatViewProvider(context.extensionUri, vencoderApi);
    collabViewProvider = new CollabViewProvider(context.extensionUri, vencoderApi);
    
    const chatView = vscode.window.registerWebviewViewProvider(
        'vencoder.chatView',
        chatViewProvider
    );
    
    const collabView = vscode.window.registerWebviewViewProvider(
        'vencoder.collabView',
        collabViewProvider
    );
    
    registerCommands(context, vencoderApi, chatViewProvider);
    
    if (config.get<boolean>('showStatusBar', true)) {
        statusBarManager.show();
    }
    
    vencoderApi.on('statusChange', (status: string) => {
        statusBarManager?.updateStatus(status);
    });
    
    vencoderApi.on('error', (error: string) => {
        vscode.window.showErrorMessage(`VenCoder: ${error}`);
    });
    
    vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration('vencoder')) {
            const newConfig = vscode.workspace.getConfiguration('vencoder');
            const newServerUrl = newConfig.get<string>('serverUrl');
            
            if (newServerUrl !== undefined && newServerUrl !== serverUrl) {
                vencoderApi?.updateServerUrl(newServerUrl);
            }
            
            if (newConfig.get<boolean>('showStatusBar') === false) {
                statusBarManager?.hide();
            } else {
                statusBarManager?.show();
            }
        }
    });
    
    context.subscriptions.push(
        chatView,
        collabView,
        statusBarManager
    );
    
    console.log('VenCoder extension activated');
}

export function deactivate() {
    vencoderApi?.dispose();
    statusBarManager?.dispose();
}
