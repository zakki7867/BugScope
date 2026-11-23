export interface FailureReport {
  error_type: string;
  message: string;
  file: string;
  line: number;
  function: string;
  call_chain: Array<{
    file: string;
    line: number;
    function: string;
    code?: string;
  }>;
  category: string;
  severity: string;
}

export interface EvidenceItem {
  file: string;
  line_start: number;
  line_end: number;
  quote: string;
  stance: "supports" | "contradicts";
  reason: string;
  verified: boolean;
}

export interface RankedHypothesis {
  id: number;
  title: string;
  explanation: string;
  evidence: EvidenceItem[];
  score: number;
  label: "supported" | "unsupported";
  is_upstream: boolean;
  rank: number;
  verified_support_count: number;
  verified_contradict_count: number;
  discarded_evidence_count: number;
}

export interface ExperimentResult {
  hypothesis_id: number;
  experiment_type: string;
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  success: boolean;
  conclusion: "confirmed" | "refuted" | "inconclusive";
  notes?: string;
}

export interface FixProposal {
  status: "patch_generated" | "needs_human_decision";
  diff: string;
  explanation: string;
  human_decision_reason?: string;
  decision_options?: Array<{
    choice: string;
    description: string;
  }>;
}

export interface ValidationReport {
  verdict: "validated" | "partially_validated" | "not_validated" | "could_not_reproduce" | "needs_human_decision";
  reproduced_before: boolean;
  patch_applies: boolean;
  regression_passes_after: boolean;
  existing_suite_passes_after: boolean;
  retries_attempted: number;
  failure_log?: string;
}

export interface TraceEntry {
  node: string;
  input_summary: string;
  output_summary: string;
  duration_ms: float;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

export interface InvestigationReport {
  investigation_id: string;
  created_at: string;
  failure_report: FailureReport;
  hypotheses: RankedHypothesis[];
  top_hypothesis?: RankedHypothesis;
  experiments: ExperimentResult[];
  fix_proposal?: FixProposal;
  validation_report?: ValidationReport;
  traces: TraceEntry[];
  verdict: string;
  total_duration_seconds: number;
  total_cost_usd: number;
  total_tokens_in: number;
  total_tokens_out: number;
}

export interface InvestigationSummary {
  id: string;
  created_at: string;
  verdict: string;
  error_type: string;
  message: string;
  file: string;
  total_duration_seconds: number;
  total_cost_usd: number;
}
