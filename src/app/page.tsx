"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Plus, ArrowUp, MessageSquare, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from "@/components/ui/dialog";

// Sub-components
import Topbar from "@/components/workspace/Topbar";
import ActivityBar from "@/components/workspace/ActivityBar";
import TableOfContents from "@/components/workspace/TableOfContents";
import GeminiAssistant from "@/components/workspace/GeminiAssistant";
import CodeCell from "@/components/workspace/CodeCell";
import TextCell from "@/components/workspace/TextCell";
import LoginForm from "@/components/auth/LoginForm";
import { sendChatAction } from "@/lib/actions/ai.action";
import { analyzeFileAction, fetchProjectResourcesAction } from "@/lib/actions/project.action";
import { useAppDispatch, useAppSelector } from "@/redux/hooks";
import { fetchStorageLocations, createProject, createFolder } from "@/redux/slices/projectSlice";
import { uploadFileToApi } from "@/lib/file";

interface Message {
  role: "user" | "ai";
  text: string;
  code?: string | null;
  truncated?: boolean;
}

interface Cell {
  id: string;
  type: "code" | "text";
  source: string;
  output?: string | null;
  output_type?: "text" | "image" | "table" | null;
}

interface SessionState {
  active: boolean;
  filename: string;
  dfName: string;
  columns: string[];
  dtypes: Record<string, string>;
  rowCount: number;
}

function extractFolderId(payload: any): string | null {
  if (!payload) return null;
  return payload.data?.id || payload.id || payload.data?.data?.id || payload.data?.data?.folder_id || null;
}

function WorkspaceContent() {
  const searchParams = useSearchParams();
  const nbId = searchParams.get("nb");

  const [isLoggedIn, setIsLoggedIn] = React.useState(false);
  const [isAuthChecking, setIsAuthChecking] = React.useState(true);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      setIsLoggedIn(localStorage.getItem("isLoggedIn") === "true");
      setIsAuthChecking(false);
    }
  }, []);

  // ── Session / dataset state ──────────────────────────────────────────────
  const [session, setSession] = React.useState<SessionState>({
    active: false,
    filename: "",
    dfName: "",
    columns: [],
    dtypes: {},
    rowCount: 0,
  });
  const [uploadedFiles, setUploadedFiles] = React.useState<string[]>([]);
  const [currentVaultFileId, setCurrentVaultFileId] = React.useState<string | null>(null);

  // ── Notebook state ───────────────────────────────────────────────────────
  const [notebookId, setNotebookId] = React.useState<string | null>(null);
  const [notebookTitle, setNotebookTitle] = React.useState("Untitled");
  const [cells, setCells] = React.useState<Cell[]>([]);
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [pendingCode, setPendingCode] = React.useState<string | null>(null);

  // ── UI state ─────────────────────────────────────────────────────────────
  const [leftSidebarOpen, setLeftSidebarOpen] = React.useState(false);
  const [rightSidebarOpen, setRightSidebarOpen] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState<"gemini" | "preview">("gemini");
  const [showGeminiTab, setShowGeminiTab] = React.useState(true);
  const [showPreviewTab, setShowPreviewTab] = React.useState(true);
  const [chatLoading, setChatLoading] = React.useState(false);
  const [runningCellId, setRunningCellId] = React.useState<string | null>(null);
  const [welcomeInput, setWelcomeInput] = React.useState("");
  const [chatInput, setChatInput] = React.useState("");

  // Project creation state (Redux integrated)
  const dispatch = useAppDispatch();
  const { storageLocations, locationsLoading, createProjectLoading, createFolderLoading, selectedLocation } = useAppSelector((state) => state.project);

  const [isCreateProjectOpen, setIsCreateProjectOpen] = React.useState(false);
  const [projectName, setProjectName] = React.useState("");

  const [isCreateFolderOpen, setIsCreateFolderOpen] = React.useState(false);
  const [newFolderNameInput, setNewFolderNameInput] = React.useState("");

  // Prerequisite flow states
  const [createdProjectId, setCreatedProjectId] = React.useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("createdProjectId");
    }
    return null;
  });
  const [createdFolderId, setCreatedFolderId] = React.useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("createdFolderId");
    }
    return null;
  });
  const [pendingUploadFile, setPendingUploadFile] = React.useState<File | null>(null);
  const [isPrerequisiteOpen, setIsPrerequisiteOpen] = React.useState(false);
  const [prerequisiteStep, setPrerequisiteStep] = React.useState<"project" | "folder">("project");

  const [newProjectName, setNewProjectName] = React.useState("");
  const [newFolderName, setNewFolderName] = React.useState("");

  const [createdProjectName, setCreatedProjectName] = React.useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("createdProjectName");
    }
    return null;
  });

  interface Resource {
    id: string;
    name: string;
    type: "folder" | "file";
    parent: any;
  }
  const [projectResources, setProjectResources] = React.useState<Resource[]>([]);

  const loadProjectResources = React.useCallback(async () => {
    if (!createdProjectId) return;
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetchProjectResourcesAction(createdProjectId, null, token);
      if (res.success) {
        const list = res.data?.data || res.data || [];
        setProjectResources(list);
      }
    } catch (err) {
      console.error("Failed to load project resources:", err);
    }
  }, [createdProjectId]);

  React.useEffect(() => {
    loadProjectResources();
  }, [loadProjectResources]);

  React.useEffect(() => {
    if (createdProjectName && notebookTitle === "Untitled") {
      setNotebookTitle(createdProjectName);
    }
  }, [createdProjectName, notebookTitle]);

  React.useEffect(() => {
    if (isCreateProjectOpen) {
      dispatch(fetchStorageLocations());
    }
  }, [isCreateProjectOpen, dispatch]);

  const handleCreateProject = async () => {
    if (!projectName.trim() || !selectedLocation) return;
    try {
      const resultAction = await dispatch(createProject({ name: projectName, storageLocation: selectedLocation }));
      if (createProject.fulfilled.match(resultAction)) {
        alert(`Project "${projectName}" created successfully!`);
        const payloadData = resultAction.payload as any;
        const projId = payloadData?.data?.id;
        if (projId) {
          setCreatedProjectId(projId);
          localStorage.setItem("createdProjectId", projId);
          setCreatedProjectName(projectName);
          localStorage.setItem("createdProjectName", projectName);
        }
        setIsCreateProjectOpen(false);
        setProjectName("");
      } else {
        alert(resultAction.payload || "Failed to create project");
      }
    } catch (err: any) {
      alert(err.message || "Failed to create project");
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderNameInput.trim() || !createdProjectId) return;
    try {
      const resultAction = await dispatch(createFolder({ name: newFolderNameInput, projectId: createdProjectId }));
      if (createFolder.fulfilled.match(resultAction)) {
        alert(`Folder "${newFolderNameInput}" created successfully!`);
        const payloadData = resultAction.payload as any;
        const foldId = extractFolderId(payloadData);
        const finalFoldId = foldId || "created-folder";
        setCreatedFolderId(finalFoldId);
        localStorage.setItem("createdFolderId", finalFoldId);
        setIsCreateFolderOpen(false);
        setNewFolderNameInput("");
        loadProjectResources();
      } else {
        alert(resultAction.payload || "Failed to create folder");
      }
    } catch (err: any) {
      alert(err.message || "Failed to create folder");
    }
  };

  const handlePrerequisiteCreateProject = async () => {
    if (!newProjectName.trim() || !selectedLocation) return;
    try {
      const resultAction = await dispatch(createProject({ name: newProjectName, storageLocation: selectedLocation }));
      if (createProject.fulfilled.match(resultAction)) {
        alert(`Project "${newProjectName}" created successfully!`);
        const payloadData = resultAction.payload as any;
        const projId = payloadData?.data?.id;
        if (projId) {
          setCreatedProjectId(projId);
          localStorage.setItem("createdProjectId", projId);
          setCreatedProjectName(newProjectName);
          localStorage.setItem("createdProjectName", newProjectName);
          setPrerequisiteStep("folder");
        } else {
          alert("Project created, but ID not received");
        }
      } else {
        alert(resultAction.payload || "Failed to create project");
      }
    } catch (err: any) {
      alert(err.message || "Failed to create project");
    }
  };

  const handlePrerequisiteCreateFolder = async () => {
    if (!newFolderName.trim() || !createdProjectId) return;
    try {
      const resultAction = await dispatch(createFolder({ name: newFolderName, projectId: createdProjectId }));
      if (createFolder.fulfilled.match(resultAction)) {
        alert(`Folder "${newFolderName}" created successfully!`);
        const payloadData = resultAction.payload as any;
        const foldId = extractFolderId(payloadData);
        const finalFoldId = foldId || "created-folder";
        setCreatedFolderId(finalFoldId);
        localStorage.setItem("createdFolderId", finalFoldId);
        setIsPrerequisiteOpen(false);
        loadProjectResources();
        if (pendingUploadFile) {
          await proceedUpload(pendingUploadFile, createdProjectId, finalFoldId);
        }
      } else {
        alert(resultAction.payload || "Failed to create folder");
      }
    } catch (err: any) {
      alert(err.message || "Failed to create folder");
    }
  };

  const proceedUpload = async (file: File, projId?: string, foldId?: string) => {
    const activeProjId = projId || createdProjectId;
    const activeFoldId = foldId || createdFolderId;
    if (!activeProjId || !activeFoldId) return;
    triggerBanner("Uploading dataset…");
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const result = await uploadFileToApi(file, activeProjId, activeFoldId, token);
      if (!result.success) {
        triggerBanner(result.error || "Upload failed.", "err");
        alert("Upload failed: " + (result.error || "unknown error"));
        return;
      }
      const fileData = result.data;
      const fileId = fileData.id;

      triggerBanner("Analyzing dataset…");
      const analyzeResult = await analyzeFileAction(fileId, token);

      let analysisData = analyzeResult.success ? analyzeResult.data?.data : null;

      if (!analyzeResult.success) {
        console.warn("Backend analysis failed (likely the 307 redirect bug). Using local fallback.", analyzeResult.error);
        if (file.name.toLowerCase().endsWith('.csv')) {
          try {
            const text = await file.slice(0, 4096).text();
            const firstLine = text.split('\n')[0];
            const columns = firstLine.split(',').map(c => c.trim().replace(/^"|"$/g, ''));
            analysisData = { columns, dtypes: {}, row_count: file.size };
          } catch (e) {
            console.error("Local fallback extraction failed", e);
          }
        }
      }

      // Initialize notebook details associated with the uploaded file ID
      setCurrentVaultFileId(fileId);
      setNotebookId(null);
      setNotebookTitle((fileData.name || file.name).replace(/\.[^/.]+$/, ""));
      setCells([]);
      setMessages([]);

      setSession({
        active: true,
        filename: fileData.name || file.name,
        dfName: inferDfName(fileData.name || file.name),
        columns: analysisData?.columns || [],
        dtypes: analysisData?.dtypes || {},
        rowCount: analysisData?.row_count || fileData.size || file.size,
      });
      setUploadedFiles((prev) => Array.from(new Set([...prev, fileData.name || file.name])));
      triggerBanner(`✓ ${fileData.name || file.name} loaded and analyzed successfully`, "ok");
      setPendingUploadFile(null);
      loadProjectResources();
    } catch (err: any) {
      triggerBanner("Upload error: " + err.message, "err");
      alert("Upload error: " + err.message);
    }
  };
  const [saveStatus, setSaveStatus] = React.useState("All changes saved");
  const [banner, setBanner] = React.useState<{ text: string; type: "err" | "ok" | "" } | null>(null);

  const welcomeFileInputRef = React.useRef<HTMLInputElement | null>(null);

  // ── Helpers ──────────────────────────────────────────────────────────────
  const triggerBanner = (text: string, type: "err" | "ok" | "" = "") => {
    setBanner({ text, type });
    setTimeout(() => setBanner(null), 4000);
  };

  const inferDfName = (fn: string) => {
    let n = fn.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_]/g, "_").replace(/^(\d)/, "_$1");
    n = n.replace(/_+/g, "_").replace(/^_+|_+$/g, "");
    return "df_" + (n || "data");
  };

  const generateChips = () => {
    const { dfName, columns, dtypes } = session;
    if (!dfName || !session.active) return [];
    const chips: string[] = [`Show summary statistics for ${dfName}`];
    const numCol = columns.find((c) => dtypes[c]?.includes("float") || dtypes[c]?.includes("int"));
    const catCol = columns.find((c) => dtypes[c]?.includes("str") || dtypes[c]?.includes("object"));
    if (numCol) chips.push(`Visualize the distribution of '${numCol}'`);
    if (catCol) chips.push(`Show value counts for '${catCol}'`);
    if (numCol && catCol) chips.push(`Create a plot comparing survival rates by '${catCol}'`);
    return chips.slice(0, 4);
  };

  // ── Upload handler (real API) ─────────────────────────────────────────────
  const handleUpload = async (file: File, fromSidebar = false, folderId?: string | null) => {
    if (!file) return;

    let projId = createdProjectId;
    let foldId = folderId || createdFolderId;

    if (!projId || !foldId) {
      if (fromSidebar) {
        try {
          triggerBanner("Initializing workspace...");

          if (!projId) {
            // No project exists at all, create project and default folder
            const locsResult = await dispatch(fetchStorageLocations());
            let locId = "";
            if (fetchStorageLocations.fulfilled.match(locsResult) && locsResult.payload.length > 0) {
              locId = locsResult.payload[0].id;
            } else {
              locId = "default-loc";
            }

            const projResult = await dispatch(createProject({ name: "Default Project", storageLocation: locId }));
            if (createProject.fulfilled.match(projResult)) {
              const payloadData = projResult.payload as any;
              const createdProjId = payloadData?.data?.id;
              if (createdProjId) {
                projId = createdProjId;
                setCreatedProjectId(createdProjId);
                localStorage.setItem("createdProjectId", createdProjId);

                const foldResult = await dispatch(createFolder({ name: "Default Folder", projectId: createdProjId }));
                if (createFolder.fulfilled.match(foldResult)) {
                  const foldPayloadData = foldResult.payload as any;
                  const extractedId = extractFolderId(foldPayloadData);
                  const finalFoldId = extractedId || "created-folder";
                  foldId = finalFoldId;
                  setCreatedFolderId(finalFoldId);
                  localStorage.setItem("createdFolderId", finalFoldId);
                }
              }
            }
          } else {
            // Project exists, but no folder is active/selected.
            // Check if there is an existing folder we can use (load on-demand if empty).
            let resources = projectResources;
            if (resources.length === 0) {
              const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
              const res = await fetchProjectResourcesAction(projId, null, token);
              if (res.success) {
                resources = res.data?.data || res.data || [];
                setProjectResources(resources);
              }
            }

            const existingFolder = resources.find(r => r.type === "folder");
            if (existingFolder) {
              foldId = existingFolder.id;
              setCreatedFolderId(existingFolder.id);
              localStorage.setItem("createdFolderId", existingFolder.id);
            } else {
              // No folder exists in this project, create a default folder
              const foldResult = await dispatch(createFolder({ name: "Default Folder", projectId: projId }));
              if (createFolder.fulfilled.match(foldResult)) {
                const foldPayloadData = foldResult.payload as any;
                const extractedId = extractFolderId(foldPayloadData);
                const finalFoldId = extractedId || "created-folder";
                foldId = finalFoldId;
                setCreatedFolderId(finalFoldId);
                localStorage.setItem("createdFolderId", finalFoldId);
              }
            }
          }
        } catch (err) {
          console.error("Silent project/folder creation failed:", err);
        }
      } else {
        // Not from sidebar (welcome page upload)
        if (!projId) {
          setPendingUploadFile(file);
          setPrerequisiteStep("project");
          setIsPrerequisiteOpen(true);
          dispatch(fetchStorageLocations());
          return;
        } else {
          // Project exists, but no folder. Load resources on-demand to check folders.
          let resources = projectResources;
          if (resources.length === 0) {
            try {
              const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
              const res = await fetchProjectResourcesAction(projId, null, token);
              if (res.success) {
                resources = res.data?.data || res.data || [];
                setProjectResources(resources);
              }
            } catch (err) {
              console.error("Failed to check resources for welcome page upload:", err);
            }
          }

          const existingFolder = resources.find(r => r.type === "folder");
          if (existingFolder) {
            foldId = existingFolder.id;
            setCreatedFolderId(existingFolder.id);
            localStorage.setItem("createdFolderId", existingFolder.id);
          } else {
            setPendingUploadFile(file);
            setPrerequisiteStep("folder");
            setIsPrerequisiteOpen(true);
            return;
          }
        }
      }
    }

    if (projId && foldId && foldId !== "created-folder") {
      await proceedUpload(file, projId, foldId);
    } else {
      triggerBanner("Workspace initialization failed", "err");
    }
  };

  const handleSelectDataset = async (filename: string, fileId?: string | null) => {
    const activeFileId = fileId || projectResources.find(r => r.type === "file" && r.name === filename)?.id || null;
    
    setCurrentVaultFileId(activeFileId);
    
    let loadedNotebookFromBackend = false;
    
    if (activeFileId) {
      triggerBanner(`Restoring notebook for ${filename}…`);
      try {
        const res = await fetch(`/api/notebooks/by-file/${activeFileId}`);
        if (res.ok) {
          const data = await res.json();
          setNotebookId(data.notebook_id);
          setNotebookTitle(data.title || filename.replace(/\.[^/.]+$/, ""));
          setCells(
            (data.cells || []).map((c: any, i: number) => ({
              id: c.id || `cell_${i}_${Math.random()}`,
              type: c.type,
              source: c.source || "",
              output: c.output || null,
              output_type: c.output_type || null,
            }))
          );
          setMessages(
            (data.messages || []).map((m: any) => ({
              role: m.role,
              text: m.text,
              code: m.code || null,
            }))
          );
          loadedNotebookFromBackend = true;
          triggerBanner(`✓ Notebook restored for ${filename}`, "ok");
        } else {
          // If not found in backend, check per-file localStorage
          const localRaw = localStorage.getItem(`dn_notebook_${activeFileId}`);
          if (localRaw) {
            try {
              const snap = JSON.parse(localRaw);
              if (snap.notebook_id) setNotebookId(snap.notebook_id);
              if (snap.title) setNotebookTitle(snap.title);
              if (snap.cells?.length) setCells(snap.cells);
              if (snap.messages?.length) setMessages(snap.messages);
              loadedNotebookFromBackend = true;
              triggerBanner(`✓ Notebook restored from local cache for ${filename}`, "ok");
            } catch (_) {}
          }
        }
      } catch (err: any) {
        console.warn("Failed to check backend notebook by-file:", err);
      }
    }

    // If notebook wasn't loaded (i.e. fresh workspace for this file), initialize state
    if (!loadedNotebookFromBackend) {
      setNotebookId(null);
      setNotebookTitle(filename.replace(/\.[^/.]+$/, ""));
      setCells([]);
      setMessages([]);
    }

    triggerBanner(`Loading dataset ${filename}…`);
    try {
      const res = await fetch("/api/upload/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename }),
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok) {
        // Fallback: if session not found, try to locate it in projectResources and analyze it
        const fileObj = projectResources.find(r => r.type === "file" && r.name === filename);
        if (fileObj) {
          triggerBanner(`Analyzing dataset ${filename}…`);
          const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
          const analyzeResult = await analyzeFileAction(fileObj.id, token);
          if (analyzeResult.success) {
            const analysisData = analyzeResult.data?.data;
            setSession({
              active: true,
              filename: fileObj.name,
              dfName: inferDfName(fileObj.name),
              columns: analysisData?.columns || [],
              dtypes: analysisData?.dtypes || {},
              rowCount: analysisData?.row_count || 0,
            });
            setUploadedFiles((prev) => Array.from(new Set([...prev, fileObj.name])));
            triggerBanner(`✓ Switched to dataset: ${fileObj.name}`, "ok");
            setRightSidebarOpen(true);
            setShowPreviewTab(true);
            setActiveTab("preview");
            return;
          }
        }
        triggerBanner(data.detail || "Selection failed.", "err");
        return;
      }
      setSession({
        active: true,
        filename: data.filename,
        dfName: inferDfName(data.filename),
        columns: data.columns || [],
        dtypes: data.dtypes || {},
        rowCount: data.row_count || 0,
      });
      triggerBanner(`✓ Switched to dataset: ${data.filename}`, "ok");
      setRightSidebarOpen(true);
      setShowPreviewTab(true);
      setActiveTab("preview");
    } catch (err: any) {
      triggerBanner("Selection error: " + err.message, "err");
    }
  };

  const closeGeminiTab = () => {
    setShowGeminiTab(false);
    if (!showPreviewTab) {
      setRightSidebarOpen(false);
    } else {
      setActiveTab("preview");
    }
  };

  const closePreviewTab = () => {
    setShowPreviewTab(false);
    if (!showGeminiTab) {
      setRightSidebarOpen(false);
    } else {
      setActiveTab("gemini");
    }
  };



  // ── SSE Stream Execution (real API) ──────────────────────────────────────
  const streamExec = async (cellId: string, code: string) => {
    setRunningCellId(cellId);
    setCells((prev) =>
      prev.map((c) => (c.id === cellId ? { ...c, output: JSON.stringify([]), output_type: "text" } : c))
    );

    const appendOutput = (type: "text" | "image" | "table", data: string) => {
      setCells((prev) =>
        prev.map((c) => {
          if (c.id !== cellId) return c;
          let list: { type: string; data: string }[] = [];
          try {
            list = JSON.parse(c.output || "[]");
          } catch { }
          if (!Array.isArray(list)) list = [];

          if (type === "text") {
            if (list.length > 0 && list[list.length - 1].type === "text") {
              list[list.length - 1].data += data;
            } else {
              list.push({ type: "text", data });
            }
          } else {
            list.push({ type, data });
          }
          return { ...c, output: JSON.stringify(list) };
        })
      );
    };

    try {
      const res = await fetch("/api/execute/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ code }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({ detail: "Execution failed" }));
        setCells((prev) =>
          prev.map((c) =>
            c.id === cellId
              ? { ...c, output: JSON.stringify([{ type: "text", data: `❌ ${e.detail || "Execution failed"}` }]), output_type: "text" }
              : c
          )
        );
        return;
      }
      const reader = res.body?.getReader();
      const dec = new TextDecoder();
      let buf = "";
      if (!reader) return;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const part of parts) {
          const raw = part.trim();
          if (!raw || !raw.startsWith("data:")) continue;
          try {
            const ev = JSON.parse(raw.slice(5).trim());
            if (ev.type === "stdout") {
              appendOutput("text", ev.data + "\n");
            } else if (ev.type === "image") {
              appendOutput("image", ev.data);
            } else if (ev.type === "table") {
              appendOutput("table", JSON.stringify(ev.data));
            } else if (ev.type === "error") {
              appendOutput("text", "\n❌ " + ev.data);
            }
          } catch (_) { }
        }
      }
    } catch (err: any) {
      setCells((prev) =>
        prev.map((c) =>
          c.id === cellId ? { ...c, output: JSON.stringify([{ type: "text", data: "❌ " + err.message }]), output_type: "text" } : c
        )
      );
    } finally {
      setRunningCellId(null);
    }
  };

  // ── Chat with Gemini (real API) ───────────────────────────────────────────
  const sendChat = async (text: string) => {
    if (!text.trim()) return;
    if (!session.active) {
      triggerBanner("Please upload a dataset first", "err");
      return;
    }
    setChatLoading(true);
    setPendingCode(null);
    setMessages((prev) => [...prev, { role: "user", text }]);
    try {
      const res = await sendChatAction(text);
      if (res.status === 401 || res.status === 404) {
        triggerBanner("Session expired — please re-upload your dataset", "err");
        setSession({ active: false, filename: "", dfName: "", columns: [], dtypes: {}, rowCount: 0 });
        setMessages([]);
        setCells([]);
        return;
      }
      const data = res.data;
      if (!res.ok) throw new Error(data?.detail || res.error || "Chat failed");
      const isTruncated = data?.truncated === true;
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          text: data?.explanation || "Here is the code.",
          code: data?.code || null,
          truncated: isTruncated,
        },
      ]);
      if (data?.code && !isTruncated) setPendingCode(data.code);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "⚠️ " + err.message, code: null },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  // ── Welcome prompt submit: real API + open sidebars ───────────────────────
  const handlePromptSubmit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (!session.active) {
      triggerBanner("Please upload a dataset first", "err");
      return;
    }
    setWelcomeInput("");
    setChatInput("");
    setLeftSidebarOpen(true);
    setRightSidebarOpen(true);
    setShowGeminiTab(true);
    setActiveTab("gemini");
    sendChat(trimmed);
  };

  const handleUnloadDataset = () => {
    setSession({ active: false, filename: "", dfName: "", columns: [], dtypes: {}, rowCount: 0 });
    setUploadedFiles([]);
  };

  const handleLoadSampleData = () => {
    const sampleCsv = 'Name,Age,Salary,Department\nAlice,28,75000,Engineering\nBob,34,82000,Sales\nCharlie,31,68000,HR\nDiana,26,72000,Engineering\nEve,29,79000,Sales';
    const blob = new Blob([sampleCsv], { type: 'text/csv' });
    const file = new File([blob], 'sample_data.csv', { type: 'text/csv' });
    handleUpload(file);
  };

  // ── Cell helpers ──────────────────────────────────────────────────────────
  const addCodeCell = (initialCode = "", executeImmediately = false) => {
    const id = "cell_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    const newCell: Cell = { id, type: "code", source: initialCode, output: null, output_type: null };
    setCells((prev) => [...prev, newCell]);
    if (executeImmediately && initialCode) {
      setTimeout(() => streamExec(id, initialCode), 100);
    }
  };

  const addTextCell = () => {
    const id = "cell_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    setCells((prev) => [...prev, { id, type: "text", source: "", output: null, output_type: null }]);
  };

  const moveCellUp = (index: number) => {
    if (index === 0) return;
    const n = [...cells];
    [n[index - 1], n[index]] = [n[index], n[index - 1]];
    setCells(n);
  };

  const moveCellDown = (index: number) => {
    if (index === cells.length - 1) return;
    const n = [...cells];
    [n[index], n[index + 1]] = [n[index + 1], n[index]];
    setCells(n);
  };

  // ── Save / load notebook ──────────────────────────────────────────────────
  const saveNotebook = async () => {
    setSaveStatus("Saving…");
    const snapshot = {
      notebook_id: notebookId,
      vault_file_id: currentVaultFileId,
      title: notebookTitle,
      dataset_filename: session.filename || null,
      session,
      cells,
      messages,
      saved_at: new Date().toISOString(),
    };
    localStorage.setItem("dn_current_notebook", JSON.stringify(snapshot));
    if (currentVaultFileId) {
      localStorage.setItem(`dn_notebook_${currentVaultFileId}`, JSON.stringify(snapshot));
    }
    try {
      const res = await fetch("/api/notebooks/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notebook_id: notebookId || undefined,
          vault_file_id: currentVaultFileId || undefined,
          title: notebookTitle,
          cells: cells.map((c, i) => ({
            id: c.id || `cell_${i}`,
            type: c.type,
            source: c.source,
            output: c.output,
            output_type: c.output_type,
          })),
          messages: messages.map(m => ({
            role: m.role,
            text: m.text,
            code: m.code || null,
          })),
          dataset_filename: session.filename || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Save failed");
      setNotebookId(data.notebook_id);
      const hhmm = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setSaveStatus(`✓ Saved ${hhmm}`);
    } catch {
      setSaveStatus("Saved locally");
    }
  };

  const loadNotebookById = async (id: string) => {
    try {
      triggerBanner("Loading notebook…");
      const res = await fetch(`/api/notebooks/${id}`);
      if (!res.ok) { triggerBanner("Notebook not found", "err"); return; }
      const data = await res.json();
      setNotebookId(data.notebook_id);
      setCurrentVaultFileId(data.vault_file_id || null);
      setNotebookTitle(data.title || "Untitled");
      if (data.dataset_filename) {
        setSession({
          active: true,
          filename: data.dataset_filename,
          dfName: inferDfName(data.dataset_filename),
          columns: [],
          dtypes: {},
          rowCount: 0,
        });
        setUploadedFiles([data.dataset_filename]);
      }
      setCells(
        (data.cells || []).map((c: any, i: number) => ({
          id: c.id || `cell_${i}_${Math.random()}`,
          type: c.type,
          source: c.source || "",
          output: c.output || null,
          output_type: c.output_type || null,
        }))
      );
      setMessages(
        (data.messages || []).map((m: any) => ({
          role: m.role,
          text: m.text,
          code: m.code || null,
        }))
      );
      triggerBanner(`Loaded: ${data.title}`, "ok");
    } catch (err: any) {
      triggerBanner("Load failed: " + err.message, "err");
    }
  };

  const restoreFromLocal = () => {
    const raw = localStorage.getItem("dn_current_notebook");
    if (!raw) return;
    try {
      const snap = JSON.parse(raw);
      if (snap.session?.active) setSession(snap.session);
      if (snap.notebook_id) setNotebookId(snap.notebook_id);
      if (snap.vault_file_id) setCurrentVaultFileId(snap.vault_file_id);
      if (snap.title) setNotebookTitle(snap.title);
      if (snap.dataset_filename) setUploadedFiles([snap.dataset_filename]);
      if (snap.cells?.length) setCells(snap.cells);
      if (snap.messages?.length) setMessages(snap.messages);
    } catch (_) { }
  };

  const runAllCells = async () => {
    triggerBanner("Running all cells…");
    const codeCells = cells.filter((c) => c.type === "code");
    for (const cell of codeCells) {
      await streamExec(cell.id, cell.source);
    }
    triggerBanner("✓ All code cells executed", "ok");
  };

  const handleNewNotebook = () => {
    if (!confirm("Start a new notebook? This clears the current session.")) return;
    setSession({ active: false, filename: "", dfName: "", columns: [], dtypes: {}, rowCount: 0 });
    setMessages([]);
    setCells([]);
    setNotebookId(null);
    setCurrentVaultFileId(null);
    setNotebookTitle("Untitled");
    setUploadedFiles([]);
    localStorage.removeItem("dn_current_notebook");
    setLeftSidebarOpen(false);
    setRightSidebarOpen(false);
  };

  // Autosave every 10s
  React.useEffect(() => {
    const interval = setInterval(() => {
      if (cells.length > 0) saveNotebook();
    }, 10000);
    return () => clearInterval(interval);
  }, [cells, notebookId, notebookTitle, session, messages, currentVaultFileId]);

  // Init
  React.useEffect(() => {
    if (searchParams.get("new") === "true") {
      setSession({ active: false, filename: "", dfName: "", columns: [], dtypes: {}, rowCount: 0 });
      setMessages([]);
      setCells([]);
      setNotebookId(null);
      setCurrentVaultFileId(null);
      setNotebookTitle("Untitled");
      setUploadedFiles([]);
      localStorage.removeItem("dn_current_notebook");
      setLeftSidebarOpen(false);
      setRightSidebarOpen(false);
    } else if (nbId) {
      loadNotebookById(nbId);
      setLeftSidebarOpen(true);
      setRightSidebarOpen(true);
    } else {
      const raw = localStorage.getItem("dn_current_notebook");
      if (raw) {
        restoreFromLocal();
      } else {
        setSession({ active: false, filename: "", dfName: "", columns: [], dtypes: {}, rowCount: 0 });
        setMessages([]);
        setCells([]);
        setNotebookId(null);
        setCurrentVaultFileId(null);
        const savedProjName = localStorage.getItem("createdProjectName");
        setNotebookTitle(savedProjName || "Untitled");
        setUploadedFiles([]);
      }
      setLeftSidebarOpen(!!localStorage.getItem("createdProjectId"));
      setRightSidebarOpen(false);
    }
    if (searchParams.get("toc") === "true") setLeftSidebarOpen(true);
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────
  if (isAuthChecking) {
    return (
      <div className="h-screen bg-[#0A1628] text-slate-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <LoginForm
        onLoginSuccess={() => {
          localStorage.setItem("isLoggedIn", "true");
          setIsLoggedIn(true);
        }}
      />
    );
  }

  const chips = generateChips();

  return (
    <div className="h-screen bg-[#0A1628] text-slate-100 flex flex-col font-sans overflow-hidden">

      {/* ── Topbar ── */}
      <Topbar
        notebookTitle={notebookTitle}
        setNotebookTitle={setNotebookTitle}
        saveStatus={saveStatus}
        saveNotebook={saveNotebook}
        onRunAll={runAllCells}
      />

      {/* ── Banner ── */}
      {banner && (
        <div
          role="alert"
          className={`px-4 py-1.5 text-xs text-center border-b font-medium transition-all ${banner.type === "err"
              ? "bg-red-950/20 text-red-400 border-red-900/30"
              : banner.type === "ok"
                ? "bg-emerald-950/20 text-emerald-400 border-emerald-900/30"
                : "bg-amber-950/20 text-amber-400 border-amber-900/30"
            }`}
        >
          {banner.text}
        </div>
      )}

      {/* ── Main layout ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Activity Bar */}
        <ActivityBar
          leftSidebarOpen={leftSidebarOpen}
          setLeftSidebarOpen={setLeftSidebarOpen}
          onNewNotebook={() => setIsCreateProjectOpen(true)}
        />

        {/* Left sidebar: Table of Contents */}
        {leftSidebarOpen && (
          <TableOfContents
            projectResources={projectResources}
            projectName={createdProjectName}
            handleUpload={handleUpload}
            onClose={() => setLeftSidebarOpen(false)}
            onFileDoubleClick={handleSelectDataset}
            onRefresh={loadProjectResources}
            onCreateFolderClick={() => {
              if (!createdProjectId) {
                alert("Please create or select a project first.");
                return;
              }
              setIsCreateFolderOpen(true);
            }}
            selectedFolderId={createdFolderId}
            onSelectFolder={(folderId) => {
              setCreatedFolderId(folderId);
              localStorage.setItem("createdFolderId", folderId);
            }}
          />
        )}

        {/* ── Central workspace ── */}
        <main className="flex-1 flex flex-col overflow-hidden bg-[#0A1628]">

          {cells.length === 0 && !rightSidebarOpen ? (
            /* ── WELCOME SCREEN (Image 1) ─────────────────────────────── */
            <div className="flex-1 flex flex-col items-center justify-center px-6 overflow-y-auto">
              <div className="w-full max-w-2xl flex flex-col items-center gap-7">

                {/* Greeting */}
                <div className="text-center">
                  <h1 className="text-[36px] font-semibold tracking-tight text-slate-100 leading-none">
                    Hello, Manjunathgan
                  </h1>
                  <p className="mt-3 text-[14px] text-slate-400">
                    How can I help you today?
                  </p>
                </div>

                {/* Suggestion chips — only shown when dataset uploaded */}
                {chips.length > 0 && (
                  <div className="flex flex-col gap-2 w-full items-center">
                    {chips.map((chip, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setWelcomeInput(chip);
                          setChatInput(chip);
                        }}
                        className="px-5 py-2.5 rounded-full border border-emerald-500/20 bg-emerald-500/[0.03] text-[13px] text-emerald-400 hover:text-emerald-300 hover:border-emerald-400/40 hover:bg-emerald-500/[0.07] transition-all cursor-pointer w-full max-w-lg text-center"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                )}

                {/* Prompt input box */}
                <div className="w-full max-w-lg">
                  <div className="bg-[#00081a] border border-slate-800 rounded-2xl px-4 pt-4 pb-3 flex flex-col gap-3 focus-within:border-cyan-500/40 focus-within:shadow-[0_0_0_3px_rgba(6,182,212,0.04)] transition-all">
                    <input
                      type="file"
                      ref={welcomeFileInputRef}
                      accept=".csv,.xlsx,.xls"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files?.[0]) {
                          handleUpload(e.target.files[0]);
                          e.target.value = "";
                        }
                      }}
                    />
                    {session.active && (
                      <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400 text-xs w-fit select-none">
                        <span className="font-mono font-medium">{session.filename}</span>
                        <button
                          onClick={handleUnloadDataset}
                          className="text-emerald-500 hover:text-emerald-300 transition-colors cursor-pointer"
                          title="Unload dataset"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                    <textarea
                      value={welcomeInput}
                      onChange={(e) => {
                        setWelcomeInput(e.target.value);
                        setChatInput(e.target.value);
                        const el = e.currentTarget;
                        el.style.height = "auto";
                        el.style.height = Math.min(el.scrollHeight, 140) + "px";
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          handlePromptSubmit(welcomeInput);
                        }
                      }}
                      placeholder="What can I help you build?"
                      rows={2}
                      className="w-full bg-transparent outline-none resize-none text-slate-200 text-[14px] placeholder:text-slate-600 leading-relaxed min-h-[44px] max-h-36"
                    />
                    <div className="flex items-center justify-between border-t border-slate-800/60 pt-2.5">
                      <button
                        onClick={() => welcomeFileInputRef.current?.click()}
                        className="p-1.5 text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 rounded-lg transition-all cursor-pointer"
                        title={session.active ? `Dataset: ${session.filename}` : "Upload dataset (.csv, .xlsx)"}
                      >
                        <Plus className="h-[18px] w-[18px] stroke-[2.5]" />
                      </button>
                      <button
                        disabled={!welcomeInput.trim()}
                        onClick={() => handlePromptSubmit(welcomeInput)}
                        className={`h-8 w-8 rounded-full flex items-center justify-center transition-all ${welcomeInput.trim()
                            ? "bg-emerald-500 hover:bg-emerald-400 text-slate-950 cursor-pointer hover:shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                            : "bg-slate-800 text-slate-600 cursor-not-allowed opacity-40"
                          }`}
                      >
                        <ArrowUp className="h-4 w-4 stroke-[2.5]" />
                      </button>
                    </div>
                  </div>
                  {/* Dataset status hint */}
                  <p className="text-center text-[11px] text-slate-600 mt-2.5">
                    {session.active
                      ? `✓ ${session.filename} · ${session.rowCount} rows`
                      : "Upload a dataset to get started"}
                  </p>

                  {!session.active && (
                    <div className="mt-4 flex flex-col items-center gap-2 text-center">
                      <p className="text-[11px] text-slate-500">
                        Don't have a dataset? Try our sample data.
                      </p>
                      <button
                        onClick={handleLoadSampleData}
                        className="px-4 py-1.5 rounded-full border border-slate-700 bg-slate-900/60 hover:border-emerald-500/30 text-xs text-slate-350 hover:text-emerald-400 hover:bg-slate-900 transition-all cursor-pointer shadow-sm font-medium"
                      >
                        [Sample] Use Sample Data
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* ── NOTEBOOK WORKSPACE (Image 2 - left half) ─────────────── */
            <div className="flex-1 overflow-y-auto px-6 py-6">
              <div className=" flex flex-col gap-5 pb-28">

                {/* Cell list */}
                {cells.map((cell, idx) =>
                  cell.type === "code" ? (
                    <CodeCell
                      key={cell.id}
                      cellId={cell.id}
                      source={cell.source}
                      output={cell.output}
                      outputType={cell.output_type}
                      index={idx}
                      runningCellId={runningCellId}
                      streamExec={streamExec}
                      onUpdateSource={(id, src) =>
                        setCells((prev) => prev.map((c) => (c.id === id ? { ...c, source: src } : c)))
                      }
                      onMoveUp={moveCellUp}
                      onMoveDown={moveCellDown}
                      onDelete={(id) => setCells((prev) => prev.filter((c) => c.id !== id))}
                    />
                  ) : (
                    <TextCell
                      key={cell.id}
                      cellId={cell.id}
                      source={cell.source}
                      index={idx}
                      onUpdateSource={(id, src) =>
                        setCells((prev) => prev.map((c) => (c.id === id ? { ...c, source: src } : c)))
                      }
                      onMoveUp={moveCellUp}
                      onMoveDown={moveCellDown}
                      onDelete={(id) => setCells((prev) => prev.filter((c) => c.id !== id))}
                    />
                  )
                )}

                {/* Add cell bar */}
                <div className="relative flex items-center justify-center py-4 mt-2">
                  <div className="absolute inset-x-0 top-1/2 h-px bg-slate-800/60" />
                  <div className="relative flex items-center gap-3 z-10">
                    <button
                      onClick={() => addCodeCell()}
                      className="flex items-center gap-1.5 px-4 py-1.5 bg-[#0a1628] border border-slate-800 hover:border-cyan-500/30 rounded-full text-[11px] text-slate-500 hover:text-cyan-400 font-semibold transition-all cursor-pointer shadow-sm"
                    >
                      + Code
                    </button>
                    <button
                      onClick={() => addTextCell()}
                      className="flex items-center gap-1.5 px-4 py-1.5 bg-[#0a1628] border border-slate-800 hover:border-cyan-500/30 rounded-full text-[11px] text-slate-500 hover:text-cyan-400 font-semibold transition-all cursor-pointer shadow-sm"
                    >
                      + Text
                    </button>
                  </div>
                </div>

              </div>
            </div>
          )}
        </main>

        {/* ── Right sidebar: Gemini Assistant (Image 2 - right half) ── */}
        {rightSidebarOpen && (
          <GeminiAssistant
            messages={messages}
            chatInput={chatInput}
            setChatInput={setChatInput}
            chatLoading={chatLoading}
            sendChat={sendChat}
            pendingCode={pendingCode}
            setPendingCode={setPendingCode}
            addCodeCell={addCodeCell}
            onClose={() => setRightSidebarOpen(false)}
            handleUpload={handleUpload}
            sessionActive={session.active}
            sessionFilename={session.filename}
            onUnloadDataset={handleUnloadDataset}
            triggerBanner={triggerBanner}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            showGeminiTab={showGeminiTab}
            showPreviewTab={showPreviewTab}
            onCloseGeminiTab={closeGeminiTab}
            onClosePreviewTab={closePreviewTab}
          />
        )}

        {/* Floating Gemini button when right sidebar is closed */}
        {!rightSidebarOpen && cells.length > 0 && (
          <button
            onClick={() => {
              setRightSidebarOpen(true);
              setShowGeminiTab(true);
              setShowPreviewTab(true);
            }}
            className="fixed bottom-6 right-6 h-11 w-11 rounded-full bg-[#00bcd4] hover:bg-[#00bcd4]/80 text-slate-950 shadow-lg z-50 transition-all hover:scale-105 flex items-center justify-center"
          >
            <MessageSquare className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Create Project Dialog */}
      <Dialog open={isCreateProjectOpen} onOpenChange={(open) => !open && setIsCreateProjectOpen(false)}>
        <DialogContent className="bg-slate-900 border-slate-800 text-slate-100">
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div>
              <Label htmlFor="project-name-input-main" className="text-slate-400 mb-2 block">Project Name</Label>
              <Input
                id="project-name-input-main"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="bg-slate-950 border-slate-800 text-slate-100 focus-visible:ring-emerald-500"
                placeholder="e.g. Project - 7"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setIsCreateProjectOpen(false)} className="hover:bg-slate-800 text-slate-400 hover:text-slate-200">
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleCreateProject}
              disabled={createProjectLoading || !projectName.trim() || locationsLoading || !selectedLocation}
              className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold"
            >
              {createProjectLoading ? "Creating..." : "Create Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Folder Dialog */}
      <Dialog open={isCreateFolderOpen} onOpenChange={(open) => !open && setIsCreateFolderOpen(false)}>
        <DialogContent className="bg-slate-900 border-slate-800 text-slate-100">
          <DialogHeader>
            <DialogTitle>Create New Folder</DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div>
              <Label htmlFor="folder-name-input-main" className="text-slate-400 mb-2 block">Folder Name</Label>
              <Input
                id="folder-name-input-main"
                value={newFolderNameInput}
                onChange={(e) => setNewFolderNameInput(e.target.value)}
                className="bg-slate-950 border-slate-800 text-slate-100 focus-visible:ring-emerald-500"
                placeholder="e.g. Datasets"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setIsCreateFolderOpen(false)} className="hover:bg-slate-800 text-slate-400 hover:text-slate-200">
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleCreateFolder}
              disabled={createFolderLoading || !newFolderNameInput.trim()}
              className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold"
            >
              {createFolderLoading ? "Creating..." : "Create Folder"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Prerequisite Project/Folder Creation Dialog */}
      <Dialog open={isPrerequisiteOpen} onOpenChange={(open) => !open && setIsPrerequisiteOpen(false)}>
        <DialogContent className="bg-slate-900 border-slate-800 text-slate-100">
          <DialogHeader>
            <DialogTitle>
              {prerequisiteStep === "project" ? "Step 1: Create Project" : "Step 2: Create Folder"}
            </DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            {prerequisiteStep === "project" ? (
              <div>
                <Label htmlFor="prereq-project-name" className="text-slate-400 mb-2 block">
                  You need to create a project first before uploading. Enter Project Name:
                </Label>
                <Input
                  id="prereq-project-name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="bg-slate-950 border-slate-800 text-slate-100 focus-visible:ring-emerald-500"
                  placeholder="e.g. Project Alpha"
                />
              </div>
            ) : (
              <div>
                <Label htmlFor="prereq-folder-name" className="text-slate-400 mb-2 block">
                  Now create a folder under your project. Enter Folder Name:
                </Label>
                <Input
                  id="prereq-folder-name"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  className="bg-slate-950 border-slate-800 text-slate-100 focus-visible:ring-emerald-500"
                  placeholder="e.g. Datasets"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setIsPrerequisiteOpen(false)} className="hover:bg-slate-800 text-slate-400 hover:text-slate-200">
              Cancel
            </Button>
            {prerequisiteStep === "project" ? (
              <Button
                size="sm"
                onClick={handlePrerequisiteCreateProject}
                disabled={createProjectLoading || !newProjectName.trim() || locationsLoading || !selectedLocation}
                className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold"
              >
                {createProjectLoading ? "Creating..." : "Create Project"}
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handlePrerequisiteCreateFolder}
                disabled={createFolderLoading || !newFolderName.trim()}
                className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold"
              >
                {createFolderLoading ? "Creating..." : "Create Folder"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function WorkspacePage() {
  return (
    <React.Suspense fallback={
      <div className="h-screen bg-[#0A1628] text-slate-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
      </div>
    }>
      <WorkspaceContent />
    </React.Suspense>
  );
}
