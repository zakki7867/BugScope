import React from "react";
import { EvidenceItem } from "@/types";
import { CheckCircle2, XCircle, ArrowUpRight, ArrowDownRight } from "lucide-react";

interface EvidenceCardProps {
  evidence: EvidenceItem;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ evidence }) => {
  const isSupporting = evidence.stance === "supports";

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 transition hover:border-slate-700">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          {evidence.verified ? (
            <span className="flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Verified On-Disk
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <XCircle className="w-3.5 h-3.5" />
              Discarded (Mismatch/Hallucinated)
            </span>
          )}

          <span
            className={`flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded ${
              isSupporting
                ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
            }`}
          >
            {isSupporting ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
            {evidence.stance.toUpperCase()}
          </span>
        </div>

        <span className="font-mono text-xs text-slate-400">
          {evidence.file}:{evidence.line_start}-{evidence.line_end}
        </span>
      </div>

      <pre className="p-3 my-2 bg-slate-950 rounded-md font-mono text-xs text-slate-200 border border-slate-800/80 overflow-x-auto whitespace-pre-wrap">
        {evidence.quote}
      </pre>

      <p className="text-xs text-slate-300 mt-2">
        <strong className="text-slate-400">Reason:</strong> {evidence.reason}
      </p>
    </div>
  );
};
