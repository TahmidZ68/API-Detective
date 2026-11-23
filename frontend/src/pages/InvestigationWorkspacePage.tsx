import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CheckCircle2,
  ChevronRight,
  Clock,
  FileCode,
  FileDown,
  GitPullRequestDraft,
  Layers,
  ShieldCheck,
  Terminal,
  Wrench,
  XCircle,
} from "lucide-react";
import { apiClient } from "../services/apiClient";
import { SeverityBadge, StatusPill } from "../components/SeverityBadge";
import type { RemediationPlanItem } from "../types/api";

export const InvestigationWorkspacePage: React.FC = () => {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmFix, setConfirmFix] = useState<RemediationPlanItem | null>(null);

  const listQuery = useQuery({
    queryKey: ["investigations"],
    queryFn: () => apiClient.listInvestigations(50),
  });

  const activeId = id || listQuery.data?.[0]?.investigation_id;

  const detailQuery = useQuery({
    queryKey: ["investigation", activeId],
    queryFn: () => apiClient.getInvestigation(activeId!),
    enabled: Boolean(activeId),
  });

  const approveMutation = useMutation({
    mutationFn: (fixId: string) => apiClient.approveFix(activeId!, fixId, true, true),
    onSuccess: (updated) => {
      setConfirmFix(null);
      queryClient.setQueryData(["investigation", activeId], updated);
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
  });

  if (listQuery.isLoading || detailQuery.isLoading) {
    return (
      <div className="space-y-4 animate-pulse" data-testid="workspace-loading">
        <div className="h-10 w-80 bg-slate-800 rounded" />
        <div className="h-64 bg-slate-900 border border-slate-800 rounded-xl" />
      </div>
    );
  }

  const report = detailQuery.data;

  if (!report) {
    return (
      <div className="p-8 rounded-xl bg-[#0b1120] border border-slate-800 text-center space-y-3">
        <p className="text-slate-300 font-medium">No investigation selected or available.</p>
        <Link
          to="/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium"
        >
          Start New Investigation
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Bar & Investigation Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800/70">
              {report.investigation_id}
            </span>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold uppercase ${
                report.status === "resolved"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                  : "bg-blue-950 text-blue-300 border border-blue-800"
              }`}
            >
              {report.status}
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100 mt-2">{report.title}</h1>
          <p className="text-xs font-mono text-slate-400 mt-1">
            {report.http_method} {report.target_url || "Repository Analysis"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {listQuery.data && listQuery.data.length > 1 && (
            <select
              aria-label="Switch active investigation"
              value={report.investigation_id}
              onChange={(e) => navigate(`/workspace/${e.target.value}`)}
              className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200"
            >
              {listQuery.data.map((inv) => (
                <option key={inv.investigation_id} value={inv.investigation_id}>
                  {inv.investigation_id} — {inv.title.slice(0, 42)}
                </option>
              ))}
            </select>
          )}
          <Link
            to={`/inspector?id=${report.investigation_id}`}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>Request Inspector</span>
          </Link>
          <Link
            to={`/reports?id=${report.investigation_id}`}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium text-white"
          >
            <FileDown className="w-3.5 h-3.5" />
            <span>Export Report</span>
          </Link>
        </div>
      </div>

      {/* Executive Summary Banner */}
      <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-800/50 text-sm text-slate-200">
        <div className="text-xs font-semibold uppercase tracking-wider text-blue-400 mb-1">
          Deterministic Executive Summary
        </div>
        <p>{report.summary}</p>
      </div>

      {/* Verification Banner if Level 4 Verification Ran */}
      {report.verification && (
        <div
          className={`p-5 rounded-xl border ${
            report.verification.fix_worked
              ? "bg-emerald-950/25 border-emerald-800/70"
              : "bg-amber-950/25 border-amber-800/70"
          }`}
          data-testid="verification-results"
        >
          <div className="flex items-center gap-2 font-semibold text-sm text-slate-100">
            {report.verification.fix_worked ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <XCircle className="w-5 h-5 text-amber-400" />
            )}
            <span>Step 7 Verification Result: {report.verification.summary}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3 text-xs">
            <div>
              <div className="font-semibold text-emerald-300 mb-1">Passed Verification Checks</div>
              <ul className="space-y-1 text-slate-300">
                {report.verification.passed_checks.map((c, idx) => (
                  <li key={idx} className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
            {report.verification.unverified_assumptions.length > 0 && (
              <div>
                <div className="font-semibold text-slate-400 mb-1">Unverified Assumptions</div>
                <ul className="list-disc list-inside text-slate-400 space-y-1">
                  {report.verification.unverified_assumptions.map((u, idx) => (
                    <li key={idx}>{u}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Grid: Timeline + Root Causes */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent Execution Timeline */}
        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-400" />
              <span>Agent Execution Timeline</span>
            </h2>
            <span className="text-xs font-mono text-slate-400">{report.timeline.length} steps</span>
          </div>
          <ol className="relative border-l border-slate-800 ml-2.5 space-y-4">
            {report.timeline.map((step) => (
              <li key={step.step_number} className="ml-4">
                <div className="absolute w-2.5 h-2.5 bg-blue-500 rounded-full -left-[5.5px] mt-1.5 border border-slate-950" />
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-semibold text-blue-300 uppercase">
                    {step.step_number}. {step.phase}
                  </span>
                  <span className="font-mono text-slate-500 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {step.duration_ms.toFixed(1)}ms
                  </span>
                </div>
                {step.tool_name && (
                  <div className="mt-0.5">
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-purple-300">
                      tool: {step.tool_name}
                    </span>
                  </div>
                )}
                <p className="text-xs text-slate-300 mt-1">{step.summary}</p>
              </li>
            ))}
          </ol>
        </div>

        {/* Ranked Root Causes & Deterministic Findings */}
        <div className="lg:col-span-2 space-y-6">
          {/* Root Cause Hypotheses */}
          <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-400" />
                <span>Ranked Root-Cause Hypotheses</span>
              </h2>
              <span className="text-xs text-slate-400">Ranked by evidence confidence</span>
            </div>

            {report.root_causes.length === 0 ? (
              <p className="text-sm text-emerald-400">
                No root-cause failures detected in this investigation.
              </p>
            ) : (
              <div className="space-y-3">
                {report.root_causes.map((rc) => (
                  <div
                    key={rc.hypothesis_id}
                    className="p-4 rounded-lg bg-slate-900/90 border border-slate-800 space-y-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300 font-mono text-xs font-bold border border-blue-500/30">
                          Rank #{rc.rank}
                        </span>
                        <h3 className="text-sm font-semibold text-slate-100">{rc.title}</h3>
                      </div>
                      <StatusPill status={rc.status} confidence={rc.confidence} />
                    </div>
                    <p className="text-xs text-slate-300">{rc.explanation}</p>
                    <div className="pt-1">
                      <div className="text-[11px] font-semibold text-slate-400 uppercase mb-1">
                        Supporting Evidence:
                      </div>
                      <ul className="space-y-1">
                        {rc.supporting_evidence.map((ev, i) => (
                          <li
                            key={i}
                            className="text-xs font-mono text-slate-300 bg-slate-950/70 px-2.5 py-1 rounded border border-slate-800/80 flex items-center gap-1.5"
                          >
                            <ChevronRight className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                            <span className="break-all">{ev}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* All Deterministic Findings */}
          <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
              Deterministic Diagnostic Findings ({report.findings.length})
            </h2>
            <div className="space-y-3">
              {report.findings.map((f, idx) => (
                <div
                  key={`${f.diagnostic_id}-${idx}`}
                  className="p-4 rounded-lg bg-slate-900/70 border border-slate-800/90 space-y-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-blue-400 px-2 py-0.5 rounded bg-slate-950 border border-slate-800">
                        {f.diagnostic_id}
                      </span>
                      <SeverityBadge severity={f.severity} />
                      <span className="text-xs uppercase font-mono text-slate-400">
                        {f.category}
                      </span>
                    </div>
                    <StatusPill status={f.status} confidence={f.confidence} />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-100">{f.title}</h3>
                  <p className="text-xs text-slate-300">{f.description}</p>
                  <div className="text-xs text-blue-300 bg-blue-950/30 border border-blue-900/50 rounded p-2.5">
                    <strong>Recommended Action:</strong> {f.recommendation}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Remediation Plan & Controlled Code Repairs */}
      <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Wrench className="w-4 h-4 text-emerald-400" />
              <span>Remediation Plan & Controlled Repair Patches</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Review generated unified diffs (Level 2). Explicit developer approval is required before applying or verifying changes (Levels 3 & 4).
            </p>
          </div>
        </div>

        {report.remediation_plan.length === 0 ? (
          <p className="text-xs text-slate-400">No remediation actions needed.</p>
        ) : (
          <div className="space-y-4">
            {report.remediation_plan.map((fix) => (
              <div
                key={fix.fix_id}
                className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-950 text-emerald-300 border border-slate-800">
                      {fix.fix_id}
                    </span>
                    <h3 className="text-sm font-semibold text-slate-100">{fix.problem}</h3>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      Risk: {fix.risk_level.toUpperCase()}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800/60">
                      Repair Level {fix.repair_level}
                    </span>
                  </div>

                  {fix.applied ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-800 text-xs font-semibold">
                      <ShieldCheck className="w-4 h-4" />
                      Approved & Verified
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmFix(fix)}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors"
                    >
                      <GitPullRequestDraft className="w-3.5 h-3.5" />
                      <span>Approve & Verify Repair</span>
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded bg-slate-950/60 border border-slate-800/80">
                    <span className="text-slate-400 font-semibold block mb-0.5">
                      Recommended Solution:
                    </span>
                    <span className="text-slate-200">{fix.recommended_solution}</span>
                  </div>
                  <div className="p-2.5 rounded bg-slate-950/60 border border-slate-800/80">
                    <span className="text-slate-400 font-semibold block mb-0.5">
                      Verification Procedure:
                    </span>
                    <span className="text-slate-200">{fix.verification_procedure}</span>
                  </div>
                </div>

                {fix.unified_diff && (
                  <pre className="p-3 rounded-lg bg-[#050811] border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto">
                    <code>{fix.unified_diff}</code>
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Explicit Approval Confirmation Dialog */}
      {confirmFix && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4"
        >
          <div className="max-w-lg w-full rounded-xl bg-[#0b1120] border border-slate-700 p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-slate-100">
              Confirm Repair Approval ({confirmFix.fix_id})
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              You are authorizing API Detective to apply repair{" "}
              <span className="font-mono text-blue-300">{confirmFix.fix_id}</span> (
              {confirmFix.problem}) and execute Level 4 automated verification diagnostics.
            </p>
            {confirmFix.unified_diff && (
              <pre className="p-3 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 max-h-48 overflow-y-auto">
                <code>{confirmFix.unified_diff}</code>
              </pre>
            )}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmFix(null)}
                className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={approveMutation.isPending}
                onClick={() => approveMutation.mutate(confirmFix.fix_id)}
                className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white"
              >
                {approveMutation.isPending ? "Verifying..." : "Confirm & Run Verification"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
