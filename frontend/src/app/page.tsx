"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { fetchInvestigations } from "@/lib/api";
import { InvestigationSummary } from "@/types";
import {
  ShieldCheck,
  Bug,
  CheckCircle,
  Clock,
  DollarSign,
  ArrowRight,
  RefreshCw,
  Search,
} from "lucide-react";

export default function Dashboard() {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await fetchInvestigations();
      setInvestigations(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load investigations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const total = investigations.length;
  const validated = investigations.filter((i) => i.verdict === "validated").length;
  const validationRate = total > 0 ? ((validated / total) * 100).toFixed(1) : "0.0";
  const avgDuration =
    total > 0
      ? (
          investigations.reduce((acc, curr) => acc + curr.total_duration_seconds, 0) /
          total
        ).toFixed(2)
      : "0.00";

  return (
    <div className="space-y-8">
      {/* Hero Banner */}
      <div className="rounded-2xl border border-border bg-gradient-to-r from-blue-950/40 via-surface to-surface p-8 shadow-2xl relative overflow-hidden">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 text-xs font-semibold mb-4 border border-blue-500/20">
            <ShieldCheck className="w-3.5 h-3.5" />
            Autonomous Evidence-Checked Debugger
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-3">
            Honest, Mechanically Verified Python Debugging
          </h1>
          <p className="text-gray-300 text-sm sm:text-base leading-relaxed mb-6">
            Investigate failures, formulate root-cause hypotheses with verified code quotes,
            execute controlled sandbox experiments, and validate fixes without hallucinations.
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <Link
              href="/investigate/new"
              className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition shadow-lg shadow-blue-600/30 flex items-center gap-2"
            >
              Start Investigation
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/evaluation"
              className="px-5 py-2.5 rounded-lg border border-border bg-surfaceLight hover:bg-slate-700 text-gray-200 text-sm font-semibold transition"
            >
              View Benchmark Results
            </Link>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl border border-border bg-surface shadow-md">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium mb-1">
            <span>Total Investigated</span>
            <Bug className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-black text-white">{total}</div>
        </div>

        <div className="p-5 rounded-xl border border-border bg-surface shadow-md">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium mb-1">
            <span>Fix Validated Rate</span>
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-emerald-400">{validationRate}%</div>
        </div>

        <div className="p-5 rounded-xl border border-border bg-surface shadow-md">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium mb-1">
            <span>Avg Latency</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-black text-white">{avgDuration}s</div>
        </div>

        <div className="p-5 rounded-xl border border-border bg-surface shadow-md">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium mb-1">
            <span>Evidence Verification</span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-black text-purple-400">100%</div>
        </div>
      </div>

      {/* Investigations Table */}
      <div className="rounded-xl border border-border bg-surface shadow-xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="text-lg font-bold text-white">Recent Investigations</h2>
            <p className="text-xs text-gray-400">Historical bug investigations and verdict reports</p>
          </div>
          <button
            onClick={loadData}
            className="p-2 rounded-lg hover:bg-surfaceLight text-gray-400 hover:text-white transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading investigations...</div>
        ) : error ? (
          <div className="p-12 text-center text-rose-400">{error}</div>
        ) : investigations.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            No investigations recorded yet. Click "Start Investigation" to begin.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-surfaceLight/50 text-gray-400 text-xs uppercase tracking-wider border-b border-border">
                <tr>
                  <th className="px-6 py-3">Error &amp; Location</th>
                  <th className="px-6 py-3">Verdict</th>
                  <th className="px-6 py-3">Duration</th>
                  <th className="px-6 py-3">Cost</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {investigations.map((item) => (
                  <tr key={item.id} className="hover:bg-surfaceLight/30 transition">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-white">{item.error_type}</div>
                      <div className="text-xs text-gray-400 font-mono line-clamp-1">
                        {item.file}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                          item.verdict === "validated"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : item.verdict === "needs_human_decision"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        }`}
                      >
                        {item.verdict.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-300">
                      {item.total_duration_seconds.toFixed(2)}s
                    </td>
                    <td className="px-6 py-4 text-emerald-400 font-mono">
                      ${item.total_cost_usd.toFixed(4)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link
                        href={`/investigations/${item.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-surfaceLight hover:bg-blue-600 text-xs font-semibold text-white transition"
                      >
                        Details
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
