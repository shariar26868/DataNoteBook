"use client";

import * as React from "react";
import Link from "next/link";
import { Eye, Sparkles, Upload, Play } from "lucide-react";

interface TopbarProps {
  notebookTitle?: string;
  setNotebookTitle?: (title: string) => void;
  saveStatus?: string;
  saveNotebook?: () => void;
  onRunAll?: () => void;
}

export default function Topbar({
  notebookTitle,
  setNotebookTitle,
  saveStatus,
  saveNotebook,
  onRunAll,
}: TopbarProps) {
  return (
    <header className="h-11 bg-[#0A1628] border-b border-slate-900/80 flex items-center justify-between px-4 z-50 flex-shrink-0">
      {/* Left: title & run all */}
      <div className="flex items-center gap-3 min-w-0">
        {notebookTitle !== undefined ? (
          <>
            <input
              value={notebookTitle}
              onChange={(e) => setNotebookTitle && setNotebookTitle(e.target.value)}
              className="bg-transparent text-slate-200 text-sm font-medium outline-none px-1 py-0.5 rounded hover:bg-slate-800/40 focus:bg-slate-800/40 transition-colors w-44 truncate"
              aria-label="Notebook title"
            />
            {onRunAll && (
              <button
                onClick={onRunAll}
                className="h-7 px-2.5 rounded bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 text-[11px] font-semibold flex items-center gap-1.5 transition-all select-none border border-emerald-500/20 hover:border-emerald-500/40 active:scale-95 cursor-pointer"
                title="Run all code cells in sequence"
              >
                <Play className="h-2.5 w-2.5 fill-emerald-400" />
                <span>Run All</span>
              </button>
            )}
          </>
        ) : (
          <span className="text-slate-200 text-sm font-medium select-none">Projects</span>
        )}
      </div>

      {/* Center: notebook icons */}
      <div className="flex items-center gap-1">
        <button
          className="h-7 w-7 rounded flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
          title="Preview"
        >
          <Eye className="h-3.5 w-3.5" />
        </button>
        <button
          className="h-7 w-7 rounded flex items-center justify-center text-[#00bcd4] hover:bg-slate-800/60 transition-colors"
          title="AI"
        >
          <Sparkles className="h-3.5 w-3.5 fill-current" />
        </button>
      </div>

      {/* Right: save status + share */}
      <div className="flex items-center gap-3">
        {saveStatus && (
          <span className="text-[10px] text-slate-600 font-mono hidden sm:block">{saveStatus}</span>
        )}
        <button
          onClick={saveNotebook}
          className="h-7 w-7 rounded flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
          title="Export / Share"
        >
          <Upload className="h-3.5 w-3.5" />
        </button>
      </div>
    </header>
  );
}
