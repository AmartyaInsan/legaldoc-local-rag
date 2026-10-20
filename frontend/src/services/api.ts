import type { Message, Thread, ServiceHealth, DocumentItem, SourceCitation, MetadataFilter, SubAgentEvent } from '../types/chat';

const API_BASE = '/api';

export async function fetchHealth(): Promise<ServiceHealth> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Failed to fetch health: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchThreads(): Promise<Thread[]> {
  const res = await fetch(`${API_BASE}/chat/threads`);
  if (!res.ok) {
    throw new Error(`Failed to fetch threads: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchThreadMessages(threadId: string): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/chat/threads/${threadId}/messages`);
  if (!res.ok) {
    throw new Error(`Failed to fetch thread messages: ${res.statusText}`);
  }
  return res.json();
}

export async function createThread(title?: string): Promise<Thread> {
  const res = await fetch(`${API_BASE}/chat/threads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: title || 'New Conversation' }),
  });
  if (!res.ok) {
    throw new Error(`Failed to create thread: ${res.statusText}`);
  }
  return res.json();
}

export async function updateThread(
  threadId: string,
  updates: { title?: string; is_pinned?: boolean }
): Promise<Thread> {
  const res = await fetch(`${API_BASE}/chat/threads/${threadId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    throw new Error(`Failed to update thread: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteThread(threadId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/threads/${threadId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete thread: ${res.statusText}`);
  }
}

// Document Management APIs
export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) {
    throw new Error(`Failed to fetch documents: ${res.statusText}`);
  }
  return res.json();
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }
  return res.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${documentId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete document: ${res.statusText}`);
  }
}

export interface ModelsResponse {
  active_model: string;
  subagent_model?: string;
  available_models: string[];
  provider: string;
}

export async function fetchModels(): Promise<ModelsResponse> {
  const res = await fetch(`${API_BASE}/chat/models`);
  if (!res.ok) {
    throw new Error(`Failed to fetch models: ${res.statusText}`);
  }
  return res.json();
}

export interface StreamChatOptions {
  messages: Message[];
  threadId?: string;
  model?: string;
  subagentModel?: string;
  systemPrompt?: string;
  metadataFilter?: MetadataFilter;
  searchMode?: 'hybrid' | 'vector' | 'keyword';
  signal?: AbortSignal;
  onToolEvents?: (events: any[]) => void;
  onSubAgentEvents?: (events: SubAgentEvent[]) => void;
  onSources?: (sources: SourceCitation[]) => void;
  onToken: (token: string) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
}

export async function streamChatCompletion({
  messages,
  threadId,
  model,
  subagentModel,
  systemPrompt,
  metadataFilter,
  searchMode = 'hybrid',
  signal,
  onToolEvents,
  onSubAgentEvents,
  onSources,
  onToken,
  onComplete,
  onError,
}: StreamChatOptions): Promise<void> {
  try {
    const formattedMessages = messages.map(m => ({
      role: m.role,
      content: m.content,
    }));

    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages: formattedMessages,
        thread_id: threadId,
        model,
        subagent_model: subagentModel,
        system_prompt: systemPrompt,
        metadata_filter: metadataFilter,
        search_mode: searchMode,
      }),
      signal,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Chat API error (${response.status}): ${errText}`);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;

        const dataStr = trimmed.slice(6);
        if (dataStr === '[DONE]') {
          onComplete();
          return;
        }

        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.error) {
            onError(new Error(parsed.error));
            return;
          }
          if (parsed.tool_events && onToolEvents) {
            onToolEvents(parsed.tool_events);
          }
          if (parsed.subagent_events && onSubAgentEvents) {
            onSubAgentEvents(parsed.subagent_events);
          }
          if (parsed.sources && onSources) {
            onSources(parsed.sources);
          }
          if (parsed.token) {
            onToken(parsed.token);
          }
        } catch {
          // ignore partial JSON chunk parsing issues
        }
      }
    }

    onComplete();
  } catch (err: any) {
    if (err.name === 'AbortError') {
      onComplete();
      return;
    }
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}
