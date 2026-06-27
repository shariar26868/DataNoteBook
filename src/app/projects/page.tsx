"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Search, 
  Plus, 
  FolderClosed, 
  MoreVertical, 
  FolderOpen, 
  Loader2, 
  AlertTriangle 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogFooter 
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import Topbar from "@/components/workspace/Topbar";
import ActivityBar from "@/components/workspace/ActivityBar";
import { useAppDispatch, useAppSelector } from "@/redux/hooks";
import { fetchStorageLocations, createProject } from "@/redux/slices/projectSlice";
import { fetchProjectsAction } from "@/lib/actions/project.action";

interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  storage_location?: string;
}

export default function ProjectsPage() {
  const router = useRouter();
  const [isAuthChecking, setIsAuthChecking] = React.useState(true);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const logged = localStorage.getItem("isLoggedIn") === "true";
      if (!logged) {
        router.push("/");
      } else {
        setIsAuthChecking(false);
      }
    }
  }, [router]);

  const [projects, setProjects] = React.useState<Project[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  
  // Controls
  const [search, setSearch] = React.useState("");
  const [sort, setSort] = React.useState("updated");

  // Project creation state (Redux integrated)
  const dispatch = useAppDispatch();
  const { storageLocations, locationsLoading, createProjectLoading, selectedLocation } = useAppSelector((state) => state.project);
  
  const [isCreateProjectOpen, setIsCreateProjectOpen] = React.useState(false);
  const [projectName, setProjectName] = React.useState("");

  React.useEffect(() => {
    if (isCreateProjectOpen) {
      dispatch(fetchStorageLocations());
    }
  }, [isCreateProjectOpen, dispatch]);

  const loadProjects = React.useCallback(async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("token");
      const result = await fetchProjectsAction(token);
      if (!result.success) throw new Error(result.error || "Failed to fetch projects");
      const list = result.data?.data || result.data || [];
      setProjects(Array.isArray(list) ? list : []);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Could not load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreateProject = async () => {
    if (!projectName.trim() || !selectedLocation) return;
    try {
      const resultAction = await dispatch(createProject({ name: projectName, storageLocation: selectedLocation }));
      if (createProject.fulfilled.match(resultAction)) {
        alert(`Project "${projectName}" created successfully!`);
        setIsCreateProjectOpen(false);
        setProjectName("");
        loadProjects();
      } else {
        alert(resultAction.payload || "Failed to create project");
      }
    } catch (err: any) {
      alert(err.message || "Failed to create project");
    }
  };

  const handleSelectProject = (projectId: string, projectName: string) => {
    localStorage.setItem("createdProjectId", projectId);
    localStorage.setItem("createdProjectName", projectName);
    localStorage.removeItem("createdFolderId");
    router.push("/");
  };

  const filteredProjects = React.useMemo(() => {
    if (!search) return projects;
    const q = search.toLowerCase();
    return projects.filter(p => (p.name || "").toLowerCase().includes(q));
  }, [projects, search]);

  const sortedProjects = React.useMemo(() => {
    const list = [...filteredProjects];
    if (sort === "title") {
      list.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    } else {
      list.sort((a, b) => {
        const dateA = a.updated_at || a.created_at || "";
        const dateB = b.updated_at || b.created_at || "";
        return dateB.localeCompare(dateA);
      });
    }
    return list;
  }, [filteredProjects, sort]);

  const formatDate = (iso: string) => {
    if (!iso) return "";
    const d = new Date(iso);
    const now = new Date();
    const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
    if (diff === 0) return "Today";
    if (diff === 1) return "Yesterday";
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  };

  if (isAuthChecking) {
    return (
      <div className="min-h-screen bg-[#070a0e] text-slate-100 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-sky-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#070a0e] text-slate-100 flex flex-col font-sans h-screen overflow-hidden">
      {/* Shared Top Bar */}
      <Topbar />

      {/* Sidebar & Workspace */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Shared Activity Bar */}
        <ActivityBar
          leftSidebarOpen={false}
          setLeftSidebarOpen={() => router.push("/?toc=true")}
          onNewNotebook={() => setIsCreateProjectOpen(true)}
        />

        {/* Main Dashboard */}
        <main className="flex-1 overflow-y-auto px-4 py-8 md:px-8 max-w-4xl mx-auto w-full">
          {/* Search bar */}
          <div className="relative mb-6 max-w-md">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <Input
              placeholder="Search Projects"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-slate-900 border-slate-800 text-slate-100 placeholder-slate-500 rounded-full focus-visible:ring-sky-500 focus-visible:border-sky-500"
            />
          </div>

          {/* Controls Row */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-slate-400">
              {loading ? "Loading projects..." : `${sortedProjects.length} project${sortedProjects.length === 1 ? "" : "s"}`}
            </h2>
            <div className="flex items-center gap-2">
              {/* <Button
                onClick={() => setIsCreateProjectOpen(true)}
                className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold rounded-md inline-flex items-center"
                size="sm"
              >
                <Plus className="h-4 w-4 mr-1" /> New Project
              </Button>
              <Link href="/?new=true" className={cn(buttonVariants({ size: "sm" }), "bg-sky-400 hover:bg-sky-500 text-slate-950 font-semibold rounded-md inline-flex items-center")}>
                <Plus className="h-4 w-4 mr-1" /> New Notebook
              </Link> */}
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="bg-slate-900 border border-slate-800 text-slate-300 rounded-md py-1 px-3 text-xs outline-none focus:border-sky-500 cursor-pointer"
              >
                <option value="updated">Last edited</option>
                <option value="title">Title A–Z</option>
              </select>
            </div>
          </div>

          {/* Projects Grid */}
          {error ? (
            <div className="text-center py-12 bg-slate-900/50 rounded-lg border border-slate-800 text-red-400">
              <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-80" />
              <p>Could not load projects: {error}</p>
            </div>
          ) : loading && sortedProjects.length === 0 ? (
            <div className="text-center py-12 text-slate-500 flex flex-col items-center justify-center gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-sky-400" />
              <span>Loading projects…</span>
            </div>
          ) : sortedProjects.length === 0 ? (
            <div className="text-center py-16 bg-slate-900/40 rounded-lg border border-slate-900 flex flex-col items-center justify-center">
              <span className="text-4xl mb-3 opacity-30">📁</span>
              <p className="text-slate-400 text-sm mb-4">No projects found.</p>
              <Button onClick={() => setIsCreateProjectOpen(true)} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "border-slate-800 hover:bg-slate-800 inline-flex items-center")}>
                Create your first project →
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {sortedProjects.map((proj) => (
                <Card 
                  key={proj.id} 
                  className="bg-slate-900 hover:bg-slate-850 border-slate-800 hover:border-slate-700 transition-all cursor-pointer group relative overflow-hidden"
                  onClick={() => handleSelectProject(proj.id, proj.name)}
                >
                  <CardContent className="p-4 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2 bg-slate-950 rounded-md text-emerald-400/80 group-hover:text-emerald-400 transition-colors">
                        <FolderClosed className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-slate-200 group-hover:text-slate-100 truncate">
                          {proj.name || "Untitled Project"}
                        </h3>
                        <p className="text-xs text-slate-500 mt-0.5 truncate">
                          Updated: {proj.updated_at ? formatDate(proj.updated_at) : (proj.created_at ? formatDate(proj.created_at) : "N/A")}
                        </p>
                      </div>
                    </div>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500 hover:text-slate-200 hover:bg-slate-850 rounded-md flex-shrink-0">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="bg-slate-900 border-slate-800 text-slate-300">
                        <DropdownMenuItem 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectProject(proj.id, proj.name);
                          }}
                          className="hover:bg-slate-800 hover:text-slate-100 cursor-pointer"
                        >
                          <FolderOpen className="h-4 w-4 mr-2" /> Open Project
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* Create Project Dialog */}
      <Dialog open={isCreateProjectOpen} onOpenChange={(open) => !open && setIsCreateProjectOpen(false)}>
        <DialogContent className="bg-slate-900 border-slate-800 text-slate-100">
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div>
              <Label htmlFor="project-name-input" className="text-slate-400 mb-2 block">Project Name</Label>
              <Input
                id="project-name-input"
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
    </div>
  );
}
