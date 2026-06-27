"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Plus, FolderOpen, Search } from "lucide-react";

interface ActivityBarProps {
  leftSidebarOpen: boolean;
  setLeftSidebarOpen: (open: boolean) => void;
  onNewNotebook?: () => void;
}

export default function ActivityBar({
  leftSidebarOpen,
  setLeftSidebarOpen,
  onNewNotebook,
}: ActivityBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const isProjects = pathname === "/projects";
  const isWorkspace = pathname === "/";

  const handleLogout = () => {
    if (typeof window !== "undefined") {
      if (confirm("Are you sure you want to log out?")) {
        localStorage.removeItem("isLoggedIn");
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        localStorage.removeItem("createdProjectId");
        localStorage.removeItem("createdFolderId");
        window.location.href = "/";
      }
    }
  };

  return (
    <aside className="w-[46px] bg-[#00081A] flex flex-col items-center py-3 gap-1 flex-shrink-0 z-40">
      {/* Q2 Logo */}
      <div className="w-8 h-8 flex items-center justify-center mb-2 select-none">
        <span className="font-extrabold text-[15px] leading-none">
          <span className="text-[#facc15]">Q</span>
          <span className="text-[#00bcd4]">2</span>
        </span>
      </div>

      {/* + New project */}
      <button
        onClick={() => (onNewNotebook ? onNewNotebook() : router.push("/?new=true"))}
        title="New project"
        className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors cursor-pointer ${
          isWorkspace && !leftSidebarOpen
            ? "text-slate-200 bg-slate-800/60"
            : "text-slate-500 hover:text-slate-200 hover:bg-slate-800/50"
        }`}
      >
        <Plus className="h-4 w-4" />
      </button>

      {/* Folder / Current Project toggle */}
      <button
        onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
        title="Current Project"
        className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors cursor-pointer ${
          isWorkspace && leftSidebarOpen
            ? "text-slate-200 bg-slate-800/60"
            : "text-slate-500 hover:text-slate-200 hover:bg-slate-800/50"
        }`}
      >
        <FolderOpen className="h-4 w-4" />
      </button>

      {/* Search / Projects */}
      <Link
        href="/projects"
        title="Projects"
        className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors ${
          isProjects
            ? "text-slate-200 bg-slate-800/60"
            : "text-slate-500 hover:text-slate-200 hover:bg-slate-800/50"
        }`}
      >
        <Search className="h-4 w-4" />
      </Link>

      {/* Spacer */}
      <div className="flex-1" />

      {/* User avatar */}
      <button
        onClick={handleLogout}
        className="h-7 w-7 rounded-full bg-pink-600 flex items-center justify-center border border-pink-700/60 cursor-pointer"
        title="Log out"
      >
        <span className="text-[11px] font-bold text-white uppercase leading-none">M</span>
      </button>
    </aside>
  );
}
