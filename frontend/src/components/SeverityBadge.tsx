import React from "react";
import type { DiagnosticSeverity, FindingStatus } from "../types/api";
import { cn } from "../utils/cn";

export const SeverityBadge: React.FC<{ severity: DiagnosticSeverity }> = ({ severity }) => {
  const styles: Record<DiagnosticSeverity, string> = {
    critical: "bg-red-950/80 text-red-300 border-red-800/80",
    high: "bg-orange-950/80 text-orange-300 border-orange-800/80",
    medium: "bg-amber-950/80 text-amber-300 border-amber-800/80",
    low: "bg-blue-950/80 text-blue-300 border-blue-800/80",
    informational: "bg-slate-800/80 text-slate-300 border-slate-700",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide border",
        styles[severity] || styles.informational
      )}
    >
      {severity}
    </span>
  );
};

export const StatusPill: React.FC<{ status: FindingStatus; confidence?: number }> = ({
  status,
  confidence,
}) => {
  const styles: Record<FindingStatus, string> = {
    confirmed: "bg-emerald-950/70 text-emerald-300 border-emerald-800/70",
    probable: "bg-blue-950/70 text-blue-300 border-blue-800/70",
    possible: "bg-amber-950/70 text-amber-300 border-amber-800/70",
    unverified: "bg-slate-800 text-slate-400 border-slate-700",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border",
        styles[status] || styles.unverified
      )}
    >
      <span>{status}</span>
      {typeof confidence === "number" && (
        <span className="font-mono opacity-80">({Math.round(confidence * 100)}%)</span>
      )}
    </span>
  );
};
