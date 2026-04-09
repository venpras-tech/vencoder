import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import { EventEmitter } from 'events';

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
}

export interface ChatOptions {
    message: string;
    mode?: 'agent' | 'ask' | 'plan';
    stream?: boolean;
    sessionId?: number;
}

export interface ModelInfo {
    name: string;
    provider: string;
    size?: number;
}

export interface SessionInfo {
    id: number;
    title: string;
    created_at: string;
    message_count?: number;
}

export interface FileChange {
    path: string;
    old_content?: string;
    new_content: string;
    action: 'create' | 'edit' | 'delete';
}

export interface ToolResult {
    tool: string;
    success: boolean;
    result: string;
    error?: string;
}

export class VenCoderAPI extends EventEmitter {
    private client: AxiosInstance;
    private sessionId: number | null = null;
    private abortController: AbortController | null = null;

    constructor(baseUrl: string = 'http://localhost:8765') {
        super();
        this.client = axios.create({
            baseURL: baseUrl,
            timeout: 300000,
            headers: {
                'Content-Type': 'application/json',
            },
        });
    }

    updateServerUrl(baseUrl: string): void {
        this.client = axios.create({
            baseURL: baseUrl,
            timeout: 300000,
            headers: {
                'Content-Type': 'application/json',
            },
        });
    }

    async health(): Promise<boolean> {
        try {
            const response = await this.client.get('/health');
            return response.status === 200;
        } catch {
            return false;
        }
    }

    async getModels(): Promise<ModelInfo[]> {
        try {
            const response = await this.client.get('/models');
            return response.data.models || [];
        } catch (error) {
            this.emit('error', 'Failed to get models');
            return [];
        }
    }

    async getCurrentModel(): Promise<string | null> {
        try {
            const response = await this.client.get('/model');
            return response.data.model;
        } catch {
            return null;
        }
    }

    async setModel(model: string): Promise<boolean> {
        try {
            await this.client.patch('/model', { model });
            return true;
        } catch (error) {
            this.emit('error', 'Failed to set model');
            return false;
        }
    }

    async sendMessage(
        options: ChatOptions,
        onChunk?: (chunk: string) => void,
        onToolCall?: (tool: string, args: object) => void,
        onToolResult?: (result: ToolResult) => void
    ): Promise<string> {
        this.abortController = new AbortController();
        
        try {
            if (options.stream !== false) {
                return await this._streamMessage(options, onChunk, onToolCall, onToolResult);
            } else {
                return await this._sendMessage(options);
            }
        } catch (error) {
            if (axios.isAxiosError(error) && error.code === 'CANCEL') {
                throw new Error('Request cancelled');
            }
            throw error;
        } finally {
            this.abortController = null;
        }
    }

    private async _streamMessage(
        options: ChatOptions,
        onChunk?: (chunk: string) => void,
        onToolCall?: (tool: string, args: object) => void,
        onToolResult?: (result: ToolResult) => void
    ): Promise<string> {
        const response = await this.client.post(
            '/chat',
            {
                message: options.message,
                mode: options.mode || 'agent',
                session_id: options.sessionId || this.sessionId,
            },
            {
                responseType: 'stream',
                signal: this.abortController?.signal,
            }
        );

        let fullResponse = '';

        return new Promise((resolve, reject) => {
            response.data.on('data', (chunk: Buffer) => {
                const lines = chunk.toString().split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        
                        if (data === '[DONE]') {
                            this.sessionId = (response.headers as any)['x-session-id'] || this.sessionId;
                            resolve(fullResponse);
                            return;
                        }

                        try {
                            const parsed = JSON.parse(data);
                            
                            if (parsed.type === 'chunk') {
                                fullResponse += parsed.content;
                                onChunk?.(parsed.content);
                            } else if (parsed.type === 'tool_call') {
                                onToolCall?.(parsed.tool, parsed.args);
                            } else if (parsed.type === 'tool_result') {
                                onToolResult?.(parsed.result);
                            }
                        } catch {
                            // Ignore parse errors for partial JSON
                        }
                    }
                }
            });

            response.data.on('end', () => {
                this.sessionId = (response.headers as any)['x-session-id'] || this.sessionId;
                resolve(fullResponse);
            });

            response.data.on('error', (error: Error) => {
                reject(error);
            });
        });
    }

    private async _sendMessage(options: ChatOptions): Promise<string> {
        const response = await this.client.post('/chat/run', {
            message: options.message,
            mode: options.mode || 'agent',
            session_id: options.sessionId || this.sessionId,
        });
        
        this.sessionId = response.data.session_id || this.sessionId;
        return response.data.response;
    }

    cancelRequest(): void {
        this.abortController?.abort();
    }

    async getSessions(): Promise<SessionInfo[]> {
        try {
            const response = await this.client.get('/history');
            return response.data.conversations || [];
        } catch {
            return [];
        }
    }

    async getSession(sessionId: number): Promise<ChatMessage[]> {
        try {
            const response = await this.client.get(`/history/${sessionId}`);
            return response.data.messages || [];
        } catch {
            return [];
        }
    }

    async deleteSession(sessionId: number): Promise<boolean> {
        try {
            await this.client.delete('/history', {
                data: { ids: [sessionId] },
            });
            return true;
        } catch {
            return false;
        }
    }

    async createCheckpoint(filePath: string, action: string): Promise<string | null> {
        try {
            const response = await this.client.post('/checkpoint', {
                file_path: filePath,
                action,
            });
            return response.data.checkpoint_id;
        } catch {
            return null;
        }
    }

    async undoCheckpoint(checkpointId?: string): Promise<boolean> {
        try {
            const params = checkpointId ? { checkpoint_id: checkpointId } : {};
            await this.client.post('/checkpoint/undo', null, { params });
            return true;
        } catch {
            return false;
        }
    }

    async getCheckpoints(): Promise<Array<{ id: string; file_path: string; timestamp: string }>> {
        try {
            const response = await this.client.get('/checkpoint');
            return response.data.checkpoints || [];
        } catch {
            return [];
        }
    }

    async getMemory(): Promise<string> {
        try {
            const response = await this.client.get('/memory/content');
            return response.data.content || '';
        } catch {
            return '';
        }
    }

    async updateMemory(content: string): Promise<boolean> {
        try {
            await this.client.post('/memory', { memory: content });
            return true;
        } catch {
            return false;
        }
    }

    async runGitCommand(command: string, ...args: string[]): Promise<string> {
        try {
            const endpoint = `/git/${command}`;
            const response = await this.client.get(endpoint, { params: { args } });
            return response.data.output || '';
        } catch (error) {
            return `Git command failed: ${error}`;
        }
    }

    async readFile(filePath: string): Promise<string | null> {
        try {
            const response = await this.client.get('/files/content', {
                params: { path: filePath },
            });
            return response.data.content;
        } catch {
            return null;
        }
    }

    async writeFile(filePath: string, content: string): Promise<boolean> {
        try {
            await this.client.post('/files/write', {
                path: filePath,
                content,
            });
            return true;
        } catch {
            return false;
        }
    }

    async runLintCheck(filePath?: string): Promise<{ success: boolean; issues: string[] }> {
        try {
            const params = filePath ? { file: filePath } : {};
            const response = await this.client.get('/lint/check', { params });
            return response.data;
        } catch {
            return { success: false, issues: [] };
        }
    }

    async runLintFix(filePath?: string): Promise<{ success: boolean; fixed: number }> {
        try {
            const params = filePath ? { file: filePath } : {};
            const response = await this.client.get('/lint/fix', { params });
            return response.data;
        } catch {
            return { success: false, fixed: 0 };
        }
    }

    async runTypeCheck(filePath?: string): Promise<{ success: boolean; errors: string[] }> {
        try {
            const params = filePath ? { file: filePath } : {};
            const response = await this.client.get('/typecheck', { params });
            return response.data;
        } catch {
            return { success: false, errors: [] };
        }
    }

    async runSecurityScan(filePath?: string): Promise<{ success: boolean; vulnerabilities: string[] }> {
        try {
            const params = filePath ? { file: filePath } : {};
            const response = await this.client.get('/security/scan', { params });
            return response.data;
        } catch {
            return { success: false, vulnerabilities: [] };
        }
    }

    async runCodeReview(filePath?: string): Promise<{ success: boolean; issues: string[] }> {
        try {
            const params = filePath ? { file: filePath } : {};
            const response = await this.client.get('/review/scan', { params });
            return response.data;
        } catch {
            return { success: false, issues: [] };
        }
    }

    dispose(): void {
        this.removeAllListeners();
        this.cancelRequest();
    }
}

export function createVenCoderAPI(baseUrl?: string): VenCoderAPI {
    return new VenCoderAPI(baseUrl);
}
