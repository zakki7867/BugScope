import React from "react";
import Link from "next/link";
import { Terminal, Compass, BarChart3, FolderGit2, ShieldCheck } from "lucide-react";

export const Navbar: React.FC = () => {
  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="font-extrabold text-xl tracking-tight text-white">BugScope</span>
            <span className="ml-2 px-1.5 py-0.5 text-xs font-medium rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
              AI Debugger
            </span>
          </div>
        </Link>

        <nav className="flex items-center gap-1 sm:gap-4 text-sm font-medium">
          <Link
            href="/"
            className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-surfaceLight text-gray-300 hover:text-white transition"
          >
            <Compass className="w-4 h-4" />
            Dashboard
          </Link>
          <Link
            href="/investigate/new"
            className="flex items-center gap-2 px-3 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white font-semibold transition shadow-md shadow-blue-600/20"
          >
            <Terminal className="w-4 h-4" />
            New Investigation
          </Link>
          <Link
            href="/repositories"
            className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-surfaceLight text-gray-300 hover:text-white transition"
          >
            <FolderGit2 className="w-4 h-4" />
            Explorer
          </Link>
          <Link
            href="/evaluation"
            className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-surfaceLight text-gray-300 hover:text-white transition"
          >
            <BarChart3 className="w-4 h-4" />
            Benchmark
          </Link>
        </nav>
      </div>
    </header>
  );
};
