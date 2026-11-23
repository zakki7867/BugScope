"use client";

import React, { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  NodeProps,
  Edge,
  Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CheckCircle2, Clock, Cpu, FileCode2, PlayCircle, AlertCircle } from "lucide-react";

interface NodeData {
  label: string;
  type: "deterministic" | "llm";
  status: "COMPLETED" | "RUNNING" | "SKIPPED" | "FAILED";
  duration_ms: number;
  cost_usd: number;
  output_summary?: string;
}

const CustomNode: React.FC<NodeProps<Node<NodeData>>> = ({ data }) => {
  const isLLM = data.type === "llm";
  const isCompleted = data.status === "COMPLETED";

  return (
    <div
      className={`px-4 py-3 rounded-xl border min-w-[210px] shadow-xl transition-all ${
        isCompleted
          ? "bg-slate-900 border-slate-700 text-white"
          : "bg-slate-950/60 border-slate-800 text-slate-400"
      }`}
    >
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-blue-500" />
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 font-bold text-sm">
          {isLLM ? <Cpu className="w-4 h-4 text-purple-400" /> : <FileCode2 className="w-4 h-4 text-blue-400" />}
          <span>{data.label}</span>
        </div>
        <span
          className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
            isLLM ? "bg-purple-500/20 text-purple-300" : "bg-blue-500/20 text-blue-300"
          }`}
        >
          {data.type}
        </span>
      </div>

      <div className="text-xs text-slate-400 line-clamp-1 mb-2">
        {data.output_summary || "Awaiting execution..."}
      </div>

      <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-800 text-slate-400">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {data.duration_ms ? `${data.duration_ms.toFixed(0)}ms` : "0ms"}
        </span>
        {data.cost_usd > 0 && (
          <span className="text-emerald-400 font-mono">
            ${data.cost_usd.toFixed(4)}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-blue-500" />
    </div>
  );
};

export const InvestigationGraph: React.FC<{ graphData: any }> = ({ graphData }) => {
  const nodeTypes = useMemo(() => ({ custom: CustomNode }), []);

  const nodes: Node<NodeData>[] = useMemo(() => {
    if (!graphData?.nodes) return [];

    const order = [
      "failure_analyzer",
      "repo_investigator",
      "reproducer",
      "hypothesis_generator",
      "evidence_verifier",
      "experiment_runner",
      "fix_generator",
      "test_generator",
      "validator",
      "report_builder",
    ];

    return order.map((id, index) => {
      const n = graphData.nodes.find((item: any) => item.id === id) || {
        id,
        label: id.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()),
        type: id.includes("generator") ? "llm" : "deterministic",
        status: "SKIPPED",
        duration_ms: 0,
        cost_usd: 0,
      };

      const x = 320;
      const y = index * 105 + 20;

      return {
        id: n.id,
        type: "custom",
        position: { x, y },
        data: {
          label: n.label,
          type: n.type,
          status: n.status,
          duration_ms: n.duration_ms,
          cost_usd: n.cost_usd,
          output_summary: n.output_summary,
        },
      };
    });
  }, [graphData]);

  const edges: Edge[] = useMemo(() => {
    if (!graphData?.edges) return [];
    return graphData.edges.map((e: any, idx: number) => ({
      id: `e-${idx}`,
      source: e.source,
      target: e.target,
      animated: true,
      style: { stroke: "#3b82f6", strokeWidth: 2 },
    }));
  }, [graphData]);

  return (
    <div className="w-full h-[620px] bg-slate-950 rounded-xl border border-slate-800 overflow-hidden relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-right"
      >
        <Background color="#1e293b" gap={16} />
        <Controls className="bg-slate-900 border-slate-700 text-white fill-white" />
      </ReactFlow>
    </div>
  );
};
