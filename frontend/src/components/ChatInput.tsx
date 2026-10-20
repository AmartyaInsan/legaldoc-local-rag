import React, { useRef, useEffect, useState, useMemo } from 'react';
import { Send, Square, Sparkles, Filter, X, Check, FileText, Tag, ChevronDown, Zap, Search, Target } from 'lucide-react';
import type { DocumentItem, MetadataFilter } from '../types/chat';

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  onSend: () => void;
  isStreaming: boolean;
  onStop: () => void;
  activeModel: string;
  documents?: DocumentItem[];
  metadataFilter?: MetadataFilter | null;
  onFilterChange?: (filter: MetadataFilter | null) => void;
  searchMode?: 'hybrid' | 'vector' | 'keyword';
  onSearchModeChange?: (mode: 'hybrid' | 'vector' | 'keyword') => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  input,
  setInput,
  onSend,
  isStreaming,
  onStop,
  activeModel,
  documents = [],
  metadataFilter = null,
  onFilterChange,
  searchMode = 'hybrid',
  onSearchModeChange,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [filterMenuOpen, setFilterMenuOpen] = useState(false);
  const [searchModeMenuOpen, setSearchModeMenuOpen] = useState(false);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && input.trim()) {
        onSend();
      }
    }
  };

  const samplePrompts = [
    "Terjemahkan ketentuan utama dokumen ini ke bahasa yang lebih baru dan mudah dipahami.",
    "What is the trademark registration flow in Indonesia based on the documents?",
    "Bandingkan seluruh dokumen yang ada di knowledge base secara terstruktur.",
    "Berapa banyak dokumen dan chunk di database? (SQL)",
  ];

  // Active document IDs in metadataFilter
  const activeDocIds = useMemo<string[]>(() => {
    if (!metadataFilter) {
      return documents.map((d) => d.id);
    }
    if (metadataFilter.document_ids) {
      return metadataFilter.document_ids;
    }
    if (metadataFilter.document_id) {
      return [metadataFilter.document_id];
    }
    return documents.map((d) => d.id);
  }, [metadataFilter, documents]);

  // Active filter label
  const activeFilterLabel = useMemo(() => {
    if (!metadataFilter) return null;
    if (metadataFilter.document_type) {
      return `Tipe: ${metadataFilter.document_type}`;
    }
    if (metadataFilter.keyword) {
      return `Keyword: ${metadataFilter.keyword}`;
    }
    if (metadataFilter.document_ids) {
      const count = metadataFilter.document_ids.length;
      if (count === documents.length) {
        return `Semua Dokumen (${documents.length})`;
      }
      if (count === 0) {
        return '0 Dokumen Aktif (Tidak Ada)';
      }
      if (count === 1) {
        const doc = documents.find((d) => d.id === metadataFilter.document_ids![0]);
        return doc?.metadata?.title || doc?.filename || '1 Dokumen Aktif';
      }
      return `${count}/${documents.length} Dokumen Aktif`;
    }
    if (metadataFilter.document_id) {
      const doc = documents.find((d) => d.id === metadataFilter.document_id);
      return doc?.metadata?.title || doc?.filename || '1 Dokumen Aktif';
    }
    return null;
  }, [metadataFilter, documents]);

  const handleToggleDoc = (docId: string) => {
    let currentIds: string[];
    if (metadataFilter?.document_ids) {
      currentIds = [...metadataFilter.document_ids];
    } else if (metadataFilter?.document_id) {
      currentIds = [metadataFilter.document_id];
    } else {
      currentIds = documents.map((d) => d.id);
    }

    let nextIds: string[];
    if (currentIds.includes(docId)) {
      nextIds = currentIds.filter((id) => id !== docId);
    } else {
      nextIds = [...currentIds, docId];
    }

    if (nextIds.length === documents.length) {
      onFilterChange?.(null);
    } else {
      onFilterChange?.({ document_ids: nextIds });
    }
  };

  const handleSelectAllDocs = () => {
    onFilterChange?.(null);
  };

  const handleClearDocs = () => {
    onFilterChange?.({ document_ids: [] });
  };

  const handleSoloDoc = (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onFilterChange?.({ document_ids: [docId] });
  };

  // Unique document types from uploaded documents
  const uniqueDocTypes = useMemo(() => {
    const types = new Set<string>();
    for (const doc of documents) {
      if (doc.metadata?.document_type && doc.metadata.document_type !== 'general') {
        types.add(doc.metadata.document_type);
      }
    }
    return Array.from(types);
  }, [documents]);

  return (
    <div className="p-4 bg-gradient-to-t from-[#0b0f19] via-[#0b0f19] to-transparent">
      <div className="max-w-4xl mx-auto">
        {/* Sample prompt pills if empty */}
        {input.length === 0 && (
          <div className="hidden sm:flex items-center space-x-2 mb-3 overflow-x-auto pb-1">
            <span className="text-[11px] text-slate-500 font-medium shrink-0 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-cyan-400" /> Suggestions:
            </span>
            {samplePrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => setInput(prompt)}
                className="text-[11px] text-slate-400 bg-slate-800/60 hover:bg-slate-800 hover:text-cyan-300 border border-slate-700/60 rounded-full px-3 py-1 transition truncate max-w-xs cursor-pointer"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Input Card */}
        <div className="relative rounded-2xl bg-slate-900/90 border border-slate-700/80 focus-within:border-cyan-500/70 focus-within:ring-2 focus-within:ring-cyan-500/20 shadow-xl backdrop-blur-xl transition duration-200">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Tanyakan dalam Bahasa Indonesia atau English tentang Hukum, Inventaris, Presentasi Klien, atau KPI (${activeModel})...`}
            rows={1}
            disabled={isStreaming}
            className="w-full bg-transparent px-4 pt-3.5 pb-12 text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none min-h-[52px]"
          />

          {/* Action Row */}
          <div className="absolute left-3 right-3 bottom-2.5 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {/* Search Mode Selector (Module 6) */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setSearchModeMenuOpen((prev) => !prev)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition cursor-pointer ${
                    searchMode === 'hybrid'
                      ? 'bg-cyan-950/80 text-cyan-300 border-cyan-500/50 shadow-sm shadow-cyan-500/10'
                      : searchMode === 'vector'
                      ? 'bg-indigo-950/80 text-indigo-300 border-indigo-500/50'
                      : 'bg-amber-950/80 text-amber-300 border-amber-500/50'
                  }`}
                  title="Search Mode (Hybrid Vector + BM25, Vector Only, or Keyword Only)"
                >
                  {searchMode === 'hybrid' && <Zap className="w-3 h-3 text-cyan-400" />}
                  {searchMode === 'vector' && <Target className="w-3 h-3 text-indigo-400" />}
                  {searchMode === 'keyword' && <Search className="w-3 h-3 text-amber-400" />}
                  <span className="capitalize">{searchMode} Search</span>
                  <ChevronDown className="w-3 h-3 opacity-60" />
                </button>

                {searchModeMenuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-30"
                      onClick={() => setSearchModeMenuOpen(false)}
                    />
                    <div className="absolute left-0 bottom-full mb-2 w-64 rounded-xl bg-slate-900 border border-slate-700/90 shadow-2xl p-1.5 z-40 text-xs backdrop-blur-xl space-y-1">
                      <div className="px-2 py-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                        Retrieval Strategy
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          onSearchModeChange?.('hybrid');
                          setSearchModeMenuOpen(false);
                        }}
                        className={`w-full flex items-start gap-2 px-2.5 py-2 rounded-lg text-left transition cursor-pointer ${
                          searchMode === 'hybrid'
                            ? 'bg-cyan-500/20 text-cyan-300 font-medium'
                            : 'text-slate-300 hover:bg-slate-800/80'
                        }`}
                      >
                        <Zap className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="font-semibold flex items-center gap-1.5">
                            Hybrid (RRF + Rerank)
                            {searchMode === 'hybrid' && <Check className="w-3 h-3 text-cyan-400" />}
                          </div>
                          <p className="text-[10px] text-slate-400">Combines Dense Vector and BM25 Sparse search with cross-scoring reranking.</p>
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          onSearchModeChange?.('vector');
                          setSearchModeMenuOpen(false);
                        }}
                        className={`w-full flex items-start gap-2 px-2.5 py-2 rounded-lg text-left transition cursor-pointer ${
                          searchMode === 'vector'
                            ? 'bg-indigo-500/20 text-indigo-300 font-medium'
                            : 'text-slate-300 hover:bg-slate-800/80'
                        }`}
                      >
                        <Target className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="font-semibold flex items-center gap-1.5">
                            Dense Vector Only
                            {searchMode === 'vector' && <Check className="w-3 h-3 text-indigo-400" />}
                          </div>
                          <p className="text-[10px] text-slate-400">Cosine similarity using 768-dim embeddings from nomic-embed-text.</p>
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          onSearchModeChange?.('keyword');
                          setSearchModeMenuOpen(false);
                        }}
                        className={`w-full flex items-start gap-2 px-2.5 py-2 rounded-lg text-left transition cursor-pointer ${
                          searchMode === 'keyword'
                            ? 'bg-amber-500/20 text-amber-300 font-medium'
                            : 'text-slate-300 hover:bg-slate-800/80'
                        }`}
                      >
                        <Search className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="font-semibold flex items-center gap-1.5">
                            Sparse BM25 Only
                            {searchMode === 'keyword' && <Check className="w-3 h-3 text-amber-400" />}
                          </div>
                          <p className="text-[10px] text-slate-400">Exact keyword matching with BM25 term frequency weighting.</p>
                        </div>
                      </button>
                    </div>
                  </>
                )}
              </div>

              {/* Filter Scope Button & Popover */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setFilterMenuOpen((prev) => !prev)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition cursor-pointer ${
                    metadataFilter
                      ? 'bg-cyan-950/80 text-cyan-300 border-cyan-500/50 shadow-sm shadow-cyan-500/10'
                      : 'bg-slate-800/80 text-slate-400 border-slate-700/60 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                  title="Filter knowledge base retrieval scope"
                >
                  <Filter className={`w-3 h-3 ${metadataFilter ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span className="truncate max-w-[110px] sm:max-w-[160px]">
                    {activeFilterLabel || (documents.length > 0 ? `All Docs (${documents.length})` : 'All Docs')}
                  </span>
                  {metadataFilter ? (
                    <span
                      role="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onFilterChange?.(null);
                      }}
                      className="ml-0.5 hover:text-white p-0.5 rounded cursor-pointer"
                      title="Clear filter"
                    >
                      <X className="w-3 h-3 text-cyan-300 hover:text-white" />
                    </span>
                  ) : (
                    <ChevronDown className="w-3 h-3 text-slate-500" />
                  )}
                </button>

                {/* Popover Dropdown Menu */}
                {filterMenuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-30"
                      onClick={() => setFilterMenuOpen(false)}
                    />
                    <div className="absolute left-0 bottom-full mb-2 w-80 sm:w-96 rounded-xl bg-slate-900 border border-slate-700/90 shadow-2xl p-2.5 z-40 text-xs backdrop-blur-xl space-y-2 max-h-80 overflow-y-auto">
                      <div className="flex items-center justify-between px-1 pb-1 border-b border-slate-800">
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                          <Filter className="w-3 h-3 text-cyan-400" />
                          Workspace Dokumen Rujukan
                        </span>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={handleSelectAllDocs}
                            className="text-[10px] text-cyan-400 hover:text-cyan-300 font-medium px-1.5 py-0.5 rounded hover:bg-slate-800 transition cursor-pointer"
                          >
                            Pilih Semua
                          </button>
                          <span className="text-slate-600">•</span>
                          <button
                            type="button"
                            onClick={handleClearDocs}
                            className="text-[10px] text-slate-400 hover:text-rose-400 font-medium px-1.5 py-0.5 rounded hover:bg-slate-800 transition cursor-pointer"
                          >
                            Kosongkan
                          </button>
                        </div>
                      </div>

                      {/* Document List with Multi-Select Checkboxes */}
                      {documents.length > 0 ? (
                        <div className="space-y-1">
                          <div className="px-1 text-[10px] text-slate-500 font-medium flex items-center justify-between">
                            <span>Daftar Dokumen ({activeDocIds.length}/{documents.length} aktif)</span>
                            <span className="text-[9px] text-slate-500">Centang dokumen rujukan</span>
                          </div>
                          {documents.map((doc) => {
                            const isChecked = activeDocIds.includes(doc.id);
                            const docTitle = doc.metadata?.title || doc.filename;
                            return (
                              <div
                                key={doc.id}
                                onClick={() => handleToggleDoc(doc.id)}
                                className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left transition cursor-pointer group ${
                                  isChecked
                                    ? 'bg-slate-800/90 text-slate-100 border border-cyan-500/30'
                                    : 'text-slate-400 hover:bg-slate-800/40 border border-transparent'
                                }`}
                              >
                                <div className="flex items-center gap-2.5 min-w-0 flex-1 mr-2">
                                  {/* Custom Checkbox */}
                                  <div
                                    className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition ${
                                      isChecked
                                        ? 'bg-cyan-500 border-cyan-400 text-slate-950 font-bold shadow-sm shadow-cyan-500/20'
                                        : 'border-slate-600 bg-slate-800/80 group-hover:border-slate-500'
                                    }`}
                                  >
                                    {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                                  </div>

                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-1.5">
                                      <FileText className="w-3.5 h-3.5 text-cyan-400/80 shrink-0" />
                                      <span className="truncate font-medium text-xs text-slate-200" title={docTitle}>
                                        {docTitle}
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono mt-0.5">
                                      {doc.metadata?.document_type && (
                                        <span className="uppercase text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-400">
                                          {doc.metadata.document_type}
                                        </span>
                                      )}
                                      <span>{doc.chunk_count || 0} chunk</span>
                                      {doc.filename !== docTitle && (
                                        <span className="truncate text-slate-600 max-w-[120px]">{doc.filename}</span>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                <button
                                  type="button"
                                  onClick={(e) => handleSoloDoc(doc.id, e)}
                                  className="opacity-0 group-hover:opacity-100 text-[10px] px-1.5 py-0.5 rounded bg-slate-700/60 hover:bg-cyan-600 text-slate-300 hover:text-white transition shrink-0 cursor-pointer"
                                  title="Jadikan satu-satunya rujukan aktif"
                                >
                                  Hanya Ini
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="text-center py-4 text-slate-500">
                          Belum ada dokumen yang diunggah.
                        </div>
                      )}

                      {/* Document Categories / Types */}
                      {uniqueDocTypes.length > 0 && (
                        <div className="pt-2 border-t border-slate-800 space-y-1">
                          <div className="px-1 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                            Filter Berdasarkan Kategori Dokumen
                          </div>
                          <div className="flex flex-wrap gap-1 pt-1">
                            {uniqueDocTypes.map((type) => {
                              const isSelected = metadataFilter?.document_type?.toLowerCase() === type.toLowerCase();
                              return (
                                <button
                                  key={type}
                                  type="button"
                                  onClick={() => {
                                    if (isSelected) {
                                      onFilterChange?.(null);
                                    } else {
                                      onFilterChange?.({ document_type: type });
                                    }
                                  }}
                                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition cursor-pointer ${
                                    isSelected
                                      ? 'bg-cyan-500/20 text-cyan-300 font-medium border border-cyan-500/40'
                                      : 'bg-slate-800/60 text-slate-400 border border-slate-700/50 hover:bg-slate-800 hover:text-slate-200'
                                  }`}
                                >
                                  <Tag className="w-3 h-3 text-emerald-400" />
                                  <span className="capitalize">{type}</span>
                                  {isSelected && <Check className="w-2.5 h-2.5 text-cyan-400" />}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>

              <span className="hidden xl:inline-flex items-center gap-1 text-[10px] text-zinc-300 font-mono bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/60">
                🛠️ Tools: RAG • SQL • Web • <span className="text-violet-400 font-semibold">🤖 Sub-Agents</span>
              </span>

              <span className="hidden lg:inline text-[11px] text-slate-500">
                Use <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-mono text-[10px] text-slate-400">Shift + Enter</kbd> for newline
              </span>
            </div>

            <div className="flex items-center space-x-2">
              {isStreaming ? (
                <button
                  onClick={onStop}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 text-xs font-medium transition shadow-sm cursor-pointer"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  onClick={onSend}
                  disabled={!input.trim()}
                  className={`p-2 rounded-xl transition flex items-center justify-center cursor-pointer ${
                    input.trim()
                      ? 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-md shadow-cyan-500/20 scale-100'
                      : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                  }`}
                  title="Send message"
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
