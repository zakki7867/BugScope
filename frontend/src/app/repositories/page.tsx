"use client";

import React, { useEffect, useState } from "react";
import { fetchRepositories } from "@/lib/api";
import { FolderGit2, FileText, Folder, Search, Code2 } from "lucide-react";

export default function RepositoryExplorer() {
  const [repositories, setRepositories] = useState<any[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<any | null>(null);
  const [tree, setTree] = useState<any[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);

  useEffect(() => {
    fetchRepositories().then((data) => {
      const repos = data.repositories || [];
      setRepositories(repos);
      if (repos.length > 0) {
        selectRepository(repos[0]);
      }
    });
  }, []);

  const selectRepository = async (repo: any) => {
    setSelectedRepo(repo);
    setSelectedFile(null);
    setFileContent("");
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/repositories/tree?path=${encodeURIComponent(repo.path)}`);
      const data = await res.json();
      setTree(data.tree || []);
    } catch {
      setTree([]);
    }
  };

  const loadFile = async (filePath: string) => {
    if (!selectedRepo) return;
    setSelectedFile(filePath);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/repositories/file?repo_path=${encodeURIComponent(
          selectedRepo.path
        )}&file_path=${encodeURIComponent(filePath)}`
      );
      const data = await res.json();
      setFileContent(data.content || "");
    } catch {
      setFileContent("// Error loading file");
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo || !searchQuery) return;
    try {
      const res = await fetch("http://127.0.0.1:8000/api/repositories/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_path: selectedRepo.path, query: searchQuery }),
      });
      const data = await res.json();
      setSearchResults(data.matches || []);
    } catch {
      setSearchResults([]);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-white">Repository Explorer</h1>
          <p className="text-sm text-gray-400 mt-1">
            Browse Python source files, AST symbols, and test suites across project repositories.
          </p>
        </div>

        <select
          value={selectedRepo?.path || ""}
          onChange={(e) => {
            const found = repositories.find((r) => r.path === e.target.value);
            if (found) selectRepository(found);
          }}
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
        >
          {repositories.map((r) => (
            <option key={r.path} value={r.path}>
              {r.name} ({r.category})
            </option>
          ))}
        </select>
      </div>

      {/* Main Grid: Tree + Code */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 h-[640px]">
        {/* Left Sidebar: Tree & Search */}
        <div className="md:col-span-4 rounded-xl border border-border bg-surface p-4 flex flex-col h-full shadow-xl">
          <form onSubmit={handleSearch} className="mb-4">
            <div className="relative">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search code symbols/regex..."
                className="w-full rounded-lg border border-border bg-slate-950 pl-9 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </form>

          {searchResults.length > 0 && (
            <div className="mb-4 p-2 bg-blue-500/10 rounded-lg border border-blue-500/20 max-h-40 overflow-y-auto text-xs">
              <div className="font-bold text-blue-400 mb-1">Search Results ({searchResults.length}):</div>
              {searchResults.map((m, idx) => (
                <div
                  key={idx}
                  onClick={() => loadFile(m.file)}
                  className="cursor-pointer py-1 hover:text-white truncate"
                >
                  <span className="font-mono text-gray-400">{m.file}:{m.line}</span> - {m.content}
                </div>
              ))}
            </div>
          )}

          <div className="flex-1 overflow-y-auto space-y-1 text-xs">
            <div className="font-bold text-gray-400 uppercase tracking-wider text-[11px] mb-2">
              Files ({tree.length})
            </div>
            {tree.map((item) => (
              <button
                key={item.path}
                onClick={() => !item.is_dir && loadFile(item.path)}
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded transition text-left truncate ${
                  selectedFile === item.path
                    ? "bg-blue-600 text-white font-semibold"
                    : "text-gray-300 hover:bg-surfaceLight"
                }`}
              >
                {item.is_dir ? (
                  <Folder className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                ) : (
                  <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                )}
                <span className="truncate">{item.path}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Right Pane: Code Viewer */}
        <div className="md:col-span-8 rounded-xl border border-border bg-surface flex flex-col h-full shadow-xl overflow-hidden">
          <div className="px-4 py-2.5 bg-surfaceLight border-b border-border flex items-center justify-between text-xs">
            <span className="font-mono text-blue-400">{selectedFile || "No file selected"}</span>
            <span className="text-gray-400">Python AST Viewer</span>
          </div>

          <div className="flex-1 bg-slate-950 p-4 font-mono text-xs overflow-auto text-slate-200">
            {selectedFile ? (
              <pre className="whitespace-pre-wrap">{fileContent}</pre>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">
                Select a file from the repository tree to view contents.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
