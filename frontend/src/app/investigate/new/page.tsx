"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { startInvestigation, fetchRepositories } from "@/lib/api";
import { Play, Sparkles, Upload, FileCode2, AlertCircle, CheckCircle } from "lucide-react";

export default function NewInvestigation() {
  const router = useRouter();
  const [rawTrace, setRawTrace] = useState("");
  const [repoDir, setRepoDir] = useState("");
  const [testCommand, setTestCommand] = useState("");
  const [repositories, setRepositories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRepositories()
      .then((data) => setRepositories(data.repositories || []))
      .catch(() => {});
  }, []);

  const handleSelectBug = (bug: any) => {
    setRepoDir(bug.path);
    // Auto-fill a representative stack trace for benchmark bug
    setRawTrace(`Traceback (most recent call last):
  File "tests/test_main.py", line 14, in test_failure
    assert run_target() == expected
AssertionError: Bug triggered in ${bug.name}`);
    setTestCommand(`pytest ${bug.path}/tests/`);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawTrace.trim()) {
      setError("Please paste a stack trace or error message.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const res = await startInvestigation({
        raw_trace: rawTrace,
        repo_dir: repoDir || undefined,
        test_command: testCommand || undefined,
      });

      router.push(`/investigations/${res.investigation_id}`);
    } catch (err: any) {
      setError(err.message || "Failed to run investigation.");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold text-white">Start New Investigation</h1>
        <p className="text-sm text-gray-400 mt-1">
          Supply an error trace and optional repository path to begin evidence-checked root-cause analysis.
        </p>
      </div>

      {/* Benchmark Presets */}
      {repositories.length > 0 && (
        <div className="rounded-xl border border-border bg-surface p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4 font-bold text-sm text-white">
            <Sparkles className="w-4 h-4 text-blue-400" />
            <span>Select Seeded Benchmark Bug (Quick Load)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 max-h-56 overflow-y-auto p-1">
            {repositories.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => handleSelectBug(b)}
                className="text-left p-3 rounded-lg border border-border bg-surfaceLight/70 hover:border-blue-500 hover:bg-surfaceLight transition text-xs"
              >
                <div className="font-bold text-white truncate">{b.name}</div>
                <div className="text-[11px] text-blue-400 font-mono mt-0.5">{b.category}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main Form */}
      <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-surface p-6 shadow-xl space-y-6">
        {error && (
          <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-sm font-bold text-white mb-2">
            Stack Trace or Error Message <span className="text-rose-400">*</span>
          </label>
          <textarea
            value={rawTrace}
            onChange={(e) => setRawTrace(e.target.value)}
            rows={8}
            placeholder="Paste Python traceback, KeyError, TypeError, or failing pytest block here..."
            className="w-full rounded-lg border border-border bg-slate-950 p-4 font-mono text-xs text-slate-200 focus:outline-none focus:border-blue-500 transition"
            required
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-bold text-white mb-2">
              Repository Directory Path (Optional)
            </label>
            <input
              type="text"
              value={repoDir}
              onChange={(e) => setRepoDir(e.target.value)}
              placeholder="e.g. sample_bugs/bug_01_key_error or local path"
              className="w-full rounded-lg border border-border bg-slate-950 px-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 transition"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-white mb-2">
              Failing Test Command (Optional)
            </label>
            <input
              type="text"
              value={testCommand}
              onChange={(e) => setTestCommand(e.target.value)}
              placeholder="e.g. pytest tests/test_user.py"
              className="w-full rounded-lg border border-border bg-slate-950 px-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 transition"
            />
          </div>
        </div>

        <div className="pt-4 border-t border-border flex items-center justify-between">
          <div className="text-xs text-gray-400 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            Deterministic AST + Mechanical Code Quotes Verification Enabled
          </div>

          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm transition shadow-lg shadow-blue-600/30 flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>Running LangGraph Engine...</>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                Run Investigation
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
