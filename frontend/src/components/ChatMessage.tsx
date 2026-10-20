import React, { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bot,
  User,
  Copy,
  Check,
  FileText,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  Globe,
  Database,
  ExternalLink,
  Wrench,
  Layers,
  Compass,
  BrainCircuit,
  X,
  Highlighter,
} from 'lucide-react';
import type { Message, SourceCitation } from '../types/chat';

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [subagentOpen, setSubagentOpen] = useState(true);
  const [selectedCitation, setSelectedCitation] = useState<SourceCitation | null>(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Close modal on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && selectedCitation) {
        setSelectedCitation(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedCitation]);

  // Convert inline citations like [1], [2], [1, 2], [Dokumen 1] to markdown anchor links for clickable badges
  const processedContent = useMemo(() => {
    if (isUser || !message.content) return message.content;
    let text = message.content;
    // Multi citations: [1, 2] or [1, 2, 3]
    text = text.replace(/(?<!\[)\[(\d+)\s*,\s*(\d+)\](?!\()/g, '[$1](#cite-$1) [$2](#cite-$2)');
    text = text.replace(/(?<!\[)\[(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\](?!\()/g, '[$1](#cite-$1) [$2](#cite-$2) [$3](#cite-$3)');
    // Prefix citations: [Dokumen 1] or [Kutipan 1]
    text = text.replace(/(?<!\[)\[(?:Kutipan|Dokumen)\s*(\d+)\](?!\()/gi, '[$1](#cite-$1)');
    // Standard single citations: [1], [2], etc.
    text = text.replace(/(?<!\[)\[(\d+)\](?!\()/g, '[$1](#cite-$1)');
    return text;
  }, [message.content, isUser]);

  const hasSources = !isUser && message.sources && message.sources.length > 0;
  const hasToolEvents = !isUser && message.tool_events && message.tool_events.length > 0;
  const hasSubAgents = !isUser && message.subagent_events && message.subagent_events.length > 0;


  return (
    <div
      className={`py-4 px-4 md:px-6 flex gap-4 transition-colors ${
        isUser
          ? 'bg-transparent justify-end'
          : 'bg-zinc-900/40 border-y border-zinc-800/40 justify-start'
      }`}
    >
      <div
        className={`flex gap-3 max-w-4xl w-full ${
          isUser ? 'flex-row-reverse self-end justify-start max-w-2xl' : 'flex-row'
        }`}
      >
        {/* Avatar */}
        <div
          className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-md ${
            isUser
              ? 'bg-gradient-to-tr from-indigo-500 to-violet-600 text-white shadow-indigo-500/20'
              : 'bg-gradient-to-tr from-emerald-500 to-cyan-600 text-white shadow-emerald-500/20 ring-1 ring-emerald-400/30'
          }`}
        >
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </div>

        {/* Message Content Container */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-zinc-300">
                {isUser ? 'Anda' : 'Asisten RAG'}
              </span>
              {!isUser && (
                <span className="text-[10px] text-emerald-400 bg-emerald-950/70 border border-emerald-800/40 px-1.5 py-0.2 rounded font-mono">
                  {message.model || 'qwen2.5:7b'}
                </span>
              )}
            </div>

            {!isUser && message.content && (
              <button
                onClick={handleCopy}
                className="text-zinc-500 hover:text-zinc-300 p-1 rounded hover:bg-zinc-800 transition cursor-pointer"
                title="Copy response"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {/* Tools Activated Badges (Module 7) */}
          {hasToolEvents && (
            <div className="flex items-center gap-1.5 flex-wrap mb-2.5">
              <span className="text-[10px] text-zinc-500 font-medium flex items-center gap-1">
                <Wrench className="w-3 h-3 text-cyan-400" /> Tools Activated:
              </span>
              {message.tool_events!.map((t, tidx) => (
                <span
                  key={tidx}
                  className="text-[10px] px-2 py-0.5 rounded-full font-mono flex items-center gap-1 bg-zinc-800/80 border border-zinc-700/60 text-zinc-300"
                >
                  {t.tool === 'text_to_sql' && <Database className="w-3 h-3 text-emerald-400" />}
                  {t.tool === 'web_search' && <Globe className="w-3 h-3 text-blue-400" />}
                  {t.tool === 'local_retrieval' && <Sparkles className="w-3 h-3 text-cyan-400" />}
                  <span>
                    {t.tool === 'text_to_sql' ? 'Text-to-SQL' : t.tool === 'web_search' ? 'Web Search' : 'Knowledge Base'}
                  </span>
                  {t.status === 'success' && <span className="text-emerald-400">✓</span>}
                  {t.status === 'executing' && <span className="text-amber-400 animate-spin">●</span>}
                </span>
              ))}
            </div>
          )}

          {/* Sub-Agent Deep Analysis & Hierarchical Reasoning (Module 8) */}
          {hasSubAgents && (
            <div className="mb-3.5 rounded-xl border border-violet-800/50 bg-gradient-to-br from-violet-950/30 via-zinc-900/60 to-zinc-950 overflow-hidden text-xs shadow-lg shadow-violet-950/20">
              <button
                onClick={() => setSubagentOpen(!subagentOpen)}
                className="w-full px-3.5 py-2.5 flex items-center justify-between text-violet-300 hover:bg-violet-900/20 transition cursor-pointer"
              >
                <div className="flex items-center gap-2.5 font-medium">
                  <div className="p-1 rounded-md bg-violet-600/25 border border-violet-500/40 text-violet-300">
                    <BrainCircuit className="w-4 h-4 animate-pulse" />
                  </div>
                  <div className="text-left">
                    <div className="flex items-center gap-2 font-semibold text-zinc-100">
                      <span>{message.subagent_events![0].name}</span>
                      <span className="text-[10px] px-2 py-0.2 rounded-full bg-violet-500/20 text-violet-300 border border-violet-500/30 font-mono">
                        {message.subagent_events![0].role}
                      </span>
                    </div>
                    <div className="text-[10px] text-violet-400/80 mt-0.5">
                      Target: <span className="font-medium text-zinc-300">{message.subagent_events![0].target_document || 'Full Document'}</span>
                      {message.subagent_events![0].model_used && (
                        <>
                          {' • Model: '}
                          <span className="font-mono text-violet-300 font-semibold">{message.subagent_events![0].model_used}</span>
                        </>
                      )}
                      {' • '}
                      {message.subagent_events![0].status === 'completed'
                        ? `✓ Completed in ${message.subagent_events![0].elapsed_seconds || 0}s`
                        : '● Executing in progress...'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-900/40 border border-violet-700/50 text-violet-300 font-mono">
                    Isolated Context
                  </span>
                  {subagentOpen ? <ChevronDown className="w-4 h-4 text-violet-400" /> : <ChevronRight className="w-4 h-4 text-violet-400" />}
                </div>
              </button>

              {subagentOpen && (
                <div className="p-3.5 pt-1 space-y-3 border-t border-violet-800/30 bg-zinc-950/60">
                  {/* Main Agent Delegation Rationale */}
                  {message.subagent_events![0].delegation_reason && (
                    <div className="p-2.5 rounded-lg bg-violet-950/30 border border-violet-800/40 text-violet-200">
                      <span className="font-semibold text-violet-300 flex items-center gap-1.5 mb-1 text-[11px]">
                        <Compass className="w-3.5 h-3.5 text-violet-400" /> Main Agent Delegation Rationale:
                      </span>
                      <p className="text-[11px] text-zinc-300 leading-relaxed font-sans">
                        {message.subagent_events![0].delegation_reason}
                      </p>
                    </div>
                  )}

                  {/* Sub-Agent Step Timeline */}
                  <div className="space-y-1.5">
                    <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Layers className="w-3 h-3 text-violet-400" /> Sub-Agent Execution Trace & Tools Called:
                    </div>
                    <div className="space-y-1">
                      {message.subagent_events![0].steps.map((st, sidx) => (
                        <div
                          key={sidx}
                          className="px-2.5 py-1.5 rounded-md bg-zinc-900/80 border border-zinc-800/80 flex items-start gap-2 text-[11px]"
                        >
                          <span className="mt-0.5 shrink-0">
                            {st.status === 'done' ? (
                              <span className="text-emerald-400 text-xs font-bold">✓</span>
                            ) : (
                              <span className="text-violet-400 animate-spin text-xs">●</span>
                            )}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="font-medium text-zinc-200 flex items-center justify-between">
                              <span>{st.name}</span>
                              <span className="text-[9px] font-mono text-zinc-500 uppercase">{st.status}</span>
                            </div>
                            <div className="text-[10px] text-zinc-400 font-mono mt-0.5 break-words">
                              {st.detail}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Summary Banner */}
                  {message.subagent_events![0].summary && (
                    <div className="p-2 rounded-lg bg-emerald-950/30 border border-emerald-900/40 text-emerald-300 text-[11px] flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                      <span>{message.subagent_events![0].summary}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Sources Badge / Accordion for Assistant */}
          {hasSources && (
            <div className="mb-3 rounded-lg border border-emerald-800/40 bg-emerald-950/20 overflow-hidden text-xs">
              <button
                onClick={() => setSourcesOpen(!sourcesOpen)}
                className="w-full px-3 py-1.5 flex items-center justify-between text-emerald-300 hover:bg-emerald-950/40 transition cursor-pointer"
              >
                <div className="flex items-center gap-1.5 font-medium">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Retrieved Knowledge & Tool Sources ({message.sources!.length})</span>
                </div>
                {sourcesOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>

              {sourcesOpen && (
                <div className="p-2.5 pt-1 space-y-2 border-t border-emerald-800/30">
                  {message.sources!.map((src, i) => (
                    <div
                      key={i}
                      onClick={() => setSelectedCitation(src)}
                      className="p-2.5 rounded-lg bg-zinc-950/70 hover:bg-zinc-900 border border-zinc-800/80 hover:border-cyan-500/50 text-zinc-300 space-y-1.5 transition cursor-pointer group"
                      title="Klik untuk membuka teks lengkap dan rujukan"
                    >
                      <div className="flex items-start justify-between gap-2 text-[11px] font-medium text-emerald-400">
                        <div className="flex items-center gap-1.5 min-w-0">
                          {/* Citation Index Badge */}
                          <span className="text-[10px] px-1.5 py-0.2 rounded font-mono font-bold bg-cyan-950/90 border border-cyan-500/60 text-cyan-300 shrink-0 shadow-sm group-hover:scale-105 transition">
                            [{src.citation_index || i + 1}]
                          </span>

                          {/* Tool / Format Icon */}
                          {src.search_mode === 'web' || src.url ? (
                            <Globe className="w-3.5 h-3.5 shrink-0 text-blue-400" />
                          ) : src.search_mode === 'sql' ? (
                            <Database className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                          ) : (
                            <FileText className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                          )}

                          {/* Title / Link */}
                          {src.url ? (
                            <a
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="font-semibold text-blue-400 hover:text-blue-300 hover:underline truncate flex items-center gap-1"
                              title={src.url}
                            >
                              <span>{src.title || src.filename}</span>
                              <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-80" />
                            </a>
                          ) : (
                            <span className="font-semibold text-zinc-200 truncate group-hover:text-cyan-200 transition" title={src.title || src.filename}>
                              {src.title || src.filename}
                            </span>
                          )}

                          {src.title && src.title !== src.filename && !src.url && (
                            <span className="text-[10px] text-zinc-500 truncate font-normal">
                              ({src.filename})
                            </span>
                          )}

                          {src.page_label && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-cyan-300 font-mono shrink-0">
                              {src.page_label}
                            </span>
                          )}

                          {src.document_type && src.document_type !== 'general' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/50 text-emerald-300 font-mono uppercase tracking-wider shrink-0">
                              {src.document_type}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
                          {src.search_mode === 'web' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-950/70 border border-blue-700/50 text-blue-300 font-mono font-medium flex items-center gap-1">
                              🌐 Web Search
                            </span>
                          )}
                          {src.search_mode === 'sql' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/70 border border-emerald-700/50 text-emerald-300 font-mono font-medium flex items-center gap-1">
                              📊 Text-to-SQL
                            </span>
                          )}
                          {src.search_mode === 'hybrid' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950/70 border border-cyan-700/50 text-cyan-300 font-mono font-medium flex items-center gap-1">
                              ⚡ Hybrid
                            </span>
                          )}
                          {src.search_mode === 'vector' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-950/70 border border-indigo-700/50 text-indigo-300 font-mono font-medium">
                              🎯 Vector
                            </span>
                          )}
                          {src.search_mode === 'keyword' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/70 border border-amber-700/50 text-amber-300 font-mono font-medium">
                              🔍 BM25
                            </span>
                          )}
                          {src.rerank_score !== undefined && src.rerank_score !== null && (
                            <span
                              className="text-[9px] px-1.5 py-0.5 rounded bg-purple-950/70 border border-purple-700/50 text-purple-300 font-mono font-medium"
                              title={src.rerank_reason || 'Reranker confidence'}
                            >
                              Rerank: {(src.rerank_score * 100).toFixed(0)}%
                            </span>
                          )}
                          {src.similarity > 0 && (
                            <span className="font-mono text-zinc-400 text-[10px] bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                              {(src.similarity * 100).toFixed(0)}% match
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Rerank reason chip if present */}
                      {src.rerank_reason && (
                        <div className="text-[10px] text-zinc-400 font-mono flex items-center gap-1">
                          <span className="text-zinc-500">Signal:</span>
                          <span className="text-purple-300/90">{src.rerank_reason}</span>
                        </div>
                      )}

                      {/* Keywords tags if present */}
                      {src.keywords && src.keywords.length > 0 && (
                        <div className="flex items-center gap-1 flex-wrap pt-0.5">
                          {src.keywords.slice(0, 4).map((kw, kidx) => (
                            <span
                              key={kidx}
                              className="text-[9px] px-1.5 py-0.5 rounded-full bg-zinc-900 text-zinc-400 border border-zinc-800"
                            >
                              #{kw}
                            </span>
                          ))}
                        </div>
                      )}

                      <p className="text-[11px] text-zinc-400 line-clamp-2 italic font-mono bg-zinc-900/60 p-1.5 rounded border border-zinc-800/40 group-hover:border-slate-700">
                        "{src.snippet}"
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Message Body */}
          <div
            className={`text-sm leading-relaxed ${
              isUser
                ? 'bg-zinc-800/90 text-zinc-100 rounded-2xl rounded-tr-none px-4 py-3 border border-zinc-700/60 shadow-sm'
                : 'text-zinc-200'
            }`}
          >
            {isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <div className="prose prose-invert prose-sm max-w-none space-y-3">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 leading-relaxed text-zinc-200">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-5 my-2 space-y-1 text-zinc-300">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-5 my-2 space-y-1 text-zinc-300">{children}</ol>,
                    li: ({ children }) => <li className="text-zinc-300">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                    a: ({ href, children }) => {
                      if (href && (href.startsWith('#cite-') || href.startsWith('#citation-'))) {
                        const citeNum = parseInt(href.replace(/#cite(?:ation)?-/, ''), 10);
                        const matchedSource = message.sources?.find(
                          (s, idx) => s.citation_index === citeNum || (idx + 1) === citeNum
                        );
                        return (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              if (matchedSource) {
                                setSelectedCitation(matchedSource);
                              }
                            }}
                            className="inline-flex items-center justify-center px-1.5 py-0.2 mx-0.5 text-[11px] font-mono font-bold text-cyan-300 bg-cyan-950/90 hover:bg-cyan-800/90 border border-cyan-500/50 hover:border-cyan-400 rounded cursor-pointer transition transform hover:scale-105 shadow-sm align-baseline"
                            title={
                              matchedSource
                                ? `Kutipan [${citeNum}]: ${matchedSource.title || matchedSource.filename} (${matchedSource.page_label || 'Hal ?'}) - Klik untuk memeriksa teks rujukan asli`
                                : `Kutipan [${citeNum}]`
                            }
                          >
                            [{children}]
                          </button>
                        );
                      }
                      return (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline inline-flex items-center gap-0.5">
                          {children}
                          <ExternalLink className="w-3 h-3 inline opacity-70" />
                        </a>
                      );
                    },
                    code: ({ className, children, ...props }: any) => {
                      const match = /language-(\w+)/.exec(className || '');
                      const codeString = String(children).replace(/\n$/, '');
                      const isInline = !match && !codeString.includes('\n');

                      if (isInline) {
                        return (
                          <code className="bg-zinc-800 text-emerald-300 px-1.5 py-0.5 rounded text-xs font-mono border border-zinc-700/60" {...props}>
                            {children}
                          </code>
                        );
                      }

                      return (
                        <div className="my-3 rounded-xl overflow-hidden border border-zinc-700/70 bg-zinc-950 shadow-md">
                          <div className="bg-zinc-900/90 px-4 py-1.5 flex items-center justify-between border-b border-zinc-800 text-xs text-zinc-400 font-mono">
                            <span>{match ? match[1] : 'code'}</span>
                            <button
                              onClick={() => navigator.clipboard.writeText(codeString)}
                              className="hover:text-white flex items-center space-x-1 cursor-pointer"
                            >
                              <Copy className="w-3 h-3" />
                              <span>Copy</span>
                            </button>
                          </div>
                          <pre className="p-4 text-xs font-mono text-zinc-200 overflow-x-auto bg-zinc-950/80">
                            <code>{children}</code>
                          </pre>
                        </div>
                      );
                    },
                  }}
                >
                  {processedContent}
                </ReactMarkdown>

                {message.isStreaming && (
                  <span className="cursor-blink" title="Streaming..." />
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Interactive Citation Inspector Modal (NotebookLM Style Grounding Inspector) */}
      {selectedCitation && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
          onClick={() => setSelectedCitation(null)}
        >
          <div
            className="relative w-full max-w-2xl rounded-2xl bg-slate-900 border border-cyan-500/50 shadow-2xl overflow-hidden flex flex-col max-h-[85vh] text-left animate-in fade-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="px-5 py-4 bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border-b border-slate-700/80 flex items-center justify-between">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-500/50 flex items-center justify-center text-cyan-300 font-mono font-bold text-xs shrink-0">
                  [{selectedCitation.citation_index || '✓'}]
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-slate-100 truncate flex items-center gap-2">
                    <span>{selectedCitation.title || selectedCitation.filename}</span>
                  </h3>
                  <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono mt-0.5">
                    {selectedCitation.page_label && (
                      <span className="text-cyan-300 font-medium">{selectedCitation.page_label}</span>
                    )}
                    {selectedCitation.page_label && <span>•</span>}
                    <span>{selectedCitation.filename}</span>
                    {selectedCitation.search_mode && (
                      <>
                        <span>•</span>
                        <span className="capitalize">{selectedCitation.search_mode} Search</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <button
                onClick={() => setSelectedCitation(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
                title="Tutup (Esc)"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body: Grounding Passage & Highlighted Content */}
            <div className="p-5 overflow-y-auto space-y-3.5 flex-1">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5 font-medium text-cyan-400">
                  <Highlighter className="w-3.5 h-3.5" />
                  Teks Asli Rujukan Dokumen (Grounding Passage):
                </span>
                {selectedCitation.similarity > 0 && (
                  <span className="font-mono text-[10px] bg-slate-800 px-2 py-0.5 rounded border border-slate-700 text-emerald-400">
                    {(selectedCitation.similarity * 100).toFixed(0)}% Relevance Match
                  </span>
                )}
              </div>

              {/* Text Container */}
              <div className="p-4 rounded-xl bg-slate-950/90 border border-slate-800 text-slate-200 text-xs sm:text-sm leading-relaxed font-sans shadow-inner selection:bg-cyan-500/30 whitespace-pre-wrap max-h-[48vh] overflow-y-auto border-l-4 border-l-cyan-500">
                {selectedCitation.content || selectedCitation.snippet || 'Kutipan teks tidak tersedia.'}
              </div>

              {/* Additional Metadata / Keywords if present */}
              {selectedCitation.keywords && selectedCitation.keywords.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap pt-1">
                  <span className="text-[10px] text-slate-500 font-mono">Kata Kunci Terindeks:</span>
                  {selectedCitation.keywords.map((kw, kidx) => (
                    <span
                      key={kidx}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono"
                    >
                      #{kw}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3 bg-slate-900 border-t border-slate-800 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                {/* Navigation between citations if message has multiple */}
                {message.sources && message.sources.length > 1 && (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={
                        (message.sources.findIndex((s) => s.id === selectedCitation.id) || 0) <= 0
                      }
                      onClick={() => {
                        const currIdx = message.sources!.findIndex((s) => s.id === selectedCitation.id);
                        if (currIdx > 0) setSelectedCitation(message.sources![currIdx - 1]);
                      }}
                      className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                      title="Kutipan Sebelumnya"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-[11px] font-mono text-slate-400 px-1">
                      {(message.sources.findIndex((s) => s.id === selectedCitation.id) ?? 0) + 1} / {message.sources.length}
                    </span>
                    <button
                      type="button"
                      disabled={
                        (message.sources.findIndex((s) => s.id === selectedCitation.id) || 0) >= message.sources.length - 1
                      }
                      onClick={() => {
                        const currIdx = message.sources!.findIndex((s) => s.id === selectedCitation.id);
                        if (currIdx < message.sources!.length - 1) setSelectedCitation(message.sources![currIdx + 1]);
                      }}
                      className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                      title="Kutipan Berikutnya"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const textToCopy = selectedCitation.content || selectedCitation.snippet;
                    navigator.clipboard.writeText(textToCopy);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition cursor-pointer"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>Salin Kutipan</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedCitation(null)}
                  className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium transition cursor-pointer"
                >
                  Selesai
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

