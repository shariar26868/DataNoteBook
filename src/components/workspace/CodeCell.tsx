"use client";

import * as React from "react";
import {
  Play, ArrowUp, ArrowDown, Trash2, RefreshCw,
  Copy, Check
} from "lucide-react";

// ── Token-level Python syntax highlighter ────────────────────────────────────
const KW = /\b(import|from|as|def|class|return|if|elif|else|for|in|while|try|except|with|pass|break|continue|and|or|not|True|False|None|lambda|yield|assert|del|global|nonlocal|raise)\b/;
const BUILTINS = /\b(print|len|range|type|str|int|float|list|dict|set|tuple|zip|map|filter|enumerate|sorted|reversed|open|round|abs|sum|min|max|any|all|isinstance|hasattr|getattr|setattr)\b/;

function tokenizeLine(line: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let rest = line;
  let k = 0;

  // leading whitespace
  const lead = rest.match(/^(\s+)/);
  if (lead) { out.push(<span key={k++}>{lead[1]}</span>); rest = rest.slice(lead[1].length); }

  // comment
  if (rest.startsWith("#")) {
    out.push(<span key={k++} className="text-slate-500 italic">{rest}</span>);
    return out;
  }

  while (rest.length) {
    // string
    const str = rest.match(/^("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/);
    if (str) { out.push(<span key={k++} className="text-emerald-400">{str[1]}</span>); rest = rest.slice(str[1].length); continue; }
    // number
    const num = rest.match(/^(\d+(?:\.\d+)?)/);
    if (num) { out.push(<span key={k++} className="text-amber-400">{num[1]}</span>); rest = rest.slice(num[1].length); continue; }
    // f-string opener
    const fstr = rest.match(/^(f["'])/);
    if (fstr) { out.push(<span key={k++} className="text-emerald-400">{fstr[1]}</span>); rest = rest.slice(fstr[1].length); continue; }
    // identifier / keyword
    const word = rest.match(/^([A-Za-z_]\w*)/);
    if (word) {
      const w = word[1];
      let cls = "text-blue-200";
      if (KW.test(w)) cls = "text-[#c678dd] font-medium";
      else if (BUILTINS.test(w)) cls = "text-[#56b6c2]";
      else if (/^[A-Z]/.test(w)) cls = "text-yellow-300";
      out.push(<span key={k++} className={cls}>{w}</span>);
      rest = rest.slice(w.length); continue;
    }
    // operators / punctuation
    const op = rest.match(/^([+\-*/=<>!&|^~%@(),\[\]{};:.\s]+)/);
    if (op) { out.push(<span key={k++} className="text-slate-400">{op[1]}</span>); rest = rest.slice(op[1].length); continue; }
    out.push(<span key={k++}>{rest[0]}</span>);
    rest = rest.slice(1);
  }
  return out;
}

// ── Output renderer ──────────────────────────────────────────────────────────
interface OutputProps {
  output: string | null | undefined;
  outputType: "text" | "image" | "table" | null | undefined;
}
function CellOutput({ output, outputType }: OutputProps) {
  if (output === null || output === undefined) return null;

  // Handle JSON array of multiple outputs (stdout, images, tables, etc.)
  if (output.startsWith("[")) {
    try {
      const list = JSON.parse(output);
      if (Array.isArray(list)) {
        return (
          <div className="mt-2 flex flex-col gap-3">
            {list.map((item, idx) => {
              if (item.type === "image") {
                return (
                  <div key={idx} className="rounded-lg overflow-hidden border border-slate-800">
                    <img src={item.data} alt="output" className="max-w-full" />
                  </div>
                );
              }
              if (item.type === "table") {
                let rows: string[][] = [];
                try {
                  const parsed = JSON.parse(item.data);
                  if (Array.isArray(parsed) && parsed.length > 0) {
                    const keys = Object.keys(parsed[0]);
                    rows = [keys, ...parsed.map((r: any) => keys.map((k) => String(r[k] ?? "")))];
                  }
                } catch { rows = [[item.data]]; }
                return (
                  <div key={idx} className="overflow-x-auto rounded-lg border border-slate-800">
                    <table className="text-[11px] font-mono min-w-full">
                      <thead>
                        <tr>{rows[0]?.map((h, i) => (
                          <th key={i} className="px-3 py-1.5 text-left text-cyan-400 font-bold bg-slate-900/60 border-b border-slate-800">{h}</th>
                        ))}</tr>
                      </thead>
                      <tbody>
                        {rows.slice(1, 101).map((row, ri) => (
                          <tr key={ri} className={ri % 2 === 0 ? "" : "bg-slate-900/20"}>
                            {row.map((cell, ci) => <td key={ci} className="px-3 py-1 text-slate-300 border-b border-slate-900/40">{cell}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {rows.length > 101 && <p className="px-3 py-1.5 text-[10px] text-slate-600">… and {rows.length - 101} more rows</p>}
                  </div>
                );
              }
              // Text or error
              const isErr = item.data.includes("❌");
              return (
                <pre key={idx} className={`px-4 py-3 rounded-lg text-[11.5px] font-mono leading-relaxed whitespace-pre-wrap overflow-x-auto border ${
                  isErr
                    ? "text-red-400 bg-red-500/[0.04] border-red-500/15"
                    : "text-slate-300 bg-[#0b0f1a] border-slate-800/60"
                }`}>
                  {item.data}
                </pre>
              );
            })}
          </div>
        );
      }
    } catch {}
  }

  // Fallback to original single output rendering:
  if (outputType === "image") {
    return (
      <div className="mt-2 rounded-lg overflow-hidden border border-slate-800">
        <img src={output} alt="output" className="max-w-full" />
      </div>
    );
  }

  if (outputType === "table") {
    let rows: string[][] = [];
    try {
      const parsed = JSON.parse(output);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const keys = Object.keys(parsed[0]);
        rows = [keys, ...parsed.map((r: any) => keys.map((k) => String(r[k] ?? "")))];
      }
    } catch { rows = [[output]]; }
    return (
      <div className="mt-2 overflow-x-auto rounded-lg border border-slate-800">
        <table className="text-[11px] font-mono min-w-full">
          <thead>
            <tr>{rows[0]?.map((h, i) => (
              <th key={i} className="px-3 py-1.5 text-left text-cyan-400 font-bold bg-slate-900/60 border-b border-slate-800">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.slice(1, 101).map((row, ri) => (
              <tr key={ri} className={ri % 2 === 0 ? "" : "bg-slate-900/20"}>
                {row.map((cell, ci) => <td key={ci} className="px-3 py-1 text-slate-300 border-b border-slate-900/40">{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > 101 && <p className="px-3 py-1.5 text-[10px] text-slate-600">… and {rows.length - 101} more rows</p>}
      </div>
    );
  }

  const isErr = output.includes("❌");
  return (
    <pre className={`mt-2 px-4 py-3 rounded-lg text-[11.5px] font-mono leading-relaxed whitespace-pre-wrap overflow-x-auto border ${
      isErr
        ? "text-red-400 bg-red-500/[0.04] border-red-500/15"
        : "text-slate-300 bg-[#0b0f1a] border-slate-800/60"
    }`}>
      {output}
    </pre>
  );
}

// ── Main CodeCell ─────────────────────────────────────────────────────────────
interface CodeCellProps {
  cellId: string;
  source: string;
  output: string | null | undefined;
  outputType: "text" | "image" | "table" | null | undefined;
  index: number;
  runningCellId: string | null;
  streamExec: (id: string, code: string) => void;
  onUpdateSource: (id: string, source: string) => void;
  onMoveUp: (idx: number) => void;
  onMoveDown: (idx: number) => void;
  onDelete: (id: string) => void;
}

export default function CodeCell({
  cellId, source, output, outputType, index,
  runningCellId, streamExec, onUpdateSource, onMoveUp, onMoveDown, onDelete,
}: CodeCellProps) {
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const [copied, setCopied] = React.useState(false);
  const [focused, setFocused] = React.useState(false);
  const isRunning = runningCellId === cellId;

  const lines = source.split("\n");

  const syncHeight = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "0";
    ta.style.height = Math.max(72, ta.scrollHeight) + "px";
  };

  React.useEffect(() => { syncHeight(); }, [source]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const ta = e.currentTarget;
    if (e.key === "Tab") {
      e.preventDefault();
      const s = ta.selectionStart, en = ta.selectionEnd;
      const next = source.slice(0, s) + "    " + source.slice(en);
      onUpdateSource(cellId, next);
      setTimeout(() => { ta.selectionStart = ta.selectionEnd = s + 4; }, 0);
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      streamExec(cellId, source);
    }
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      const pos = ta.selectionStart;
      const before = source.slice(0, pos);
      const lastNl = before.lastIndexOf("\n");
      const curLine = lastNl === -1 ? before : before.slice(lastNl + 1);
      const indent = curLine.match(/^[ \t]*/)?.[0] ?? "";
      const extra = curLine.trimEnd().endsWith(":") ? "    " : "";
      const insert = "\n" + indent + extra;
      const next = source.slice(0, pos) + insert + source.slice(ta.selectionEnd);
      onUpdateSource(cellId, next);
      setTimeout(() => { ta.selectionStart = ta.selectionEnd = pos + insert.length; }, 0);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(source);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group flex items-start gap-3">
      {/* Gutter: run button + counter */}
      <div className="w-8 flex flex-col items-center pt-1.5 flex-shrink-0 gap-1">
        <button
          onClick={() => !isRunning && streamExec(cellId, source)}
          title="Run (Ctrl+Enter)"
          className={`h-6 w-6 rounded-full border flex items-center justify-center transition-all ${
            isRunning
              ? "border-amber-500/50 text-amber-400 bg-amber-950/20 animate-spin"
              : "border-slate-700 text-slate-500 hover:border-emerald-500 hover:text-emerald-400 hover:bg-emerald-950/20"
          }`}
        >
          {isRunning ? <RefreshCw className="h-3 w-3" /> : <Play className="h-3 w-3 fill-current" />}
        </button>
        <span className="text-[9px] font-mono text-slate-700">
          [{isRunning ? "●" : index + 1}]
        </span>
      </div>

      {/* Editor container */}
      <div className="flex-1 min-w-0">
        <div className={`relative rounded-lg overflow-hidden border transition-all ${
          focused ? "border-[#eab308] shadow-[0_0_0_1px_rgba(234,179,8,0.15)]" : "border-[#eab308]/60"
        } bg-[#0d1117]`}>

          {/* ✦ Q2 badge */}
          <div className="absolute top-0 left-0 px-2 py-0.5 bg-[#eab308] text-slate-950 rounded-br text-[9px] font-extrabold tracking-wide select-none z-10">
            ✦ Q2
          </div>

          {/* Hover controls */}
          <div className="absolute top-1 right-1 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
            <button onClick={handleCopy} title="Copy" className="h-5 w-5 rounded flex items-center justify-center text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors">
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            </button>
            <button onClick={() => onMoveUp(index)} title="Move up" className="h-5 w-5 rounded flex items-center justify-center text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors">
              <ArrowUp className="h-3 w-3" />
            </button>
            <button onClick={() => onMoveDown(index)} title="Move down" className="h-5 w-5 rounded flex items-center justify-center text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors">
              <ArrowDown className="h-3 w-3" />
            </button>
            <button onClick={() => onDelete(cellId)} title="Delete" className="h-5 w-5 rounded flex items-center justify-center text-slate-600 hover:text-red-400 hover:bg-slate-800 transition-colors">
              <Trash2 className="h-3 w-3" />
            </button>
          </div>

          {/* Code editor with line numbers */}
          <div className="relative flex pt-6">
            {/* Line numbers */}
            <div className="select-none flex flex-col items-end pr-3 pl-3 border-r border-slate-800/60 bg-[#0a0e15] pt-[3px] min-w-[36px]">
              {lines.map((_, i) => (
                <div key={i} className="text-[10px] font-mono text-slate-700 leading-5 h-5">
                  {i + 1}
                </div>
              ))}
            </div>

            {/* Textarea and Highlight Overlay Wrapper */}
            <div className="relative flex-1 min-w-0 min-h-[72px]">
              {/* Textarea (sits on top, captures inputs, text is transparent but caret is visible) */}
              <textarea
                ref={textareaRef}
                value={source}
                onChange={(e) => { onUpdateSource(cellId, e.target.value); syncHeight(); }}
                onKeyDown={handleKeyDown}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                spellCheck={false}
                placeholder="# Write Python code here…"
                className="w-full bg-transparent text-transparent caret-cyan-400 font-mono text-[12.5px] leading-5 pl-3 pr-3 pt-[3px] pb-3 resize-none focus:outline-none z-10 min-h-[72px] overflow-hidden block"
                style={{ caretColor: "#22d3ee" }}
              />

              {/* Syntax-highlighted overlay (behind/underneath the textarea) */}
              <pre className="absolute inset-0 font-mono text-[12.5px] leading-5 pl-3 pr-3 pt-[3px] pb-3 pointer-events-none select-none whitespace-pre-wrap break-words overflow-hidden">
                {lines.map((line, i) => (
                  <div key={i} className="h-5">{tokenizeLine(line)}</div>
                ))}
              </pre>
            </div>
          </div>

          {/* Running progress bar */}
          {isRunning && (
            <div className="h-0.5 w-full bg-slate-800 overflow-hidden">
              <div className="h-full w-1/3 bg-gradient-to-r from-transparent via-emerald-500 to-transparent"
                style={{ animation: "shimmer 1.2s ease-in-out infinite" }} />
            </div>
          )}
        </div>

        {/* Output */}
        <CellOutput output={output} outputType={outputType} />
      </div>

      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-200%); }
          100% { transform: translateX(600%); }
        }
      `}</style>
    </div>
  );
}
