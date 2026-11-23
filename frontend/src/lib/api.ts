import { InvestigationReport, InvestigationSummary } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

export async function fetchInvestigations(): Promise<InvestigationSummary[]> {
  const res = await fetch(`${API_BASE}/investigations`);
  if (!res.ok) throw new Error("Failed to fetch investigations");
  return res.json();
}

export async function fetchInvestigationById(id: string): Promise<InvestigationReport> {
  const res = await fetch(`${API_BASE}/investigations/${id}`);
  if (!res.ok) throw new Error("Failed to fetch investigation details");
  return res.json();
}

export async function fetchInvestigationGraph(id: string) {
  const res = await fetch(`${API_BASE}/investigations/${id}/graph`);
  if (!res.ok) throw new Error("Failed to fetch investigation graph");
  return res.json();
}

export async function startInvestigation(data: {
  raw_trace: string;
  repo_dir?: string;
  test_command?: string;
}): Promise<InvestigationReport> {
  const res = await fetch(`${API_BASE}/investigations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to start investigation");
  }
  return res.json();
}

export async function fetchRepositories() {
  const res = await fetch(`${API_BASE}/repositories/list`);
  if (!res.ok) throw new Error("Failed to list repositories");
  return res.json();
}

export async function fetchEvaluationResults() {
  const res = await fetch(`${API_BASE}/evaluation/results`);
  if (!res.ok) throw new Error("Failed to fetch evaluation results");
  return res.json();
}

export async function fetchBenchmarks() {
  const res = await fetch(`${API_BASE}/evaluation/benchmarks`);
  if (!res.ok) throw new Error("Failed to fetch benchmarks");
  return res.json();
}
