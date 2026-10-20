import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { DocumentManager } from './components/DocumentManager';
import type { Message, Thread, ServiceHealth, DocumentItem, SourceCitation, MetadataFilter } from './types/chat';
import {
  fetchHealth,
  fetchModels,
  fetchThreads,
  fetchThreadMessages,
  createThread,
  updateThread,
  deleteThread,
  streamChatCompletion,
  fetchDocuments,
  uploadDocument,
  deleteDocument,
} from './services/api';
import { Bot, Layers, Search, BrainCircuit } from 'lucide-react';

export const App: React.FC = () => {
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messagesByThread, setMessagesByThread] = useState<Record<string, Message[]>>({});
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeModel, setActiveModel] = useState('qwen2.5:7b');
  const [subagentModel, setSubagentModel] = useState('qwen2.5:7b');
  const [availableModels, setAvailableModels] = useState<string[]>(['qwen2.5:7b', 'qwen3:latest']);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Module 2, 4 & 6 state: Tabs, Ingestion, Metadata Filtering, and Hybrid Search Mode
  const [activeTab, setActiveTab] = useState<'chat' | 'documents'>('chat');
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [metadataFilter, setMetadataFilter] = useState<MetadataFilter | null>(null);
  const [searchMode, setSearchMode] = useState<'hybrid' | 'vector' | 'keyword'>('hybrid');

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize health, threads, models, and documents
  useEffect(() => {
    const init = async () => {
      try {
        const healthData = await fetchHealth();
        setHealth(healthData);
        if (healthData.config?.llm_model) {
          setActiveModel(healthData.config.llm_model);
        }
      } catch (e) {
        console.warn('Backend offline or initializing...', e);
      }

      try {
        const modelsData = await fetchModels();
        if (modelsData.available_models && modelsData.available_models.length > 0) {
          setAvailableModels(modelsData.available_models);
        }
        if (modelsData.active_model) {
          setActiveModel(modelsData.active_model);
        }
        if (modelsData.subagent_model) {
          setSubagentModel(modelsData.subagent_model);
        }
      } catch (e) {
        console.warn('Could not fetch models...', e);
      }

      try {
        const threadList = await fetchThreads();
        setThreads(threadList);
        if (threadList.length > 0) {
          const firstId = threadList[0].id;
          setActiveThreadId(firstId);
          // Load messages for initial thread
          try {
            const initialMsgs = await fetchThreadMessages(firstId);
            setMessagesByThread(prev => ({ ...prev, [firstId]: initialMsgs }));
          } catch {
            // in-memory fallback
          }
        } else {
          // Create initial thread
          const initialThread = await createThread('Getting Started');
          setThreads([initialThread]);
          setActiveThreadId(initialThread.id);
        }
      } catch (e) {
        console.warn('Could not fetch threads, using local fallback', e);
        const fallbackId = 'local-thread-1';
        setThreads([{
          id: fallbackId,
          title: 'Getting Started',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }]);
        setActiveThreadId(fallbackId);
      }

      // Load documents
      try {
        const docs = await fetchDocuments();
        setDocuments(docs);
      } catch (e) {
        console.warn('Could not load documents initially', e);
      }
    };

    init();
  }, []);

  // Refresh documents list
  const refreshDocuments = async () => {
    setDocsLoading(true);
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (e) {
      console.error('Failed to refresh documents', e);
    } finally {
      setDocsLoading(false);
    }
  };

  const handleUploadDoc = async (file: File) => {
    const newDoc = await uploadDocument(file);
    setDocuments(prev => [newDoc, ...prev.filter(d => d.id !== newDoc.id)]);
  };

  const handleDeleteDoc = async (id: string) => {
    await deleteDocument(id);
    setDocuments(prev => prev.filter(d => d.id !== id));
    // Cascade invalidation: reset filter if it targeted the deleted document
    setMetadataFilter(prev => (prev?.document_id === id ? null : prev));
  };

  // Switch threads and load conversation history
  const handleSelectThread = async (id: string) => {
    setActiveThreadId(id);
    if (!messagesByThread[id]) {
      try {
        const historyMsgs = await fetchThreadMessages(id);
        setMessagesByThread(prev => ({ ...prev, [id]: historyMsgs }));
      } catch {
        setMessagesByThread(prev => ({ ...prev, [id]: [] }));
      }
    }
  };

  // Auto-scroll on new message / token
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const currentMessages = activeThreadId ? messagesByThread[activeThreadId] || [] : [];

  useEffect(() => {
    if (activeTab === 'chat') {
      scrollToBottom();
    }
  }, [currentMessages, activeTab]);

  const handleNewThread = async () => {
    try {
      const thread = await createThread('New Conversation');
      setThreads(prev => [thread, ...prev]);
      setActiveThreadId(thread.id);
      setMessagesByThread(prev => ({ ...prev, [thread.id]: [] }));
      setActiveTab('chat');
    } catch {
      const fallbackId = `thread-${Date.now()}`;
      const newThread: Thread = {
        id: fallbackId,
        title: 'New Conversation',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setThreads(prev => [newThread, ...prev]);
      setActiveThreadId(fallbackId);
      setMessagesByThread(prev => ({ ...prev, [fallbackId]: [] }));
      setActiveTab('chat');
    }
  };

  const handleDeleteThread = async (threadId: string) => {
    try {
      await deleteThread(threadId);
    } catch {
      // Local fallback
    }
    setThreads(prev => prev.filter(t => t.id !== threadId));
    if (activeThreadId === threadId) {
      const remaining = threads.filter(t => t.id !== threadId);
      setActiveThreadId(remaining.length > 0 ? remaining[0].id : null);
    }
  };

  const handleRenameThread = async (threadId: string, newTitle: string) => {
    try {
      const updated = await updateThread(threadId, { title: newTitle });
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, title: updated.title } : t));
    } catch {
      // Local fallback
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, title: newTitle } : t));
    }
  };

  const handleTogglePinThread = async (threadId: string, isPinned: boolean) => {
    try {
      const updated = await updateThread(threadId, { is_pinned: isPinned });
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, is_pinned: updated.is_pinned } : t));
    } catch {
      // Local fallback
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, is_pinned: isPinned } : t));
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isStreaming || !activeThreadId) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      created_at: new Date().toISOString(),
    };

    const assistantMessageId = `asst-${Date.now()}`;
    const initialAssistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      model: activeModel,
      isStreaming: true,
      created_at: new Date().toISOString(),
      sources: [],
    };

    const updatedMessages = [...currentMessages, userMessage];
    setMessagesByThread(prev => ({
      ...prev,
      [activeThreadId]: [...updatedMessages, initialAssistantMessage],
    }));

    setInput('');
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Update thread title if it's the first message
    if (currentMessages.length === 0) {
      const newTitle = userMessage.content.slice(0, 30) + (userMessage.content.length > 30 ? '...' : '');
      setThreads(prev => prev.map(t => t.id === activeThreadId ? { ...t, title: newTitle } : t));
    }

    let accumulatedContent = '';
    let retrievedSources: SourceCitation[] = [];
    let executedToolEvents: any[] = [];
    let executedSubAgentEvents: any[] = [];

    await streamChatCompletion({
      messages: updatedMessages,
      threadId: activeThreadId,
      model: activeModel,
      subagentModel: subagentModel,
      metadataFilter: metadataFilter || undefined,
      searchMode: searchMode,
      signal: controller.signal,
      onToolEvents: (events) => {
        executedToolEvents = events;
        setMessagesByThread(prev => {
          const threadMsgs = prev[activeThreadId] || [];
          return {
            ...prev,
            [activeThreadId]: threadMsgs.map(m =>
              m.id === assistantMessageId
                ? { ...m, tool_events: events }
                : m
            ),
          };
        });
      },
      onSubAgentEvents: (subEvents) => {
        executedSubAgentEvents = subEvents;
        setMessagesByThread(prev => {
          const threadMsgs = prev[activeThreadId] || [];
          return {
            ...prev,
            [activeThreadId]: threadMsgs.map(m =>
              m.id === assistantMessageId
                ? { ...m, subagent_events: subEvents }
                : m
            ),
          };
        });
      },
      onSources: (sources) => {
        retrievedSources = sources;
        setMessagesByThread(prev => {
          const threadMsgs = prev[activeThreadId] || [];
          return {
            ...prev,
            [activeThreadId]: threadMsgs.map(m =>
              m.id === assistantMessageId
                ? { ...m, sources }
                : m
            ),
          };
        });
      },
      onToken: (token) => {
        accumulatedContent += token;
        setMessagesByThread(prev => {
          const threadMsgs = prev[activeThreadId] || [];
          return {
            ...prev,
            [activeThreadId]: threadMsgs.map(m =>
              m.id === assistantMessageId
                ? {
                    ...m,
                    content: accumulatedContent,
                    isStreaming: true,
                    sources: retrievedSources,
                    tool_events: executedToolEvents,
                    subagent_events: executedSubAgentEvents,
                  }
                : m
            ),
          };
        });
      },
      onComplete: () => {
        setIsStreaming(false);
        abortControllerRef.current = null;
        setMessagesByThread(prev => {
          const threadMsgs = prev[activeThreadId] || [];
          return {
            ...prev,
            [activeThreadId]: threadMsgs.map(m =>
              m.id === assistantMessageId
                ? {
                    ...m,
                    isStreaming: false,
                    sources: retrievedSources,
                    tool_events: executedToolEvents,
                    subagent_events: executedSubAgentEvents,
                  }
                : m
            ),
          };
        });
      },
      onError: (err) => {
        setIsStreaming(false);
        abortControllerRef.current = null;
        setMessagesByThread(prev => {
          const threadMsgs = prev[activeThreadId] || [];
          return {
            ...prev,
            [activeThreadId]: threadMsgs.map(m =>
              m.id === assistantMessageId
                ? {
                    ...m,
                    content: accumulatedContent + `\n\n⚠️ **Error:** ${err.message}`,
                    isStreaming: false,
                  }
                : m
            ),
          };
        });
      },
    });
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const activeThread = threads.find(t => t.id === activeThreadId);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090d16] text-zinc-100">
      {/* Sidebar (shown on Chat tab) */}
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onDeleteThread={handleDeleteThread}
        onRenameThread={handleRenameThread}
        onTogglePinThread={handleTogglePinThread}
        health={health}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col h-full min-w-0 bg-[#090d16]">
        <Header
          health={health}
          activeModel={activeModel}
          onModelChange={(m) => setActiveModel(m)}
          subagentModel={subagentModel}
          onSubagentModelChange={(m) => setSubagentModel(m)}
          availableModels={availableModels}
          threadTitle={activeThread?.title}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          documentCount={documents.length}
        />

        {/* View Switcher: Documents Tab vs Chat Tab */}
        {activeTab === 'documents' ? (
          <DocumentManager
            documents={documents}
            onUpload={handleUploadDoc}
            onDelete={handleDeleteDoc}
            onRefresh={refreshDocuments}
            isLoading={docsLoading}
          />
        ) : (
          <div className="flex-1 flex flex-col h-full min-h-0">
            {/* Messages Viewport */}
            <div className="flex-1 overflow-y-auto">
              {currentMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto space-y-6">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30 flex items-center justify-center shadow-xl shadow-emerald-500/10">
                    <Bot className="w-8 h-8 text-emerald-400" />
                  </div>

                  <div>
                    <h2 className="text-2xl font-bold tracking-tight text-white mb-2 font-['Outfit']">
                      LegalDoc & Multi-Domain Local RAG
                    </h2>
                    <p className="text-sm text-zinc-400 leading-relaxed max-w-lg mx-auto">
                      100% Close-Environment Document Q&A, Translation & Analytics powered by local <span className="text-emerald-300 font-mono font-medium">Ollama ({activeModel})</span> and <span className="text-cyan-300 font-mono font-medium">ChromaDB + SQLite</span>. Supports <strong className="text-zinc-200">Legal, Inventory, Client Presentations & KPI Reports</strong> in <strong className="text-emerald-300">Bahasa Indonesia & English</strong>. Upload files in the <button onClick={() => setActiveTab('documents')} className="text-emerald-400 underline font-medium cursor-pointer">Knowledge Base</button> tab.
                    </p>
                  </div>

                  {/* Quick Feature Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left">
                    <div
                      onClick={() => setActiveTab('documents')}
                      className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 hover:border-emerald-500/40 transition cursor-pointer"
                    >
                      <Layers className="w-4 h-4 text-emerald-400 mb-2" />
                      <div className="text-xs font-semibold text-zinc-200">Multi-Domain Ingestion</div>
                      <div className="text-[11px] text-zinc-400 mt-1">Handles Legal statutes, Inventory spreadsheets (.xlsx/.csv), Client Presentations (.pptx), and KPI Reports (.pdf/.docx).</div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 hover:border-cyan-500/40 transition">
                      <Search className="w-4 h-4 text-cyan-400 mb-2" />
                      <div className="text-xs font-semibold text-zinc-200">Bilingual (ID ↔ EN) & Quotes</div>
                      <div className="text-[11px] text-zinc-400 mt-1">Ask in Indonesian or English, modernize archaic document language, and get answers with verbatim original quotes.</div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 hover:border-purple-500/40 transition">
                      <BrainCircuit className="w-4 h-4 text-purple-400 mb-2" />
                      <div className="text-xs font-semibold text-zinc-200">Adaptive Sub-Agents & SQL</div>
                      <div className="text-[11px] text-zinc-400 mt-1">Domain-adaptive full-document audits, multi-document comparison matrices, and local SQLite analytics.</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-4 space-y-1">
                  {currentMessages.map((msg) => (
                    <ChatMessage key={msg.id} message={msg} />
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Chat Input */}
            <ChatInput
              input={input}
              setInput={setInput}
              onSend={handleSend}
              isStreaming={isStreaming}
              onStop={handleStop}
              activeModel={activeModel}
              documents={documents}
              metadataFilter={metadataFilter}
              onFilterChange={setMetadataFilter}
              searchMode={searchMode}
              onSearchModeChange={setSearchMode}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
