import React, { useState, useRef } from 'react';
import type { DocumentItem } from '../types/chat';
import {
  Upload,
  FileText,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
  Database,
  Layers,
  Sparkles,
  RefreshCw,
  FileCheck,
  FileSpreadsheet,
  FileCode,
  Globe,
  Info,
  X,
} from 'lucide-react';

interface DocumentManagerProps {
  documents: DocumentItem[];
  onUpload: (file: File) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  isLoading: boolean;
}

export const DocumentManager: React.FC<DocumentManagerProps> = ({
  documents,
  onUpload,
  onDelete,
  onRefresh,
  isLoading,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastActionNotice, setLastActionNotice] = useState<string | null>(null);
  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') {
      return <FileText className="w-4 h-4 text-rose-400" />;
    }
    if (ext === 'docx' || ext === 'doc') {
      return <FileCheck className="w-4 h-4 text-blue-400" />;
    }
    if (ext === 'html' || ext === 'htm') {
      return <Globe className="w-4 h-4 text-amber-400" />;
    }
    if (ext === 'csv' || ext === 'xlsx') {
      return <FileSpreadsheet className="w-4 h-4 text-emerald-400" />;
    }
    if (ext === 'pptx') {
      return <Layers className="w-4 h-4 text-purple-400" />;
    }
    if (ext === 'json') {
      return <FileCode className="w-4 h-4 text-cyan-400" />;
    }
    return <FileText className="w-4 h-4 text-zinc-300" />;
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    setUploadError(null);
    setLastActionNotice(null);
    setIsUploading(true);

    try {
      await onUpload(file);
      setLastActionNotice(`Processed '${file.name}'. Multi-format parser & record manager indexed content.`);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleConfirmDelete = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    try {
      await onDelete(docToDelete.id);
      setLastActionNotice(`Cascade deleted '${docToDelete.filename}' and all its vector embeddings.`);
      setDocToDelete(null);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to delete document');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const totalChunks = documents.reduce((acc, doc) => acc + (doc.chunk_count || 0), 0);

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto bg-zinc-950 text-zinc-100 p-6 md:p-8">
      {/* Title & Stats */}
      <div className="max-w-5xl w-full mx-auto space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-semibold tracking-tight text-zinc-100 flex items-center gap-2.5">
                <Database className="w-6 h-6 text-emerald-400" />
                Multi-Domain Document Knowledge Base
              </h1>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/50">
                ChromaDB + SQLite • ID ↔ EN
              </span>
            </div>
            <p className="text-sm text-zinc-400 mt-1">
              Supports <strong className="text-zinc-200">Legal Documents, Inventory Sheets (.xlsx/.csv), Client Presentations (.pptx), and KPI Reports (.pdf/.docx)</strong>. Stored 100% locally in ChromaDB & SQLite with automatic SHA-256 hash deduplication.
            </p>
          </div>

          <button
            onClick={() => onRefresh()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-zinc-300 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/60 rounded-lg transition-colors cursor-pointer self-start sm:self-auto"
            title="Refresh document status"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Knowledge Base Overview Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4 flex items-center gap-3.5">
            <div className="p-2.5 rounded-lg bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-400">Total Documents</p>
              <p className="text-xl font-bold text-zinc-100">{documents.length}</p>
            </div>
          </div>

          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4 flex items-center gap-3.5">
            <div className="p-2.5 rounded-lg bg-blue-950/60 text-blue-400 border border-blue-800/40">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-400">Indexed Chunks</p>
              <p className="text-xl font-bold text-zinc-100">{totalChunks}</p>
            </div>
          </div>

          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4 flex items-center gap-3.5">
            <div className="p-2.5 rounded-lg bg-cyan-950/60 text-cyan-400 border border-cyan-800/40">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-400">Multi-Domain Engine</p>
              <p className="text-xs font-semibold text-cyan-300">Legal • Inventory • KPI • Deck</p>
            </div>
          </div>
        </div>

        {/* Drag & Drop Upload Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isUploading && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 ${
            isDragging
              ? 'border-emerald-500 bg-emerald-950/20 shadow-lg shadow-emerald-950/30'
              : 'border-zinc-800 hover:border-zinc-700 bg-zinc-900/30 hover:bg-zinc-900/50'
          } ${isUploading ? 'opacity-70 pointer-events-none' : ''}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.pptx,.xlsx,.html,.htm,.txt,.md,.markdown,.json,.csv"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />

          <div className="p-3.5 rounded-full bg-zinc-800/80 text-emerald-400 mb-3.5 border border-zinc-700/60">
            <Upload className={`w-6 h-6 ${isUploading ? 'animate-bounce' : ''}`} />
          </div>

          <p className="text-sm font-medium text-zinc-200">
            {isUploading ? (
              <span className="flex items-center gap-2 text-emerald-400">
                <RefreshCw className="w-4 h-4 animate-spin" /> Deep parsing document & generating vector embeddings...
              </span>
            ) : (
              <>
                <span className="text-emerald-400 hover:underline">Click to upload</span> or drag and drop files here
              </>
            )}
          </p>

          <p className="text-xs text-zinc-400 mt-1.5 flex items-center justify-center gap-2 flex-wrap">
            <span>📄 PDF (.pdf)</span>
            <span>•</span>
            <span>📝 Word (.docx)</span>
            <span>•</span>
            <span>📊 PowerPoint (.pptx)</span>
            <span>•</span>
            <span>📈 Excel & CSV (.xlsx, .csv)</span>
            <span>•</span>
            <span>🌐 HTML & Markdown (.html, .md)</span>
            <span>•</span>
            <span>📑 TXT & JSON</span>
          </p>
        </div>

        {uploadError && (
          <div className="flex items-center gap-2.5 p-3.5 bg-rose-950/50 border border-rose-800/60 text-rose-200 text-xs rounded-lg">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{uploadError}</span>
          </div>
        )}

        {lastActionNotice && (
          <div className="flex items-center gap-2.5 p-3.5 bg-cyan-950/40 border border-cyan-800/50 text-cyan-200 text-xs rounded-lg">
            <Info className="w-4 h-4 text-cyan-400 shrink-0" />
            <span>{lastActionNotice}</span>
          </div>
        )}

        {/* Document Ingestion Table / List */}
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl overflow-hidden shadow-sm">
          <div className="px-5 py-3.5 border-b border-zinc-800/80 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
              <FileText className="w-4 h-4 text-zinc-400" />
              Ingested Documents ({documents.length})
            </h2>
          </div>

          {documents.length === 0 ? (
            <div className="py-12 px-4 text-center">
              <FileText className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm font-medium text-zinc-400">No documents uploaded yet</p>
              <p className="text-xs text-zinc-500 mt-1">
                Upload your PDF, Word, HTML, or Markdown files above to build your local RAG knowledge base.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800/60">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-zinc-850/50 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2 rounded-lg bg-zinc-800/80 text-zinc-300 shrink-0 border border-zinc-700/50">
                      {getFileIcon(doc.filename)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-zinc-100 truncate" title={doc.filename}>
                          {doc.metadata?.title || doc.filename}
                        </p>
                        {doc.metadata?.title && doc.metadata.title !== doc.filename && (
                          <span className="text-[11px] font-mono text-zinc-400">({doc.filename})</span>
                        )}
                        {doc.metadata?.document_type && (
                          <span className="text-[10px] uppercase font-semibold tracking-wider px-2 py-0.5 rounded-full bg-purple-950/80 text-purple-300 border border-purple-800/50">
                            {doc.metadata.document_type}
                          </span>
                        )}
                      </div>

                      {doc.metadata?.summary && (
                        <p className="text-xs text-zinc-300 mt-1 line-clamp-2 leading-relaxed">
                          {doc.metadata.summary}
                        </p>
                      )}

                      <div className="flex items-center gap-3 text-xs text-zinc-400 mt-1.5 flex-wrap">
                        <span>{formatFileSize(doc.file_size)}</span>
                        <span>•</span>
                        <span className="text-emerald-400 font-mono font-medium">{doc.chunk_count} chunks</span>
                        {doc.content_hash && (
                          <>
                            <span>•</span>
                            <span className="font-mono text-[10px] text-zinc-500" title={`SHA256: ${doc.content_hash}`}>
                              hash: {doc.content_hash.slice(0, 8)}...
                            </span>
                          </>
                        )}
                        <span>•</span>
                        <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                      </div>

                      {doc.metadata?.keywords && doc.metadata.keywords.length > 0 && (
                        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                          {doc.metadata.keywords.map((kw, ki) => (
                            <span
                              key={ki}
                              className="text-[10px] px-2 py-0.5 rounded-md bg-zinc-800/90 text-cyan-300 border border-zinc-700/60 font-mono"
                            >
                              #{kw}
                            </span>
                          ))}
                        </div>
                      )}

                      {doc.message && (
                        <p className="text-[11px] text-cyan-400 mt-1">{doc.message}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-auto shrink-0">
                    {/* Status / Action badge */}
                    {doc.doc_action === 'updated' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-950/60 text-cyan-400 border border-cyan-800/40">
                        <RefreshCw className="w-3 h-3" /> Updated
                      </span>
                    )}
                    {doc.doc_action === 'skipped' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-950/60 text-amber-400 border border-amber-800/40">
                        <Info className="w-3 h-3" /> Deduplicated
                      </span>
                    )}
                    {(!doc.doc_action || doc.doc_action === 'created' || doc.doc_action === 'indexed') && doc.status === 'completed' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
                        <CheckCircle2 className="w-3 h-3" /> Indexed
                      </span>
                    )}
                    {doc.status === 'processing' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-950/60 text-amber-400 border border-amber-800/40">
                        <Clock className="w-3 h-3 animate-spin" /> Processing
                      </span>
                    )}
                    {doc.status === 'failed' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-950/60 text-rose-400 border border-rose-800/40">
                        <AlertCircle className="w-3 h-3" /> Failed
                      </span>
                    )}

                    {/* Delete action button with cascade confirmation */}
                    <button
                      onClick={() => setDocToDelete(doc)}
                      className="p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-rose-950/30 rounded-lg transition-colors cursor-pointer"
                      title="Cascade delete document and all vector chunks"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Cascade Delete Confirmation Modal */}
      {docToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-rose-950/80 text-rose-400 border border-rose-800/50">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-zinc-100">Cascade Delete Document</h3>
                  <p className="text-xs text-zinc-400">Irreversible knowledge base deletion</p>
                </div>
              </div>
              <button
                onClick={() => !isDeleting && setDocToDelete(null)}
                className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/80 text-xs text-zinc-300 space-y-1.5">
              <p>
                Are you sure you want to delete <strong className="text-zinc-100">'{docToDelete.metadata?.title || docToDelete.filename}'</strong>?
              </p>
              <p className="text-zinc-400">
                This will trigger a <span className="text-rose-400 font-semibold">cascade delete</span>:
              </p>
              <ul className="list-disc pl-4 text-zinc-400 space-y-0.5">
                <li>Document record removed from database.</li>
                <li>All <span className="text-emerald-400 font-mono font-medium">{docToDelete.chunk_count}</span> vector chunks & embeddings permanently purged.</li>
                <li>Any active chat filter targeting this document will be cleared.</li>
              </ul>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDocToDelete(null)}
                disabled={isDeleting}
                className="px-3.5 py-2 text-xs font-medium text-zinc-300 hover:text-zinc-100 bg-zinc-800 hover:bg-zinc-700/80 rounded-xl transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-500 rounded-xl transition shadow-lg shadow-rose-600/20 cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Purging Chunks...</span>
                  </>
                ) : (
                  <span>Delete & Cascade Purge</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
