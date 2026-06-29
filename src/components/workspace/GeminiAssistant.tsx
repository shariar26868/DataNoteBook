"use client";

import * as React from "react";
import {
  Plus, X, ArrowUp, Sparkles, MoreVertical, ThumbsUp, ThumbsDown,
  ChevronLeft, ChevronRight, Table, Loader2, AlertCircle, RefreshCw,
  Download, Image as ImageIcon
} from "lucide-react";

interface Message {
  role: "user" | "ai";
  text: string;
  code?: string | null;
  truncated?: boolean;
  image?: string | null;
}

interface GeminiAssistantProps {
  messages: Message[];
  chatInput: string;
  setChatInput: (val: string) => void;
  chatLoading: boolean;
  sendChat: (text: string, image?: string | null) => void;
  pendingCode: string | null;
  setPendingCode: (val: string | null) => void;
  addCodeCell: (code: string, runImmediately: boolean) => void;
  onClose: () => void;
  handleUpload: (file: File, fromSidebar: boolean) => void;
  handleSelectDataset?: (filename: string, fileId: string) => void;
  sessionActive: boolean;
  sessionFilename?: string;
  onUnloadDataset?: () => void;
  triggerBanner: (msg: string, type?: "err" | "ok" | "") => void;
  activeTab: "gemini" | "preview";
  setActiveTab: (tab: "gemini" | "preview") => void;
  showGeminiTab: boolean;
  showPreviewTab: boolean;
  onCloseGeminiTab: () => void;
  onClosePreviewTab: () => void;
}

function formatText(text: string): React.ReactNode {
  // Split on `code` spans
  const parts = text.split(/`([^`]+)`/);
  return parts.map((p, i) =>
    i % 2 === 1 ? (
      <code key={i} className="px-1.5 py-0.5 bg-emerald-950/50 text-emerald-400 rounded text-[10.5px] font-mono border border-emerald-900/30">
        {p}
      </code>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

function TruncatedWarning() {
  return (
    <div className="flex items-start gap-2 px-3 py-2 mb-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px]">
      <span className="text-base leading-none mt-0.5">⚠️</span>
      <div>
        <p className="font-semibold">Response may be incomplete</p>
        <p className="text-amber-400/70 mt-0.5">
          The AI response was cut short. The code below may be partial — please review before running, or try rephrasing your question.
        </p>
      </div>
    </div>
  );
}

export default function GeminiAssistant({
  messages, chatInput, setChatInput, chatLoading, sendChat,
  pendingCode, setPendingCode, addCodeCell,
  onClose, handleUpload, handleSelectDataset, sessionActive, sessionFilename, onUnloadDataset, triggerBanner,
  activeTab, setActiveTab,
  showGeminiTab, showPreviewTab, onCloseGeminiTab, onClosePreviewTab,
}: GeminiAssistantProps) {
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const taRef = React.useRef<HTMLTextAreaElement>(null);

  const [attachedImage, setAttachedImage] = React.useState<string | null>(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const imageInputRef = React.useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    // 1. Check for files dragged from the sidebar (TOC JSON format)
    const rawData = e.dataTransfer.getData("application/json");
    if (rawData) {
      try {
        const data = JSON.parse(rawData);
        if (data.type === "file" && data.id && data.name) {
          handleSelectDataset?.(data.name, data.id);
          triggerBanner(`Switching to dataset: ${data.name}…`, "ok");
          return;
        }
      } catch (_) {}
    }

    // 2. Check for local files dropped
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      const isImg = file.type.startsWith("image/");
      
      if (isImg) {
        const reader = new FileReader();
        reader.onload = (evt) => {
          if (evt.target?.result) {
            setAttachedImage(evt.target.result as string);
            triggerBanner("Attached image for analysis", "ok");
          }
        };
        reader.readAsDataURL(file);
      } else {
        // Dataset file
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (['.csv', '.xlsx', '.xls'].includes(ext)) {
          triggerBanner(`Uploading and analyzing local dataset: ${file.name}…`);
          handleUpload(file, true);
        } else {
          triggerBanner("Unsupported file type. Please drop images or .csv/.xlsx datasets.", "err");
        }
      }
    }
  };

  // Preview data state
  const [previewData, setPreviewData] = React.useState<{
    columns: string[];
    rows: Record<string, any>[];
    totalRows: number;
    filename: string;
  } | null>(null);
  const [previewPage, setPreviewPage] = React.useState(1);
  const [previewLoading, setPreviewLoading] = React.useState(false);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [previewSessionExpired, setPreviewSessionExpired] = React.useState(false);
  const [downloading, setDownloading] = React.useState(false);

  const handleDownloadCleaned = async () => {
    if (downloading) return;
    setDownloading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch("/api/upload/download", {
        method: "POST",
        headers: {
          ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        },
        credentials: "include",
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Failed to download cleaned dataset" }));
        throw new Error(errData.detail || "Failed to download cleaned dataset");
      }
      
      const contentDisposition = res.headers.get("Content-Disposition");
      let downloadFilename = `cleaned_${sessionFilename || "dataset.csv"}`;
      if (contentDisposition) {
        const matches = /filename="([^"]+)"/.exec(contentDisposition);
        if (matches && matches[1]) {
          downloadFilename = matches[1];
        }
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = downloadFilename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      triggerBanner("Cleaned dataset downloaded successfully and saved to Azure Vault", "ok");
    } catch (err: any) {
      triggerBanner(err.message || "Download failed", "err");
    } finally {
      setDownloading(false);
    }
  };

  const pageSize = 50;

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  const handleSend = () => {
    if (!chatInput.trim() && !attachedImage) return;
    sendChat(chatInput, attachedImage);
    setChatInput("");
    setAttachedImage(null);
    if (taRef.current) taRef.current.style.height = "auto";
  };

  // Load preview data
  const loadPreview = React.useCallback(async (page: number) => {
    if (!sessionActive) {
      setPreviewData(null);
      return;
    }
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewSessionExpired(false);
    try {
      const res = await fetch(`/api/upload/preview?page=${page}&page_size=${pageSize}`, {
        credentials: "include",
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Failed to load preview" }));
        // 401 = no session cookie; 404 = session expired/not found
        if (res.status === 401 || res.status === 404) {
          setPreviewSessionExpired(true);
          return;
        }
        throw new Error(errData.detail || "Failed to load preview");
      }
      const data = await res.json();
      setPreviewSessionExpired(false);
      setPreviewData({
        columns: data.columns || [],
        rows: data.rows || [],
        totalRows: data.total_rows || 0,
        filename: data.filename || "",
      });
    } catch (err: any) {
      setPreviewError(err.message || "An error occurred");
    } finally {
      setPreviewLoading(false);
    }
  }, [sessionActive]);

  // Reset page and reload when dataset filename changes
  React.useEffect(() => {
    setPreviewPage(1);
    if (activeTab === "preview" && sessionActive && sessionFilename) {
      loadPreview(1);
    } else {
      setPreviewData(null);
    }
  }, [sessionFilename, activeTab, sessionActive, loadPreview]);

  // Trigger preview loading for pages greater than 1
  React.useEffect(() => {
    if (activeTab === "preview" && sessionActive && previewPage > 1) {
      loadPreview(previewPage);
    }
  }, [activeTab, sessionActive, previewPage, loadPreview]);

  return (
    <aside 
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative bg-[#0A1628] border-l border-slate-900/80 flex flex-col overflow-hidden flex-shrink-0 z-30 transition-all duration-300 ${
        activeTab === "preview" ? "w-[550px]" : "w-[300px]"
      }`}
    >
      {isDragging && (
        <div className="absolute inset-0 bg-[#0A1628]/90 border-2 border-dashed border-emerald-500/40 flex flex-col items-center justify-center gap-3 z-50 pointer-events-none">
          <div className="h-12 w-12 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 text-emerald-400">
            <ArrowUp className="h-6 w-6 animate-bounce" />
          </div>
          <p className="text-xs font-medium text-slate-300">
            Drop file or image here to analyze
          </p>
        </div>
      )}
      {/* ── Header ── */}
      <div className="h-11 border-b border-slate-900/80 flex items-center justify-between px-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold text-slate-200 leading-none">Gemini</span>
        </div>
        <div className="flex items-center gap-0.5">
          <button className="h-6 w-6 rounded flex items-center justify-center text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors">
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button className="h-6 w-6 rounded flex items-center justify-center text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors">
            <MoreVertical className="h-3.5 w-3.5" />
          </button>
          <button onClick={onClose} className="h-6 w-6 rounded flex items-center justify-center text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* ── Tabs Bar ── */}
      {(showGeminiTab || showPreviewTab) && (
        <div className="flex border-b border-slate-900/80 bg-slate-950/20 text-[11.5px] flex-shrink-0">
          {showGeminiTab && (
            <button
              onClick={() => setActiveTab("gemini")}
              className={`flex-1 py-2 px-3 text-center font-medium border-b-2 transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                activeTab === "gemini"
                  ? "border-emerald-500 text-emerald-400 bg-slate-900/20"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>Gemini</span>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseGeminiTab();
                }}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
                title="Close Gemini tab"
              >
                <X className="h-2.5 w-2.5" />
              </span>
            </button>
          )}
          {showPreviewTab && (
            <button
              onClick={() => setActiveTab("preview")}
              className={`flex-1 py-2 px-3 text-center font-medium border-b-2 transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                activeTab === "preview"
                  ? "border-emerald-500 text-emerald-400 bg-slate-900/20"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>Preview</span>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  onClosePreviewTab();
                }}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
                title="Close Preview tab"
              >
                <X className="h-2.5 w-2.5" />
              </span>
            </button>
          )}
        </div>
      )}

      {/* ── Chat Tab Content ── */}
      {activeTab === "gemini" && (
        <>
          {/* ── Messages ── */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-4">
            {messages.length === 0 && (
              <div className="flex-1 flex flex-col items-center justify-center py-16 text-center gap-2">
                <div className="h-9 w-9 rounded-full bg-slate-900/60 border border-slate-800 flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-amber-500/60" />
                </div>
                <p className="text-slate-600 text-xs leading-relaxed max-w-[200px]">
                  Ask Gemini to analyze, visualize, or transform your dataset.
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className="flex gap-2 items-start">
                {msg.role === "ai" ? (
                  <>
                    {/* AI avatar */}
                    <div className="h-6 w-6 rounded-full bg-slate-900/70 border border-slate-800 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Sparkles className="h-3 w-3 text-amber-400 fill-amber-400" />
                    </div>
                    {/* AI bubble */}
                    <div className="flex-1 min-w-0">
                      <div className="bg-[#0d1520] border border-slate-800/80 rounded-xl rounded-tl-sm p-3 text-[12px] text-slate-300 leading-relaxed">
                        {msg.truncated && <TruncatedWarning />}
                        {formatText(msg.text)}
                      </div>
                      {/* Feedback row */}
                      <div className="flex items-center gap-2 mt-1.5 pl-1">
                        <button className="text-slate-700 hover:text-slate-400 transition-colors">
                          <ThumbsUp className="h-3 w-3" />
                        </button>
                        <button className="text-slate-700 hover:text-slate-400 transition-colors">
                          <ThumbsDown className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex justify-end gap-2 items-start">
                    {/* User bubble */}
                    <div className="bg-[#112240] border border-slate-800/60 rounded-xl rounded-tr-sm p-3 text-[12px] text-slate-200 leading-relaxed max-w-[85%] flex flex-col gap-2">
                      {msg.image && (
                        <img 
                          src={msg.image} 
                          alt="Attached snippet" 
                          className="max-w-full max-h-40 rounded border border-slate-700/50 object-contain bg-slate-950/20" 
                        />
                      )}
                      {msg.text && <div>{msg.text}</div>}
                    </div>
                    {/* User avatar */}
                    <div className="h-6 w-6 rounded-full bg-pink-600 flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0 mt-0.5 border border-pink-700/40">
                      M
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Loading indicator */}
            {chatLoading && (
              <div className="flex gap-2 items-start">
                <div className="h-6 w-6 rounded-full bg-slate-900/70 border border-slate-800 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Sparkles className="h-3 w-3 text-amber-400 animate-pulse" />
                </div>
                <div className="bg-[#0d1520] border border-slate-800/80 rounded-xl rounded-tl-sm px-3 py-2.5 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-600 animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-600 animate-bounce" style={{ animationDelay: "120ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-600 animate-bounce" style={{ animationDelay: "240ms" }} />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* ── Pending code action bar ── */}
          {pendingCode && (
            <div className="px-4 py-2 bg-[#0A1628] flex items-center gap-4 flex-shrink-0 select-none">
              <button
                onClick={() => { addCodeCell(pendingCode, true); setPendingCode(null); }}
                className="text-[#00B686] hover:text-emerald-400 text-[11px] font-semibold transition-all cursor-pointer flex items-center gap-1"
              >
                ▷ Accept & Run
              </button>
              <button
                onClick={() => { addCodeCell(pendingCode, false); setPendingCode(null); }}
                className="text-[#00B686] hover:text-emerald-400 text-[11px] font-semibold transition-all cursor-pointer flex items-center gap-1"
              >
                ✓ Accept
              </button>
              <button
                onClick={() => setPendingCode(null)}
                className="text-[#00B686] hover:text-emerald-400 text-[11px] font-semibold transition-all cursor-pointer flex items-center gap-1"
              >
                ✕ Cancel
              </button>
            </div>
          )}

          {/* ── Input box ── */}
          <div className="px-3 py-3 border-t border-slate-900/80 flex-shrink-0">
            <input
              type="file"
              ref={fileInputRef}
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0], true)}
            />
            <input
              type="file"
              ref={imageInputRef}
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  const reader = new FileReader();
                  reader.onload = (evt) => {
                    if (evt.target?.result) {
                      setAttachedImage(evt.target.result as string);
                    }
                  };
                  reader.readAsDataURL(file);
                  e.target.value = "";
                }
              }}
            />
            <div className="bg-[#00081a] border border-slate-800 rounded-2xl px-3 pt-3 pb-2.5 flex flex-col gap-2 focus-within:border-cyan-500/30 focus-within:shadow-[0_0_0_3px_rgba(6,182,212,0.04)] transition-all">
              {sessionActive && sessionFilename && (
                <div className="flex items-center gap-1 px-1.5 py-0.5 bg-emerald-500/10 border border-emerald-500/20 rounded text-emerald-400 text-[10.5px] w-fit select-none">
                  <span className="font-mono font-medium">{sessionFilename}</span>
                  {onUnloadDataset && (
                    <button
                      onClick={onUnloadDataset}
                      className="text-emerald-500 hover:text-emerald-300 transition-colors cursor-pointer ml-1"
                      title="Unload dataset"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  )}
                </div>
              )}
              {attachedImage && (
                <div className="relative w-16 h-16 rounded border border-slate-800 bg-slate-950/40 p-0.5 select-none mt-1 group">
                  <img src={attachedImage} alt="preview" className="w-full h-full object-cover rounded" />
                  <button
                    onClick={() => setAttachedImage(null)}
                    className="absolute -top-1.5 -right-1.5 bg-red-600 hover:bg-red-500 text-white rounded-full p-0.5 shadow-sm transition-colors cursor-pointer"
                    title="Remove image"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </div>
              )}
              <textarea
                ref={taRef}
                value={chatInput}
                onChange={(e) => {
                  setChatInput(e.target.value);
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = Math.min(el.scrollHeight, 120) + "px";
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="What can I help you build?"
                rows={1}
                className="w-full bg-transparent resize-none text-[12.5px] text-slate-200 leading-relaxed outline-none placeholder:text-slate-600 min-h-[22px] max-h-28"
              />
              <div className="flex items-center justify-between border-t border-slate-800/50 pt-2">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="p-1 text-slate-600 hover:text-slate-300 hover:bg-slate-800/60 rounded-md transition-all"
                    title="Upload dataset"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => imageInputRef.current?.click()}
                    className="p-1 text-slate-600 hover:text-slate-300 hover:bg-slate-800/60 rounded-md transition-all"
                    title="Attach image"
                  >
                    <ImageIcon className="h-3.5 w-3.5" />
                  </button>
                  {sessionActive && (
                    <button
                      onClick={handleDownloadCleaned}
                      disabled={downloading}
                      className="p-1 text-slate-600 hover:text-emerald-400 hover:bg-slate-800/60 rounded-md transition-all flex items-center justify-center"
                      title="Download Cleaned Dataset"
                    >
                      {downloading ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Download className="h-3.5 w-3.5" />
                      )}
                    </button>
                  )}
                </div>
                <button
                  disabled={chatLoading || (!chatInput.trim() && !attachedImage)}
                  onClick={handleSend}
                  className={`h-7 w-7 rounded-full flex items-center justify-center transition-all ${
                    (chatInput.trim() || attachedImage) && !chatLoading
                      ? "bg-emerald-500 hover:bg-emerald-400 text-slate-950 cursor-pointer shadow-[0_0_10px_rgba(16,185,129,0.25)]"
                      : "bg-slate-800 text-slate-600 cursor-not-allowed opacity-40"
                  }`}
                >
                  <ArrowUp className="h-3.5 w-3.5 stroke-[2.5]" />
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Preview Tab Content ── */}
      {activeTab === "preview" && (
        <div className="flex-1 flex flex-col overflow-hidden min-h-0 bg-[#071120]">
          {!sessionActive ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
              <Table className="h-10 w-10 text-slate-700 stroke-[1.5]" />
              <div>
                <h3 className="text-[13px] font-semibold text-slate-300">No Dataset Uploaded</h3>
                <p className="text-[11px] text-slate-500 mt-1 max-w-[220px] mx-auto">
                  Please upload a dataset (.csv or .xlsx) from the Gemini chat or sidebar first.
                </p>
              </div>
            </div>
          ) : previewLoading && !previewData ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
              <span className="text-xs">Loading dataset preview...</span>
            </div>
          ) : previewSessionExpired ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
              <AlertCircle className="h-8 w-8 text-amber-500" />
              <div>
                <h3 className="text-[13px] font-semibold text-amber-400">Session Expired</h3>
                <p className="text-[11px] text-slate-500 mt-2 max-w-[220px] mx-auto">
                  Your dataset session has expired. Please re-upload your file to restore the preview.
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-3 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-600/40 text-emerald-400 rounded text-xs flex items-center gap-1.5 mx-auto transition-colors"
                >
                  <Plus className="h-3 w-3" /> Re-upload Dataset
                </button>
              </div>
            </div>
          ) : previewError ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
              <AlertCircle className="h-8 w-8 text-red-500" />
              <div>
                <h3 className="text-[13px] font-semibold text-red-400">Failed to Load Preview</h3>
                <p className="text-[11px] text-slate-500 mt-1">{previewError}</p>
                <button
                  onClick={() => loadPreview(previewPage)}
                  className="mt-3 px-3 py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-200 rounded text-xs flex items-center gap-1.5 mx-auto transition-colors"
                >
                  <RefreshCw className="h-3 w-3" /> Retry
                </button>
              </div>
            </div>
          ) : previewData ? (
            <>
              {/* Dataset Info header */}
              <div className="px-3 py-2 border-b border-slate-900 bg-slate-950/30 flex items-center justify-between text-[11px] flex-shrink-0">
                <span className="font-semibold text-slate-300 truncate max-w-[250px]" title={previewData.filename}>
                  {previewData.filename}
                </span>
                <span className="text-slate-500 text-[10.5px]">
                  Total: {previewData.totalRows} rows · {previewData.columns.length} columns
                </span>
              </div>

              {/* Table wrapper */}
              <div className="flex-1 overflow-auto custom-scrollbar font-mono text-[10px] min-h-0 bg-[#050B14]">
                <table className="min-w-full w-max border-collapse border-spacing-0 text-left">
                  <thead>
                    <tr className="bg-[#091220] border-b border-slate-900 sticky top-0 z-10 shadow-sm">
                      <th className="px-2.5 py-1.5 text-slate-500 font-semibold border-r border-slate-900 w-12 text-center">
                        #
                      </th>
                      {previewData.columns.map((col) => (
                        <th
                          key={col}
                          className="px-2.5 py-1.5 text-slate-400 font-medium border-r border-slate-900 min-w-[120px] max-w-[240px] truncate whitespace-nowrap"
                          title={col}
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.rows.length === 0 ? (
                      <tr>
                        <td
                          colSpan={previewData.columns.length + 1}
                          className="text-center py-8 text-slate-500"
                        >
                          No data rows found.
                        </td>
                      </tr>
                    ) : (
                      previewData.rows.map((row, idx) => {
                        const rowNum = (previewPage - 1) * pageSize + idx + 1;
                        return (
                          <tr
                            key={idx}
                            className="border-b border-slate-900/50 hover:bg-slate-900/40 transition-colors"
                          >
                            <td className="px-2.5 py-1 text-slate-600 border-r border-slate-900 text-center select-none bg-slate-950/10">
                              {rowNum}
                            </td>
                            {previewData.columns.map((col) => {
                              const val = row[col];
                              const displayVal =
                                val === null || val === undefined
                                  ? ""
                                  : typeof val === "object"
                                  ? JSON.stringify(val)
                                  : String(val);
                              return (
                                <td
                                  key={col}
                                  className="px-2.5 py-1 text-slate-300 border-r border-slate-900/30 truncate max-w-[240px] whitespace-nowrap"
                                  title={displayVal}
                                >
                                  {displayVal}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination controls footer */}
              <div className="h-10 border-t border-slate-900/80 px-3 flex items-center justify-start gap-4 bg-slate-950/40 flex-shrink-0 text-[11px] text-slate-400">
                <div className="flex items-center gap-1.5">
                  <span>
                    Showing {Math.min(previewData.totalRows, (previewPage - 1) * pageSize + 1)}–
                    {Math.min(previewData.totalRows, previewPage * pageSize)} of {previewData.totalRows}
                  </span>
                  {previewLoading && (
                    <Loader2 className="h-3 w-3 animate-spin text-emerald-500" />
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-slate-600 mr-1 select-none">|</span>
                  <button
                    disabled={previewPage <= 1 || previewLoading}
                    onClick={() => setPreviewPage((p) => p - 1)}
                    className="h-6 w-6 rounded border border-slate-800 flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-all"
                    title="Previous page"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <span className="px-1.5 text-slate-300 text-[10.5px]">
                    Page {previewPage} / {Math.max(1, Math.ceil(previewData.totalRows / pageSize))}
                  </span>
                  <button
                    disabled={
                      previewPage >= Math.ceil(previewData.totalRows / pageSize) ||
                      previewLoading
                    }
                    onClick={() => setPreviewPage((p) => p + 1)}
                    className="h-6 w-6 rounded border border-slate-800 flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-all"
                    title="Next page"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}
    </aside>
  );
}
