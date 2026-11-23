"use client";

import React, { useState } from "react";
import { DiffEditor } from "@monaco-editor/react";
import { Copy, Check, Split, Rows } from "lucide-react";

interface MonacoDiffViewerProps {
  originalCode: string;
  modifiedCode: string;
  language?: string;
  filename?: string;
}

export const MonacoDiffViewer: React.FC<MonacoDiffViewerProps> = ({
  originalCode,
  modifiedCode,
  language = "python",
  filename,
}) => {
  const [isSideBySide, setIsSideBySide] = useState(true);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(modifiedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden shadow-2xl">
      <div className="flex items-center justify-between px-4 py-2.5 bg-surfaceLight border-b border-border text-sm">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
            {filename || "patch.py"}
          </span>
          <span className="text-xs text-gray-400">Proposed Minimal Patch</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsSideBySide(!isSideBySide)}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded bg-surface hover:bg-slate-700 text-gray-300 transition"
          >
            {isSideBySide ? <Rows className="w-3.5 h-3.5" /> : <Split className="w-3.5 h-3.5" />}
            {isSideBySide ? "Inline View" : "Side-by-Side"}
          </button>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded bg-surface hover:bg-slate-700 text-gray-300 transition"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied!" : "Copy Patched Code"}
          </button>
        </div>
      </div>

      <div className="h-[460px]">
        <DiffEditor
          height="100%"
          language={language}
          original={originalCode}
          modified={modifiedCode}
          theme="vs-dark"
          options={{
            readOnly: true,
            renderSideBySide: isSideBySide,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            automaticLayout: true,
          }}
        />
      </div>
    </div>
  );
};
