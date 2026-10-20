export interface SourceCitation {
  id?: string;
  document_id?: string;
  filename: string;
  title?: string;
  url?: string;
  document_type?: string;
  source_type?: 'document' | 'web' | 'sql_query' | string;
  keywords?: string[];
  similarity: number;
  search_mode?: 'hybrid' | 'vector' | 'keyword' | 'web' | 'sql' | string;
  rrf_score?: number;
  rerank_score?: number;
  rerank_rank?: number;
  rerank_reason?: string;
  snippet: string;
  citation_index?: number;
  page_label?: string;
  content?: string;
  chunk_index?: number;
}

export interface ExtractedMetadata {
  title?: string;
  summary?: string;
  document_type?: string;
  keywords?: string[];
  target_audience?: string;
  language?: string;
}

export interface SubAgentStep {
  step: string;
  name: string;
  status: 'executing' | 'done' | 'failed' | string;
  detail: string;
  timestamp?: string;
}

export interface SubAgentEvent {
  agent_id: string;
  name: string;
  role: string;
  status: 'executing' | 'completed' | 'failed' | string;
  scenario_type?: string;
  target_document?: string;
  delegation_reason?: string;
  elapsed_seconds?: number;
  model_used?: string;
  steps: SubAgentStep[];
  summary?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at?: string;
  isStreaming?: boolean;
  model?: string;
  sources?: SourceCitation[];
  tools_used?: string[];
  tool_events?: any[];
  subagent_events?: SubAgentEvent[];
}

export interface Thread {
  id: string;
  title: string;
  is_pinned?: boolean;
  created_at: string;
  updated_at: string;
  user_id?: string;
}

export interface DocumentItem {
  id: string;
  filename: string;
  file_size: number;
  content_hash?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | string;
  chunk_count: number;
  doc_action?: 'created' | 'updated' | 'skipped' | string;
  metadata?: ExtractedMetadata;
  message?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface MetadataFilter {
  document_id?: string;
  document_ids?: string[];
  document_type?: string;
  keyword?: string;
}

export interface ServiceHealth {
  status: string;
  environment: string;
  project: string;
  services: {
    llm: {
      status: string;
      provider: string;
      active_model: string;
      available_models: string[];
      error?: string;
    };
    local_db?: {
      status: string;
      engine: string;
      sqlite_path?: string;
      chroma_path?: string;
      documents_count?: number;
      vectors_count?: number;
      message?: string;
    };
  };
  config: {
    llm_provider: string;
    llm_model: string;
    embedding_model: string;
    langsmith_tracing: boolean;
  };
}
