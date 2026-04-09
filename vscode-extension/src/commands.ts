import * as vscode from 'vscode';
import { VenCoderAPI } from './api';
import { ChatViewProvider } from './chatView';

export function registerCommands(
    context: vscode.ExtensionContext,
    api: VenCoderAPI,
    chatViewProvider?: ChatViewProvider
): void {
    const commands = [
        vscode.commands.registerCommand('vencoder.chat', async () => {
            const message = await vscode.window.showInputBox({
                prompt: 'Enter your message to VenCoder',
                placeHolder: 'What would you like help with?',
            });

            if (message) {
                const config = vscode.workspace.getConfiguration('vencoder');
                const mode = config.get<string>('mode', 'agent');

                try {
                    const response = await api.sendMessage({ message, mode: mode as 'agent' | 'ask' | 'plan' });
                    vscode.window.showInformationMessage('VenCoder: ' + response.substring(0, 100) + '...');
                } catch (error: any) {
                    vscode.window.showErrorMessage('VenCoder error: ' + error.message);
                }
            }
        }),

        vscode.commands.registerCommand('vencoder.run', async () => {
            const message = await vscode.window.showInputBox({
                prompt: 'Enter command for VenCoder',
                placeHolder: 'e.g., Fix the bug in auth.py',
            });

            if (message) {
                const config = vscode.workspace.getConfiguration('vencoder');
                const mode = config.get<string>('mode', 'agent');

                vscode.window.withProgress({
                    location: vscode.ProgressLocation.Notification,
                    title: 'VenCoder',
                    cancellable: true,
                }, async (progress, token) => {
                    token.onCancellationRequested(() => {
                        api.cancelRequest();
                    });

                    progress.report({ message: 'Processing...' });

                    try {
                        const response = await api.sendMessage({ message, mode: mode as 'agent' | 'ask' | 'plan' });
                        progress.report({ message: 'Complete', increment: 100 });
                        vscode.window.showInformationMessage('VenCoder: Task completed');
                    } catch (error: any) {
                        vscode.window.showErrorMessage('VenCoder error: ' + error.message);
                    }
                });
            }
        }),

        vscode.commands.registerCommand('vencoder.continue', async () => {
            vscode.commands.executeCommand('vencoder.chatView.focus');
        }),

        vscode.commands.registerCommand('vencoder.stop', () => {
            api.cancelRequest();
            vscode.window.showInformationMessage('VenCoder: Operation cancelled');
        }),

        vscode.commands.registerCommand('vencoder.explain', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            const selection = editor.selection;
            const selectedText = editor.document.getText(selection);

            if (!selectedText) {
                vscode.window.showErrorMessage('No text selected');
                return;
            }

            try {
                const response = await api.sendMessage({
                    message: `Explain this code:\n\`\`\`\n${selectedText}\n\`\`\``,
                    mode: 'ask',
                });

                const doc = await vscode.workspace.openTextDocument({
                    content: `# Explanation\n\n${response}`,
                    language: 'markdown',
                });
                await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside });
            } catch (error: any) {
                vscode.window.showErrorMessage('VenCoder error: ' + error.message);
            }
        }),

        vscode.commands.registerCommand('vencoder.refactor', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            const selection = editor.selection;
            const selectedText = editor.document.getText(selection);

            if (!selectedText) {
                vscode.window.showErrorMessage('No text selected');
                return;
            }

            try {
                const response = await api.sendMessage({
                    message: `Refactor this code:\n\`\`\`\n${selectedText}\n\`\`\``,
                    mode: 'agent',
                });

                if (response.includes('```')) {
                    const match = response.match(/```[\w]*\n([\s\S]*?)```/);
                    if (match) {
                        const refactoredCode = match[1];
                        const confirmed = await vscode.window.showInformationMessage(
                            'Apply refactored code?',
                            'Apply',
                            'Preview',
                            'Cancel'
                        );

                        if (confirmed === 'Apply') {
                            editor.edit(editBuilder => {
                                editBuilder.replace(selection, refactoredCode);
                            });
                        } else if (confirmed === 'Preview') {
                            const doc = await vscode.workspace.openTextDocument({
                                content: `# Refactored Code\n\nOriginal:\n\`\`\`\n${selectedText}\n\`\`\`\n\nRefactored:\n\`\`\`\n${refactoredCode}\n\`\`\`\n\n${response}`,
                                language: 'markdown',
                            });
                            await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside });
                        }
                    }
                }
            } catch (error: any) {
                vscode.window.showErrorMessage('VenCoder error: ' + error.message);
            }
        }),

        vscode.commands.registerCommand('vencoder.fix', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            const selection = editor.selection;
            const selectedText = editor.document.getText(selection);

            if (!selectedText) {
                vscode.window.showErrorMessage('No text selected');
                return;
            }

            const problem = await vscode.window.showInputBox({
                prompt: 'Describe the problem (optional)',
                placeHolder: 'e.g., This causes a null pointer exception',
            });

            try {
                const message = problem
                    ? `Fix this code:\n\`\`\`\n${selectedText}\n\`\`\`\n\nProblem: ${problem}`
                    : `Fix this code:\n\`\`\`\n${selectedText}\n\`\`\``;

                const response = await api.sendMessage({
                    message,
                    mode: 'agent',
                });

                if (response.includes('```')) {
                    const match = response.match(/```[\w]*\n([\s\S]*?)```/);
                    if (match) {
                        const fixedCode = match[1];
                        editor.edit(editBuilder => {
                            editBuilder.replace(selection, fixedCode);
                        });
                        vscode.window.showInformationMessage('VenCoder: Code fixed');
                    }
                }
            } catch (error: any) {
                vscode.window.showErrorMessage('VenCoder error: ' + error.message);
            }
        }),

        vscode.commands.registerCommand('vencoder.test', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('No active editor');
                return;
            }

            const selection = editor.selection;
            const selectedText = editor.document.getText(selection);
            const fileName = editor.document.fileName;

            if (!selectedText) {
                vscode.window.showErrorMessage('No text selected');
                return;
            }

            try {
                const response = await api.sendMessage({
                    message: `Generate tests for this code:\n\`\`\`\n${selectedText}\n\`\`\`\n\nFile: ${fileName}`,
                    mode: 'agent',
                });

                const doc = await vscode.workspace.openTextDocument({
                    content: response,
                    language: editor.document.languageId === 'python' ? 'python' : 'typescript',
                });
                await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside });
            } catch (error: any) {
                vscode.window.showErrorMessage('VenCoder error: ' + error.message);
            }
        }),

        vscode.commands.registerCommand('vencoder.collab.create', async () => {
            const roomName = await vscode.window.showInputBox({
                prompt: 'Enter room name',
                placeHolder: 'My Collaboration Room',
            });

            if (roomName) {
                vscode.commands.executeCommand('vencoder.collabView.focus');
            }
        }),

        vscode.commands.registerCommand('vencoder.collab.join', async () => {
            const roomId = await vscode.window.showInputBox({
                prompt: 'Enter room ID',
                placeHolder: 'room-123456',
            });

            if (roomId) {
                vscode.commands.executeCommand('vencoder.collabView.focus');
            }
        }),

        vscode.commands.registerCommand('vencoder.collab.leave', async () => {
            vscode.window.showInformationMessage('Left collaboration room');
        }),

        vscode.commands.registerCommand('vencoder.settings', async () => {
            await vscode.commands.executeCommand('workbench.action.openSettings', '@ext:vencoder');
        }),

        vscode.commands.registerCommand('vencoder.runChecks', async () => {
            const editor = vscode.window.activeTextEditor;
            const filePath = editor?.document.fileName;

            vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'VenCoder: Running checks',
                cancellable: true,
            }, async (progress) => {
                progress.report({ message: 'Running linter...' });
                const lintResult = await api.runLintCheck(filePath);

                progress.report({ message: 'Running type checker...' });
                const typeResult = await api.runTypeCheck(filePath);

                progress.report({ message: 'Running security scan...' });
                const securityResult = await api.runSecurityScan(filePath);

                progress.report({ increment: 100 });

                const issues: string[] = [];
                issues.push(...lintResult.issues);
                issues.push(...typeResult.errors);
                issues.push(...securityResult.vulnerabilities);

                if (issues.length === 0) {
                    vscode.window.showInformationMessage('All checks passed!');
                } else {
                    const doc = await vscode.workspace.openTextDocument({
                        content: `# Code Quality Check Results\n\n## Issues Found\n\n${issues.map((i, idx) => `${idx + 1}. ${i}`).join('\n')}`,
                        language: 'markdown',
                    });
                    await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside });
                }
            });
        }),
    ];

    context.subscriptions.push(...commands);
}
