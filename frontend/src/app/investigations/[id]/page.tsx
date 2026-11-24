"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchInvestigationById, fetchInvestigationGraph } from "@/lib/api";
import { InvestigationReport } from "@/types";
import { InvestigationGraph } from "@/components/InvestigationGraph";
import { MonacoDiffViewer } from "@/components/MonacoDiffViewer";
import { EvidenceCard } from "@/components/EvidenceCard";
import { HumanDecisionCard } from "@/components/HumanDecisionCard";
import {
  ShieldCheck,
  Clock,
  DollarSign,
  Activity,
  GitBranch,
  Layers,
  FileCheck2,
  Terminal,
  Download,
  AlertCircle,
  FlaskConical,
  CheckCircle,
  RefreshCw,
} from "lucide-react";

export default function InvestigationDetails() {
  const { id } = useParams() as { id: string };
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [graphData, setGraphData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"graph" | "hypotheses" | "experiments" | "patch" | "validation" | "traces">("graph");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applyingPatch, setApplyingPatch] = useState(false);
  const [patchApplied, setPatchApplied] = useState(false);
  const [patchActionMsg, setPatchActionMsg] = useState<string | null>(null);

  const handleApplyPatch = async () => {
    try {
      setApplyingPatch(true);
      setPatchActionMsg(null);
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";
      const targetDir =
        (report as any)?.repository_path ||
        (report?.context_bundle as any)?.repo_dir ||
        (report?.failure_report?.file?.includes("/") ? report.failure_report.file.substring(0, report.failure_report.file.lastIndexOf("/")) : ".");
      const res = await fetch(`${API_BASE}/patches/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          investigation_id: id,
          target_repo_dir: targetDir,
          user_approved: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to apply patch.");
      setPatchApplied(true);
      setPatchActionMsg(data.message);
    } catch (err: any) {
      setPatchActionMsg(`Error: ${err.message}`);
    } finally {
      setApplyingPatch(false);
    }
  };

  const handleRollbackPatch = async () => {
    try {
      setApplyingPatch(true);
      setPatchActionMsg(null);
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";
      const targetDir =
        (report as any)?.repository_path ||
        (report?.context_bundle as any)?.repo_dir ||
        (report?.failure_report?.file?.includes("/") ? report.failure_report.file.substring(0, report.failure_report.file.lastIndexOf("/")) : ".");
      const res = await fetch(`${API_BASE}/patches/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          investigation_id: id,
          target_repo_dir: targetDir,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to rollback patch.");
      setPatchApplied(false);
      setPatchActionMsg(data.message);
    } catch (err: any) {
      setPatchActionMsg(`Error: ${err.message}`);
    } finally {
      setApplyingPatch(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    Promise.all([fetchInvestigationById(id), fetchInvestigationGraph(id)])
      .then(([rep, graph]) => {
        setReport(rep);
        setGraphData(graph);
      })
      .catch((err) => setError(err.message || "Failed to load investigation"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="p-16 text-center text-gray-400">Loading investigation report...</div>;
  }

  if (error || !report) {
    return <div className="p-16 text-center text-rose-400">{error || "Investigation not found"}</div>;
  }

  const topH = report.top_hypothesis;
  const fix = report.fix_proposal;
  const val = report.validation_report;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="rounded-xl border border-border bg-surface p-6 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-white">{report.failure_report.error_type}</h1>
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                report.verdict === "validated"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : report.verdict === "needs_human_decision"
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
              }`}
            >
              {report.verdict.replace(/_/g, " ")}
            </span>
          </div>
          <p className="text-xs font-mono text-gray-400 mt-1">
            {report.failure_report.file}:{report.failure_report.line} &bull; {report.failure_report.message}
          </p>
        </div>

        <div className="flex items-center gap-6 text-sm">
          <div>
            <div className="text-xs text-gray-400">Duration</div>
            <div className="font-bold text-white flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-blue-400" />
              {report.total_duration_seconds.toFixed(2)}s
            </div>
          </div>

          <div>
            <div className="text-xs text-gray-400">LLM Cost</div>
            <div className="font-mono font-bold text-emerald-400">
              ${report.total_cost_usd.toFixed(4)}
            </div>
          </div>

          <a
            href={`http://127.0.0.1:8000/api/reports/${id}?format=markdown`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-surfaceLight hover:bg-slate-700 text-xs font-semibold text-white transition"
          >
            <Download className="w-3.5 h-3.5" />
            Markdown
          </a>
        </div>
      </div>

      {/* Ambiguous Human Decision Alert */}
      {fix?.status === "needs_human_decision" && (
        <HumanDecisionCard
          reason={fix.human_decision_reason || ""}
          options={fix.decision_options}
        />
      )}

      {/* Tabs Navigation */}
      <div className="flex border-b border-border gap-2 text-sm">
        {[
          { id: "graph", label: "Workflow Graph", icon: Activity },
          { id: "hypotheses", label: `Hypotheses (${report.hypotheses.length})`, icon: Layers },
          { id: "experiments", label: `Experiments (${report.experiments?.length || 0})`, icon: FlaskConical },
          { id: "patch", label: "Patch & Diff", icon: GitBranch },
          { id: "validation", label: "3-Phase Validation", icon: FileCheck2 },
          { id: "traces", label: "Telemetry Traces", icon: Terminal },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2.5 font-semibold border-b-2 transition -mb-px text-xs sm:text-sm ${
                isActive
                  ? "border-blue-500 text-blue-400 bg-blue-500/5"
                  : "border-transparent text-gray-400 hover:text-white"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      {activeTab === "graph" && (
        <div>
          <InvestigationGraph graphData={graphData} />
        </div>
      )}

      {activeTab === "hypotheses" && (
        <div className="space-y-6">
          {report.hypotheses.map((h) => (
            <div
              key={h.id}
              className={`rounded-xl border p-6 shadow-xl ${
                h.rank === 1
                  ? "border-blue-500/50 bg-blue-950/20"
                  : "border-border bg-surface"
              }`}
            >
              <div className="flex items-center justify-between gap-4 mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-black text-sm px-2 py-0.5 rounded bg-blue-600 text-white">
                    Rank #{h.rank}
                  </span>
                  <h3 className="font-bold text-lg text-white">{h.title}</h3>
                  {h.is_upstream && (
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      Upstream Cause
                    </span>
                  )}
                </div>

                <div className="text-xs font-semibold text-emerald-400 font-mono">
                  Score: +{h.score} ({h.label})
                </div>
              </div>

              <p className="text-sm text-gray-300 mb-4 leading-relaxed">{h.explanation}</p>

              <h4 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">
                Code Evidence Items ({h.evidence.length})
              </h4>
              <div className="space-y-3">
                {h.evidence.map((ev, idx) => (
                  <EvidenceCard key={idx} evidence={ev} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === "experiments" && (
        <div className="space-y-4">
          {(!report.experiments || report.experiments.length === 0) ? (
            <div className="p-12 text-center text-gray-400 border border-border rounded-xl">
              No empirical experiments recorded.
            </div>
          ) : (
            report.experiments.map((exp, idx) => (
              <div key={idx} className="rounded-xl border border-border bg-surface p-5 shadow-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-blue-400 font-mono">
                    Hypothesis #{exp.hypothesis_id} &bull; {exp.experiment_type}
                  </span>
                  <span
                    className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                      exp.conclusion === "confirmed"
                        ? "bg-emerald-500/10 text-emerald-400"
                        : "bg-gray-500/10 text-gray-400"
                    }`}
                  >
                    Conclusion: {exp.conclusion}
                  </span>
                </div>
                <div className="font-mono text-xs bg-slate-950 p-2.5 rounded border border-slate-800 text-slate-300 mb-2">
                  $ {exp.command}
                </div>
                {exp.stdout && (
                  <pre className="font-mono text-xs text-slate-400 bg-slate-950/60 p-3 rounded max-h-48 overflow-y-auto">
                    {exp.stdout}
                  </pre>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "patch" && (
        <div className="space-y-4">
          {fix?.diff ? (
            <div>
              <div className="mb-4 text-sm text-gray-300">
                <strong className="text-white">Explanation:</strong> {fix.explanation}
              </div>
              <MonacoDiffViewer
                originalCode="# Original source code prior to patch application"
                modifiedCode={fix.diff}
                language="diff"
                filename={report.failure_report.file}
              />

              {/* User Approval & Rollback Action Controls */}
              <div className="mt-4 p-4 rounded-xl border border-border bg-surfaceLight/60 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-bold text-white flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    Patch Application Control (User Approval Required)
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Atomic application with pre-patch file backups and instant rollback protection.
                  </p>
                  {patchActionMsg && (
                    <div className="text-xs font-semibold text-blue-400 mt-2 font-mono">
                      {patchActionMsg}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  {!patchApplied ? (
                    <button
                      onClick={handleApplyPatch}
                      disabled={applyingPatch}
                      className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition shadow-lg shadow-emerald-600/30 flex items-center gap-2 disabled:opacity-50"
                    >
                      <CheckCircle className="w-4 h-4" />
                      {applyingPatch ? "Applying..." : "Approve & Apply Patch"}
                    </button>
                  ) : (
                    <button
                      onClick={handleRollbackPatch}
                      disabled={applyingPatch}
                      className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition shadow-lg shadow-amber-600/30 flex items-center gap-2 disabled:opacity-50"
                    >
                      <RefreshCw className="w-4 h-4" />
                      {applyingPatch ? "Reverting..." : "Rollback Applied Patch"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-gray-400 border border-border rounded-xl">
              No patch generated (e.g. human decision required or failure unsupported).
            </div>
          )}
        </div>
      )}

      {activeTab === "validation" && (
        <div className="rounded-xl border border-border bg-surface p-6 shadow-xl space-y-6">
          <h3 className="text-lg font-bold text-white">3-Phase Sandbox Validation</h3>
          {val ? (
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="p-4 rounded-lg bg-surfaceLight border border-border">
                <div className="text-xs text-gray-400 mb-1">Phase 1: Pre-Fix Reproduction</div>
                <div className="text-base font-bold text-emerald-400">
                  {val.reproduced_before ? "PASS (Reproduced)" : "FAIL"}
                </div>
              </div>

              <div className="p-4 rounded-lg bg-surfaceLight border border-border">
                <div className="text-xs text-gray-400 mb-1">Phase 2: Post-Patch Regression Pass</div>
                <div className="text-base font-bold text-emerald-400">
                  {val.regression_passes_after ? "PASS (Passed)" : "FAIL"}
                </div>
              </div>

              <div className="p-4 rounded-lg bg-surfaceLight border border-border">
                <div className="text-xs text-gray-400 mb-1">Phase 3: Zero Existing Regressions</div>
                <div className="text-base font-bold text-emerald-400">
                  {val.existing_suite_passes_after ? "PASS (No Regressions)" : "FAIL"}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-gray-400">Validation was skipped.</div>
          )}
        </div>
      )}

      {activeTab === "traces" && (
        <div className="rounded-xl border border-border bg-surface overflow-hidden shadow-xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-surfaceLight/70 text-gray-400 uppercase tracking-wider border-b border-border">
              <tr>
                <th className="px-4 py-3">Node</th>
                <th className="px-4 py-3">Input</th>
                <th className="px-4 py-3">Output</th>
                <th className="px-4 py-3">Latency</th>
                <th className="px-4 py-3">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {report.traces.map((tr, idx) => (
                <tr key={idx} className="hover:bg-surfaceLight/30 font-mono">
                  <td className="px-4 py-3 font-bold text-white">{tr.node}</td>
                  <td className="px-4 py-3 text-gray-300">{tr.input_summary}</td>
                  <td className="px-4 py-3 text-gray-300">{tr.output_summary}</td>
                  <td className="px-4 py-3 text-gray-400">{tr.duration_ms.toFixed(0)}ms</td>
                  <td className="px-4 py-3 text-emerald-400">
                    {tr.cost_usd > 0 ? `$${tr.cost_usd.toFixed(4)}` : "$0.00"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
