import React, { useState, useMemo } from 'react';
import {
  Plus,
  MessageSquare,
  Trash2,
  Server,
  Database,
  ChevronLeft,
  ChevronRight,
  Pin,
  Pencil,
  Check,
  X,
} from 'lucide-react';
import type { Thread, ServiceHealth } from '../types/chat';

interface SidebarProps {
  threads: Thread[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onDeleteThread: (threadId: string) => void;
  onRenameThread?: (threadId: string, newTitle: string) => void;
  onTogglePinThread?: (threadId: string, isPinned: boolean) => void;
  health: ServiceHealth | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onRenameThread,
  onTogglePinThread,
  health,
  collapsed,
  onToggleCollapse,
}) => {
  const isLlmOnline = health?.services?.llm?.status === 'online';
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Sort pinned threads first, then by updated_at descending
  const sortedThreads = useMemo(() => {
    return [...threads].sort((a, b) => {
      const pinA = a.is_pinned ? 1 : 0;
      const pinB = b.is_pinned ? 1 : 0;
      if (pinA !== pinB) return pinB - pinA;
      return new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime();
    });
  }, [threads]);

  const handleStartRename = (thread: Thread, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingThreadId(thread.id);
    setEditTitle(thread.title);
  };

  const handleSaveRename = (threadId: string) => {
    const trimmed = editTitle.trim();
    if (trimmed && onRenameThread) {
      onRenameThread(threadId, trimmed);
    }
    setEditingThreadId(null);
  };

  const handleCancelRename = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingThreadId(null);
  };

  return (
    <aside
      className={`h-full border-r border-slate-800/80 bg-slate-900/80 backdrop-blur-xl flex flex-col transition-all duration-300 relative z-20 ${
        collapsed ? 'w-16' : 'w-72'
      }`}
    >
      {/* Collapse Toggle Button */}
      <button
        onClick={onToggleCollapse}
        className="absolute -right-3 top-20 bg-slate-800 border border-slate-700 text-slate-300 rounded-full p-1 hover:bg-slate-700 hover:text-white transition shadow-md z-30 cursor-pointer"
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
      </button>

      {/* New Conversation Button */}
      <div className="p-3 border-b border-slate-800/80">
        <button
          onClick={onNewThread}
          className={`w-full py-2.5 px-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-xs flex items-center justify-center space-x-2 shadow-lg shadow-cyan-500/20 transition group cursor-pointer ${
            collapsed ? 'px-0' : ''
          }`}
          title="New Conversation"
        >
          <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-200" />
          {!collapsed && <span>New Conversation</span>}
        </button>
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {!collapsed && (
          <div className="px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Conversations ({threads.length})</span>
          </div>
        )}

        {sortedThreads.length === 0 ? (
          !collapsed && (
            <div className="text-center py-8 px-4 text-xs text-slate-500">
              No conversations yet. Start one above!
            </div>
          )
        ) : (
          sortedThreads.map((thread) => {
            const isActive = thread.id === activeThreadId;
            const isEditing = editingThreadId === thread.id;
            const isPinned = !!thread.is_pinned;

            return (
              <div
                key={thread.id}
                onClick={() => {
                  if (!isEditing) onSelectThread(thread.id);
                }}
                className={`group flex items-center justify-between rounded-lg px-2.5 py-2 text-xs transition cursor-pointer ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-200 font-medium border border-cyan-500/30'
                    : 'text-slate-300 hover:bg-slate-800/60 hover:text-white border border-transparent'
                } ${isPinned && !isActive ? 'bg-slate-800/30 border-amber-500/20' : ''}`}
                title={thread.title}
              >
                {/* Left Side: Icon & Title / Input */}
                {isEditing && !collapsed ? (
                  <div
                    className="flex items-center space-x-1 min-w-0 flex-1 mr-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveRename(thread.id);
                        if (e.key === 'Escape') handleCancelRename();
                      }}
                      autoFocus
                      className="w-full bg-slate-950 border border-cyan-500 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => handleSaveRename(thread.id)}
                      className="p-1 rounded hover:bg-emerald-500/20 text-emerald-400 hover:text-emerald-300 cursor-pointer"
                      title="Simpan (Enter)"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleCancelRename(e)}
                      className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white cursor-pointer"
                      title="Batal (Esc)"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2 min-w-0 flex-1">
                    {isPinned ? (
                      <Pin className="w-3.5 h-3.5 shrink-0 text-amber-400 fill-amber-400/40" />
                    ) : (
                      <MessageSquare
                        className={`w-3.5 h-3.5 shrink-0 ${
                          isActive ? 'text-cyan-400' : 'text-slate-500'
                        }`}
                      />
                    )}
                    {!collapsed && (
                      <span className="truncate flex-1" title={thread.title}>
                        {thread.title || 'Untitled Thread'}
                      </span>
                    )}
                  </div>
                )}

                {/* Right Side Action Buttons */}
                {!collapsed && !isEditing && (
                  <div className="flex items-center space-x-0.5 shrink-0 ml-1">
                    {/* Pin / Unpin Button */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onTogglePinThread?.(thread.id, !isPinned);
                      }}
                      className={`p-1 rounded hover:bg-slate-700/80 transition cursor-pointer ${
                        isPinned
                          ? 'text-amber-400 hover:text-amber-300'
                          : 'opacity-0 group-hover:opacity-100 text-slate-500 hover:text-amber-400'
                      }`}
                      title={isPinned ? 'Lepas Pin chat' : 'Pin chat ke paling atas'}
                    >
                      <Pin className={`w-3.5 h-3.5 ${isPinned ? 'fill-amber-400/40' : ''}`} />
                    </button>

                    {/* Rename Button */}
                    <button
                      type="button"
                      onClick={(e) => handleStartRename(thread, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-slate-700/80 text-slate-500 hover:text-cyan-300 transition cursor-pointer"
                      title="Ganti nama (Rename)"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>

                    {/* Delete Button */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteThread(thread.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 hover:text-red-400 text-slate-500 transition cursor-pointer"
                      title="Hapus chat"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Sidebar Footer with Live Connectivity Status */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/40 text-[11px] space-y-2">
        <div className="flex items-center justify-between text-slate-400">
          <div className="flex items-center space-x-2 min-w-0">
            <Server className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            {!collapsed && <span className="truncate">Ollama Engine</span>}
          </div>
          <div className="flex items-center space-x-1">
            <span
              className={`w-2 h-2 rounded-full ${
                isLlmOnline ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-red-400'
              }`}
            />
            {!collapsed && (
              <span className={`text-[10px] font-semibold ${isLlmOnline ? 'text-emerald-400' : 'text-red-400'}`}>
                {isLlmOnline ? 'ONLINE' : 'OFFLINE'}
              </span>
            )}
          </div>
        </div>

        {!collapsed && (
          <div className="flex items-center justify-between text-slate-400 pt-1 border-t border-slate-800/50">
            <div className="flex items-center space-x-2 min-w-0">
              <Database className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="truncate">ChromaDB + SQLite</span>
            </div>
            <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
              LOCAL
            </span>
          </div>
        )}
      </div>
    </aside>
  );
};
