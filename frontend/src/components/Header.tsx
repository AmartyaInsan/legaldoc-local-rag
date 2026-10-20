import React from 'react';
import { Sparkles, Database, Cpu, ShieldCheck, MessageSquare, Files, Bot } from 'lucide-react';
import type { ServiceHealth } from '../types/chat';

interface HeaderProps {
  health: ServiceHealth | null;
  activeModel: string;
  onModelChange: (model: string) => void;
  subagentModel?: string;
  onSubagentModelChange?: (model: string) => void;
  availableModels?: string[];
  threadTitle?: string;
  activeTab: 'chat' | 'documents';
  onTabChange: (tab: 'chat' | 'documents') => void;
  documentCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  activeModel,
  onModelChange,
  subagentModel = 'qwen2.5:7b',
  onSubagentModelChange,
  availableModels,
  threadTitle,
  activeTab,
  onTabChange,
  documentCount,
}) => {
  const models = availableModels || health?.services?.llm?.available_models || [activeModel];
  const isOllamaOnline = health?.services?.llm?.status === 'online';
  const isLocalDbConnected = health?.services?.local_db?.status === 'connected';

  return (
    <header className="h-16 border-b border-zinc-800 bg-zinc-900/70 backdrop-blur-xl px-4 md:px-6 flex items-center justify-between z-10">
      {/* Brand & Title */}
      <div className="flex items-center space-x-3 min-w-0">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 ring-1 ring-emerald-400/30 shrink-0">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center space-x-2">
            <h1 className="text-base font-bold tracking-tight text-white font-['Outfit'] truncate">
              LegalDoc <span className="text-emerald-400 font-normal">Local RAG</span>
            </h1>
            <span className="text-[10px] uppercase font-semibold tracking-wider px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/50 shrink-0">
              Ollama • Local
            </span>
          </div>
          <p className="text-xs text-zinc-400 truncate max-w-xs md:max-w-md">
            {activeTab === 'chat'
              ? threadTitle || 'Multi-Domain & Legal Assistant • Bilingual (ID/EN) Local RAG'
              : 'Multi-Domain Document Management (Legal, Inventory, KPI, Presentations)'}
          </p>
        </div>
      </div>

      {/* Center Tabs: Chat vs Documents */}
      <div className="flex items-center bg-zinc-950/80 p-1 rounded-xl border border-zinc-800/80 shadow-inner">
        <button
          onClick={() => onTabChange('chat')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            activeTab === 'chat'
              ? 'bg-zinc-800 text-zinc-100 shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Chat</span>
        </button>

        <button
          onClick={() => onTabChange('documents')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            activeTab === 'documents'
              ? 'bg-zinc-800 text-zinc-100 shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <Files className="w-3.5 h-3.5 text-emerald-400" />
          <span>Knowledge</span>
          {documentCount > 0 && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800/50">
              {documentCount}
            </span>
          )}
        </button>
      </div>

      {/* Right Badges & Dual Model Selectors */}
      <div className="hidden sm:flex items-center space-x-2.5">
        {/* Local Vector Store Status Badge */}
        <div
          className="hidden xl:flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/50 border border-zinc-700/60 text-xs text-zinc-300"
          title="100% Local Close-Environment Storage (ChromaDB Vector Index + SQLite)"
        >
          <Database className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-zinc-400">Local DB:</span>
          <span className="font-mono text-emerald-300 text-[11px]">
            {isLocalDbConnected ? 'ChromaDB + SQLite' : 'ChromaDB Local'}
          </span>
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 ml-1" />
        </div>

        {/* Main Agent Model Selector Pill */}
        <div className="flex items-center space-x-2 px-2.5 py-1.5 rounded-lg bg-zinc-800/70 border border-zinc-700/80 text-xs text-zinc-200 shadow-sm" title="Main Agent LLM Model">
          <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[11px] text-zinc-400 font-medium">Main:</span>
          <div className="flex items-center space-x-1">
            <span
              className={`w-2 h-2 rounded-full ${
                isOllamaOnline ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-amber-400'
              }`}
            />
            <select
              value={activeModel}
              onChange={(e) => onModelChange(e.target.value)}
              className="bg-transparent text-zinc-200 text-xs font-medium focus:outline-none cursor-pointer pr-1"
            >
              {models.map((m) => (
                <option key={m} value={m} className="bg-zinc-900 text-zinc-200">
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Sub-Agent Model Selector Pill */}
        {onSubagentModelChange && (
          <div className="flex items-center space-x-2 px-2.5 py-1.5 rounded-lg bg-violet-950/40 border border-violet-700/60 text-xs text-zinc-200 shadow-sm" title="Sub-Agent Specialist LLM Model">
            <Bot className="w-3.5 h-3.5 text-violet-400" />
            <span className="text-[11px] text-violet-300 font-medium">Sub-Agent:</span>
            <select
              value={subagentModel}
              onChange={(e) => onSubagentModelChange(e.target.value)}
              className="bg-transparent text-violet-200 text-xs font-medium focus:outline-none cursor-pointer pr-1"
            >
              {models.map((m) => (
                <option key={m} value={m} className="bg-zinc-900 text-zinc-200">
                  {m}
                </option>
              ))}
            </select>
            <span className="text-[9px] text-violet-400 uppercase font-semibold tracking-wider bg-violet-950/80 px-1 py-0.2 rounded border border-violet-800/40">
              Isolated
            </span>
          </div>
        )}
      </div>
    </header>
  );
};

