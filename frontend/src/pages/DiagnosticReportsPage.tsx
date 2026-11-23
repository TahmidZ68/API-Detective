import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Check, Copy, Download, FileCode, FileJson, FileText } from "lucide-react";
import { apiClient } from "../services/apiClient";

export const DiagnosticReportsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [format, setFormat] = useState<"json" | "markdown" | "html">("markdown");
  const [copied, setCopied] = useState(false);

  const listQuery = useQuery({
    queryKey: ["investigations"],
    queryFn: () => apiClient.listInvestigations(50),
  });

  const selectedId =
    searchParams.get("id") || listQuery.data?.[0]?.investigation_id || "";

  const exportQuery = useQuery({
    queryKey: ["report-export", selectedId, format],
    queryFn: () => apiClient.exportReport(selectedId, format),
    enabled: Boolean(selectedId),
  });

  const handleCopy = async () => {
    if (!exportQuery.data) return;
    await navigator.clipboard.writeText(exportQuery.data);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!exportQuery.data || !selectedId) return;
    const ext = format === "markdown" ? "md" : format;
    const mime =
      format === "json"
        ? "application/json"
        : format === "html"
        ? "text/html"
        : "text/markdown";
    const blob = new Blob([exportQuery.data], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedId}-report.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            Diagnostic Reports & Export
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Export reproducible, secret-redacted diagnostic reports in JSON, Markdown, or standalone HTML.
          </p>
        </div>

        {listQuery.data && listQuery.data.length > 0 && (
          <select
            aria-label="Select investigation report"
            value={selectedId}
            onChange={(e) => setSearchParams({ id: e.target.value })}
            className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200"
          >
            {listQuery.data.map((inv) => (
              <option key={inv.investigation_id} value={inv.investigation_id}>
                {inv.investigation_id} — {inv.title}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Format Tabs & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-[#0b1120] border border-slate-800/90">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setFormat("json")}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors ${
              format === "json"
                ? "bg-blue-600 text-white"
                : "bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800"
            }`}
          >
            <FileJson className="w-3.5 h-3.5" />
            <span>JSON</span>
          </button>
          <button
            type="button"
            onClick={() => setFormat("markdown")}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors ${
              format === "markdown"
                ? "bg-blue-600 text-white"
                : "bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Markdown</span>
          </button>
          <button
            type="button"
            onClick={() => setFormat("html")}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors ${
              format === "html"
                ? "bg-blue-600 text-white"
                : "bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800"
            }`}
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>Standalone HTML</span>
          </button>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={handleCopy}
            disabled={!exportQuery.data}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy Report</span>
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={!exportQuery.data}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download .{format === "markdown" ? "md" : format}</span>
          </button>
        </div>
      </div>

      {/* Report Preview */}
      <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90">
        {exportQuery.isLoading ? (
          <div className="h-64 animate-pulse bg-slate-900 rounded-lg" />
        ) : (
          <pre
            data-testid="report-preview"
            className="p-4 rounded-lg bg-[#050811] border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto max-h-[540px]"
          >
            <code>{exportQuery.data || "No report content available."}</code>
          </pre>
        )}
      </div>
    </div>
  );
};
