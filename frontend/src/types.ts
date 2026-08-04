export interface ChatMessage {
    role: "user" | "assistant" | "tool";
    content: string;
}

export interface ChatRequest {
    provider: string;
    model: string;
    tools_enabled: boolean;
    messages: ChatMessage[];
}

export interface ChatResponse {
    provider: string;
    model: string;
    role: string;
    content: string;
    tool_calls?: unknown[];
    done: boolean;
}