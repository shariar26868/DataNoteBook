"use client";

import * as React from "react";
import { ArrowUp, ArrowDown, Trash2, Pencil } from "lucide-react";

interface TextCellProps {
  cellId: string;
  source: string;
  index: number;
  onUpdateSource: (id: string, source: string) => void;
  onMoveUp: (idx: number) => void;
  onMoveDown: (idx: number) => void;
  onDelete: (id: string) => void;
}

// Converts a raw text line into styled JSX matching the mockup:
// inline backtick code → green badge, bold via **, italics via *, links starting with /content/ → teal
function renderInline(text: string, key?: string): React.ReactNode {
  // Split on `backtick`, **bold**, *italic*
  const parts: React.ReactNode[] = [];
  let rest = text;
  let k = 0;
  const push = (node: React.ReactNode) => parts.push(<React.Fragment key={k++}>{node}</React.Fragment>);

  while (rest.length) {
    // inline code: `…`
    const codeM = rest.match(/^`([^`]+)`/);
    if (codeM) {
      const inner = codeM[1];
      // If it looks like a file path → teal underline
      const isPath = inner.startsWith("/") || inner.includes(".csv") || inner.includes(".py");
      push(
        <span className={`font-mono text-[11.5px] px-1.5 py-0.5 rounded-md mx-0.5 ${
          isPath
            ? "text-[#00B686] underline underline-offset-2 bg-[#00B686]/[0.08] border border-[#00B686]/20"
            : "text-[#61afef] bg-slate-800/60 border border-slate-700/50"
        }`}>
          {inner}
        </span>
      );
      rest = rest.slice(codeM[0].length);
      continue;
    }
    // bold: **…**
    const boldM = rest.match(/^\*\*([^*]+)\*\*/);
    if (boldM) { push(<strong className="font-semibold text-slate-100">{boldM[1]}</strong>); rest = rest.slice(boldM[0].length); continue; }
    // italic: *…*
    const italM = rest.match(/^\*([^*]+)\*/);
    if (italM) { push(<em className="italic text-slate-300">{italM[1]}</em>); rest = rest.slice(italM[0].length); continue; }
    // plain char
    push(rest[0]);
    rest = rest.slice(1);
  }
  return <>{parts}</>;
}

// Render markdown-lite text (headings, bullets, plain paragraphs)
function renderContent(src: string): React.ReactNode {
  if (!src.trim()) return null;
  const lines = src.split("\n");
  const out: React.ReactNode[] = [];
  let li: string[] = [];

  const flushList = () => {
    if (!li.length) return;
    out.push(
      <ul key={`ul-${out.length}`} className="list-disc list-inside space-y-1 text-slate-300 text-[13.5px] leading-6 ml-1">
        {li.map((item, i) => <li key={i}>{renderInline(item.replace(/^[-*]\s+/, ""))}</li>)}
      </ul>
    );
    li = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const hMatch = line.match(/^(#{1,4})\s+(.+)$/);
    const liMatch = line.match(/^[-*]\s+.+$/);

    if (hMatch) {
      flushList();
      const level = hMatch[1].length;
      const cls = level === 1
        ? "text-xl font-bold text-slate-100 mt-2 mb-1"
        : level === 2
        ? "text-base font-semibold text-slate-200 mt-1 mb-0.5"
        : "text-sm font-semibold text-slate-300 mt-1";
      out.push(<p key={i} className={cls}>{renderInline(hMatch[2])}</p>);
    } else if (liMatch) {
      li.push(line);
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      out.push(
        <p key={i} className="text-slate-300 text-[13.5px] leading-6">
          {renderInline(line)}
        </p>
      );
    }
  }
  flushList();
  return <>{out}</>;
}

export default function TextCell({
  cellId, source, index, onUpdateSource, onMoveUp, onMoveDown, onDelete,
}: TextCellProps) {
  const [editing, setEditing] = React.useState(false);
  const taRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (editing && taRef.current) {
      taRef.current.style.height = "auto";
      taRef.current.style.height = Math.max(80, taRef.current.scrollHeight) + "px";
      taRef.current.focus();
    }
  }, [editing]);

  const syncHeight = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.max(80, ta.scrollHeight) + "px";
  };

  return (
    <div className="group flex items-start gap-3">
      {/* Gutter number */}
      <div className="w-8 flex flex-col items-center pt-1.5 flex-shrink-0">
        <span className="text-[9px] font-mono text-slate-800">[{index + 1}]</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 relative">
        {/* Hover toolbar */}
        <div className="absolute top-0 right-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          <button
            onClick={() => setEditing(true)}
            className="h-5 w-5 rounded flex items-center justify-center text-slate-700 hover:text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <Pencil className="h-3 w-3" />
          </button>
          <button onClick={() => onMoveUp(index)} className="h-5 w-5 rounded flex items-center justify-center text-slate-700 hover:text-slate-300 hover:bg-slate-800 transition-colors">
            <ArrowUp className="h-3 w-3" />
          </button>
          <button onClick={() => onMoveDown(index)} className="h-5 w-5 rounded flex items-center justify-center text-slate-700 hover:text-slate-300 hover:bg-slate-800 transition-colors">
            <ArrowDown className="h-3 w-3" />
          </button>
          <button onClick={() => onDelete(cellId)} className="h-5 w-5 rounded flex items-center justify-center text-slate-700 hover:text-red-400 hover:bg-slate-800 transition-colors">
            <Trash2 className="h-3 w-3" />
          </button>
        </div>

        {editing ? (
          <textarea
            ref={taRef}
            value={source}
            onChange={(e) => { onUpdateSource(cellId, e.target.value); syncHeight(); }}
            onBlur={() => setEditing(false)}
            onKeyDown={(e) => { if (e.key === "Escape") setEditing(false); }}
            className="w-full bg-[#0a0e1a] border border-slate-700/60 rounded-lg text-slate-200 text-[13.5px] leading-6 px-4 py-3 resize-none focus:outline-none focus:border-cyan-500/40 font-mono placeholder:text-slate-700 transition-colors"
            placeholder="Write markdown text here… (use # Heading, **bold**, `code`)"
            spellCheck={false}
          />
        ) : (
          <div
            className="min-h-[28px] px-1 py-1 cursor-text rounded-lg group-hover:bg-slate-900/10 transition-colors space-y-1.5"
            onClick={() => setEditing(true)}
          >
            {source.trim()
              ? renderContent(source)
              : <span className="text-slate-700 text-sm italic">Click to edit text cell…</span>
            }
          </div>
        )}
      </div>
    </div>
  );
}
