import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  PlusCircle,
  SearchCheck,
  Terminal,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiClient } from "../services/apiClient";
import { SeverityBadge } from "../components/SeverityBadge";

export const OverviewDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: () => apiClient.getDashboardOverview(),
  });

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse" data-testid="overview-loading">
        <div className="h-8 w-64 bg-slate-800 rounded" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-900 border border-slate-800 rounded-xl" />
          ))}
        </div>
        <div className="h-72 bg-slate-900 border border-slate-800 rounded-xl" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-6 rounded-xl bg-red-950/30 border border-red-800/60 text-red-200 space-y-3">
        <div className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <span>Unable to load backend diagnostic metrics</span>
        </div>
        <p className="text-sm text-red-300/90">
          {error instanceof Error ? error.message : "Backend API is unreachable."}
        </p>
        <button
          onClick={() => refetch()}
          className="px-3 py-1.5 rounded-lg bg-red-900/60 hover:bg-red-800 text-xs font-medium"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const categoryChartData = Object.entries(data.category_distribution).map(([name, count]) => ({
    category: name.charAt(0).toUpperCase() + name.slice(1),
    count,
  }));

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            Diagnostic Overview
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time telemetry from deterministic API investigations and agent remediation runs.
          </p>
        </div>
        <Link
          to="/new"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors shadow-sm"
        >
          <PlusCircle className="w-4 h-4" />
          <span>New Investigation</span>
        </Link>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
            <span>Total Investigations</span>
            <SearchCheck className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-3 text-3xl font-bold text-slate-100 font-mono">
            {data.total_investigations}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            Persisted in diagnostic store
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
            <span>Successful Diagnoses</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 text-3xl font-bold text-emerald-400 font-mono">
            {data.successful_diagnoses}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            Deterministic root-cause runs completed
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
            <span>Open Findings</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 text-3xl font-bold text-amber-300 font-mono">
            {data.open_issues}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            Awaiting patch approval or verification
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
            <span>Verified Fixes</span>
            <Activity className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-3 text-3xl font-bold text-blue-300 font-mono">
            {data.resolved_issues}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            Resolved via Level 4 verification
          </div>
        </div>
      </div>

      {/* Category Distribution & Recent Agent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 flex flex-col">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Diagnostic Category Distribution
          </h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="category" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    color: "#f8fafc",
                    borderRadius: "8px",
                  }}
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
              Recent Agent Activity
            </h2>
            <Terminal className="w-4 h-4 text-slate-400" />
          </div>
          <div className="space-y-3 overflow-y-auto max-h-64 pr-1">
            {data.recent_activity.length === 0 ? (
              <p className="text-xs text-slate-500">No agent tool executions recorded yet.</p>
            ) : (
              data.recent_activity.slice(0, 7).map((act, idx) => (
                <div
                  key={`${act.timestamp}-${idx}`}
                  className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800/80 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-blue-400 font-medium">
                      {act.tool_name || act.phase}
                    </span>
                    <span className="text-slate-500 font-mono">{act.duration_ms.toFixed(1)}ms</span>
                  </div>
                  <p className="text-slate-300 line-clamp-2">{act.summary}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Recent Investigations Table */}
      <div className="rounded-xl bg-[#0b1120] border border-slate-800/90 overflow-hidden">
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-100">Recent Investigations</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Select an investigation to open its execution timeline, evidence, and remediation patches.
            </p>
          </div>
          <Link
            to="/workspace"
            className="text-xs text-blue-400 hover:text-blue-300 inline-flex items-center gap-1 font-medium"
          >
            <span>Open Workspace</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {data.recent_investigations.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-sm">
            No investigations found. Start your first investigation to diagnose an endpoint.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-800/80 text-xs uppercase text-slate-400 bg-slate-900/40">
                  <th className="py-3 px-4 font-medium">ID</th>
                  <th className="py-3 px-4 font-medium">Investigation</th>
                  <th className="py-3 px-4 font-medium">Endpoint</th>
                  <th className="py-3 px-4 font-medium">Findings</th>
                  <th className="py-3 px-4 font-medium">Top Root Cause</th>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data.recent_investigations.map((inv) => {
                  const topFinding = inv.findings[0];
                  const topRc = inv.root_causes[0];
                  return (
                    <tr
                      key={inv.investigation_id}
                      onClick={() => navigate(`/workspace/${inv.investigation_id}`)}
                      className="hover:bg-slate-800/30 cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 px-4 font-mono text-xs text-blue-400">
                        {inv.investigation_id}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-200 max-w-xs truncate">
                        {inv.title}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-slate-300 max-w-xs truncate">
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 mr-1.5">
                          {inv.http_method}
                        </span>
                        {inv.target_url || "Repository / Local"}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-slate-300">
                            {inv.findings.length}
                          </span>
                          {topFinding && <SeverityBadge severity={topFinding.severity} />}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-300 max-w-xs truncate">
                        {topRc ? `${topRc.title} (${Math.round(topRc.confidence * 100)}%)` : "Clean"}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                            inv.status === "resolved"
                              ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/70"
                              : "bg-blue-950/80 text-blue-300 border border-blue-800/70"
                          }`}
                        >
                          <Clock className="w-3 h-3" />
                          {inv.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <span className="text-xs font-medium text-blue-400 hover:underline">
                          Inspect →
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
