import React from "react";
import { AlertTriangle, UserCheck, HelpCircle } from "lucide-react";

interface DecisionOption {
  choice: string;
  description: string;
}

interface HumanDecisionCardProps {
  reason: string;
  options?: DecisionOption[];
}

export const HumanDecisionCard: React.FC<HumanDecisionCardProps> = ({ reason, options }) => {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 shadow-xl mb-6">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-amber-300">
            Human Decision Required (Ambiguous Intent)
          </h3>
          <p className="text-sm text-gray-300 mt-1 leading-relaxed">
            {reason || "Multiple distinct interpretations of expected behavior exist in the codebase."}
          </p>
        </div>
      </div>

      {options && options.length > 0 && (
        <div className="mt-5 space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400/80">
            Architectural Options Evaluated:
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            {options.map((opt, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-lg border border-border bg-surfaceLight/80 text-sm hover:border-amber-500/40 transition"
              >
                <div className="flex items-center gap-2 font-bold text-white mb-1">
                  <HelpCircle className="w-4 h-4 text-amber-400" />
                  Option {opt.choice}
                </div>
                <p className="text-xs text-gray-300 leading-normal">{opt.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
