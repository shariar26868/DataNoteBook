"use client";

import * as React from "react";
import { 
  Upload, 
  FolderOpen, 
  Eye, 
  RefreshCw, 
  X, 
  FileSpreadsheet, 
  Folder, 
  ChevronRight, 
  ChevronDown,
  FolderClosed,
  FolderPlus
} from "lucide-react";

interface Resource {
  id: string;
  name: string;
  type: "folder" | "file";
  parent: any;
}

interface TableOfContentsProps {
  projectResources: Resource[];
  projectName: string | null;
  handleUpload: (file: File, fromSidebar: boolean, folderId?: string | null) => void;
  onClose: () => void;
  onFileDoubleClick: (filename: string, fileId: string) => void;
  onRefresh?: () => void;
  onCreateFolderClick?: () => void;
  selectedFolderId?: string | null;
  onSelectFolder?: (folderId: string) => void;
}

export default function TableOfContents({ 
  projectResources, 
  projectName, 
  handleUpload, 
  onClose, 
  onFileDoubleClick,
  onRefresh,
  onCreateFolderClick,
  selectedFolderId = null,
  onSelectFolder
}: TableOfContentsProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [expandedFolders, setExpandedFolders] = React.useState<Record<string, boolean>>({});
  const [uploadTargetFolderId, setUploadTargetFolderId] = React.useState<string | null>(null);

  const toggleFolder = (folderId: string) => {
    setExpandedFolders(prev => ({
      ...prev,
      [folderId]: !prev[folderId]
    }));
  };

  // Helper to extract parent ID robustly (whether string, object, or null)
  const getParentId = (parent: any): string | null => {
    if (!parent) return null;
    if (typeof parent === "object") return parent.id || null;
    return parent;
  };

  // Group resources
  const rootFolders = React.useMemo(() => {
    return projectResources.filter(r => r.type === "folder" && !getParentId(r.parent));
  }, [projectResources]);

  const rootFiles = React.useMemo(() => {
    return projectResources.filter(r => r.type === "file" && !getParentId(r.parent));
  }, [projectResources]);

  const getFilesForFolder = (folderId: string) => {
    return projectResources.filter(r => r.type === "file" && getParentId(r.parent) === folderId);
  };

  return (
    <aside className="w-56 bg-[#0A1628] border-r border-[#00081A] flex flex-col overflow-hidden flex-shrink-0 z-30">

      {/* ── Header ── */}
      <div className="h-11 flex items-center justify-between px-3 border-b border-[#00081A] flex-shrink-0">
        <span className="text-[11px] font-semibold text-slate-300 tracking-wide uppercase select-none">
          Table of contents
        </span>
        <button
          onClick={onClose}
          className="h-5 w-5 rounded flex items-center justify-center text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* ── Toolbar ── */}
      <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-slate-900/60 flex-shrink-0">
        <input
          type="file"
          ref={fileInputRef}
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.[0]) {
              handleUpload(e.target.files[0], true, uploadTargetFolderId || selectedFolderId);
              e.target.value = "";
            }
            setUploadTargetFolderId(null);
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          title="Upload file"
          className="h-7 w-7 rounded flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <Upload className="h-3.5 w-3.5" />
        </button>
        {onCreateFolderClick && (
          <button
            onClick={onCreateFolderClick}
            title="Create folder"
            className="h-7 w-7 rounded flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <FolderPlus className="h-3.5 w-3.5" />
          </button>
        )}
        <button title="Refresh" onClick={onRefresh} className="h-7 w-7 rounded flex items-center justify-center text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* ── File tree ── */}
      <div className="flex-1 overflow-y-auto py-2 custom-scrollbar font-sans">
        
        {projectResources.length === 0 ? (
          <div className="text-center py-8 text-[11px] text-slate-500 italic px-4 select-none">
            No folders or files yet.<br />Upload a dataset to start.
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {/* ── Render Folders ── */}
            {rootFolders.map((folder) => {
              const isOpen = !!expandedFolders[folder.id];
              const folderFiles = getFilesForFolder(folder.id);
              
              const isSelected = selectedFolderId === folder.id;

              return (
                <div key={folder.id} className="flex flex-col">
                  {/* Folder Row */}
                  <div
                    onClick={() => {
                      toggleFolder(folder.id);
                      onSelectFolder?.(folder.id);
                    }}
                    className={`flex items-center justify-between px-3 py-1 cursor-pointer rounded transition-colors text-[12px] group select-none ${
                      isSelected 
                        ? "bg-sky-500/10 text-sky-300 font-semibold" 
                        : "text-slate-350 hover:text-slate-200 hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      {isOpen ? (
                        <ChevronDown className="h-3 w-3 flex-shrink-0 text-slate-500" />
                      ) : (
                        <ChevronRight className="h-3 w-3 flex-shrink-0 text-slate-500" />
                      )}
                      {isOpen ? (
                        <Folder className="h-3.5 w-3.5 flex-shrink-0 text-sky-400" />
                      ) : (
                        <FolderClosed className="h-3.5 w-3.5 flex-shrink-0 text-sky-400/80" />
                      )}
                      <span className="truncate font-medium">{folder.name}</span>
                    </div>

                    {/* Direct Upload icon on hover */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectFolder?.(folder.id);
                        setUploadTargetFolderId(folder.id);
                        setTimeout(() => {
                          fileInputRef.current?.click();
                        }, 50);
                      }}
                      title="Upload file directly to this folder"
                      className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-slate-700/80 rounded transition-all text-slate-400 hover:text-slate-200 cursor-pointer"
                    >
                      <Upload className="h-3 w-3" />
                    </button>
                  </div>

                  {/* Folder Files */}
                  {isOpen && (
                    <div className="pl-6 flex flex-col gap-0.5 border-l border-slate-900 ml-5 mt-0.5 mb-1 pl-3">
                      {folderFiles.length === 0 ? (
                        <div className="px-3 py-0.5 text-[11px] text-slate-600 italic select-none">
                          Empty folder
                        </div>
                      ) : (
                        folderFiles.map((file) => (
                          <div
                            key={file.id}
                            onDoubleClick={() => onFileDoubleClick(file.name, file.id)}
                            className="flex items-center gap-1.5 px-2.5 py-0.5 cursor-pointer text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-sm transition-colors text-[11.5px] select-none"
                            title="Double click to preview dataset"
                          >
                            <FileSpreadsheet className="h-3.5 w-3.5 flex-shrink-0 text-emerald-500/70" />
                            <span className="truncate">{file.name}</span>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* ── Render Root Files (Files not in any folder) ── */}
            {rootFiles.map((file) => (
              <div
                key={file.id}
                onDoubleClick={() => onFileDoubleClick(file.name, file.id)}
                className="flex items-center gap-1.5 px-6 py-1 cursor-pointer text-slate-300 hover:text-white hover:bg-slate-800/40 rounded transition-colors text-[12px] select-none"
                title="Double click to preview dataset"
              >
                <FileSpreadsheet className="h-3.5 w-3.5 flex-shrink-0 text-emerald-500/70" />
                <span className="truncate">{file.name}</span>
              </div>
            ))}
          </div>
        )}

      </div>
    </aside>
  );
}
