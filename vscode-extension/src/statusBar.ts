import * as vscode from 'vscode';

export class StatusBarManager implements vscode.Disposable {
    private statusBarItem: vscode.StatusBarItem;
    private status: string = 'Ready';

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            100
        );
        this.statusBarItem.text = '$(bot) VenCoder';
        this.statusBarItem.tooltip = 'VenCoder AI Assistant';
        this.statusBarItem.command = 'vencoder.chat';
    }

    show(): void {
        this.statusBarItem.show();
    }

    hide(): void {
        this.statusBarItem.hide();
    }

    updateStatus(status: string): void {
        this.status = status;
        this.statusBarItem.text = `$(bot) VenCoder: ${status}`;
    }

    setWorking(message?: string): void {
        this.statusBarItem.text = message || '$(sync~spin) VenCoder';
        this.statusBarItem.tooltip = 'VenCoder is working...';
    }

    setReady(): void {
        this.statusBarItem.text = '$(bot) VenCoder';
        this.statusBarItem.tooltip = 'VenCoder AI Assistant';
    }

    setError(error: string): void {
        this.statusBarItem.text = '$(error) VenCoder Error';
        this.statusBarItem.tooltip = error;
        this.statusBarItem.color = '#f48771';
    }

    dispose(): void {
        this.statusBarItem.dispose();
    }
}
