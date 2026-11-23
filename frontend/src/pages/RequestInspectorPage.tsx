import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Clock, Lock, Server, ShieldCheck } from "lucide-react";
import { apiClient } from "../services/apiClient";

export const RequestInspectorPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const listQuery = useQuery({
    queryKey: ["investigations"],
    queryFn: () => apiClient.listInvestigations(50),
  });

  const selectedId =
    searchParams.get("id") || listQuery.data?.[0]?.investigation_id || "";

  const detailQuery = useQuery({
    queryKey: ["investigation", selectedId],
    queryFn: () => apiClient.getInvestigation(selectedId),
    enabled: Boolean(selectedId),
  });

  const report = detailQuery.data;
  const ex = report?.http_exchange;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            HTTP Request & Response Inspector
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Inspect HTTP exchange snapshots with automatic secret and token redaction.
          </p>
        </div>

        {listQuery.data && listQuery.data.length > 0 && (
          <select
            aria-label="Select investigation exchange"
            value={selectedId}
            onChange={(e) => setSearchParams({ id: e.target.value })}
            className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200"
          >
            {listQuery.data.map((inv) => (
              <option key={inv.investigation_id} value={inv.investigation_id}>
                {inv.investigation_id} — {inv.http_method} {inv.target_url || inv.title}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Redaction Notice */}
      <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-800/50 flex items-center gap-2.5 text-xs text-emerald-200">
        <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
        <span>
          <strong>Secret Redaction Enforced:</strong> Authorization headers, Bearer tokens, API keys, and sensitive query parameters are automatically masked as{" "}
          <code className="font-mono text-emerald-300">***REDACTED***</code>.
        </span>
      </div>

      {!ex ? (
        <div className="p-8 rounded-xl bg-[#0b1120] border border-slate-800 text-center text-sm text-slate-400">
          No HTTP exchange snapshot recorded for this investigation.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Request Summary Bar */}
          <div className="p-4 rounded-xl bg-[#0b1120] border border-slate-800/90 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <span className="px-2.5 py-1 rounded bg-blue-600/20 border border-blue-500/40 font-mono text-xs font-bold text-blue-300">
                {ex.method}
              </span>
              <span className="font-mono text-sm text-slate-100 truncate">{ex.url}</span>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono">
              <span
                className={`px-2.5 py-1 rounded font-bold ${
                  ex.response_status && ex.response_status >= 400
                    ? "bg-red-950 text-red-300 border border-red-800"
                    : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                }`}
              >
                Status: {ex.response_status ?? "ERR"}
              </span>
              <span className="text-slate-400 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-blue-400" />
                {ex.elapsed_ms !== null ? `${ex.elapsed_ms} ms` : "0.0 ms"}
              </span>
              <span className="text-slate-400 flex items-center gap-1">
                <Lock className="w-3.5 h-3.5 text-emerald-400" />
                TLS: {ex.tls_verified ? "Verified" : "Unverified"}
              </span>
            </div>
          </div>

          {/* Side-by-Side Request and Response */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Request Panel */}
            <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Server className="w-4 h-4 text-blue-400" />
                <span>Outgoing Request</span>
              </h2>

              <div>
                <div className="text-xs font-semibold text-slate-400 mb-2">
                  Request Headers (Redacted)
                </div>
                {Object.keys(ex.request_headers).length === 0 ? (
                  <p className="text-xs text-slate-500">No request headers sent.</p>
                ) : (
                  <div className="rounded-lg bg-slate-950 border border-slate-800 divide-y divide-slate-800/80 text-xs font-mono">
                    {Object.entries(ex.request_headers).map(([k, v]) => (
                      <div key={k} className="p-2 flex justify-between gap-4">
                        <span className="text-blue-300 font-semibold">{k}:</span>
                        <span className="text-slate-300 break-all">{v}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <div className="text-xs font-semibold text-slate-400 mb-2">
                  Query Parameters
                </div>
                {Object.keys(ex.query_params).length === 0 ? (
                  <p className="text-xs text-slate-500">No query parameters.</p>
                ) : (
                  <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto">
                    {JSON.stringify(ex.query_params, null, 2)}
                  </pre>
                )}
              </div>

              <div>
                <div className="text-xs font-semibold text-slate-400 mb-2">Request Body</div>
                <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto max-h-64">
                  {ex.request_body
                    ? JSON.stringify(ex.request_body, null, 2)
                    : "// No request body persisted or empty payload"}
                </pre>
              </div>
            </div>

            {/* Response Panel */}
            <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Server className="w-4 h-4 text-purple-400" />
                <span>Incoming Response</span>
              </h2>

              <div>
                <div className="text-xs font-semibold text-slate-400 mb-2">
                  Response Headers
                </div>
                {Object.keys(ex.response_headers).length === 0 ? (
                  <p className="text-xs text-slate-500">No response headers captured.</p>
                ) : (
                  <div className="rounded-lg bg-slate-950 border border-slate-800 divide-y divide-slate-800/80 text-xs font-mono">
                    {Object.entries(ex.response_headers).map(([k, v]) => (
                      <div key={k} className="p-2 flex justify-between gap-4">
                        <span className="text-purple-300 font-semibold">{k}:</span>
                        <span className="text-slate-300 break-all">{v}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <div className="text-xs font-semibold text-slate-400 mb-2">Response Body</div>
                <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto max-h-72">
                  {typeof ex.response_body === "string"
                    ? ex.response_body
                    : ex.response_body
                    ? JSON.stringify(ex.response_body, null, 2)
                    : ex.raw_response_text || "// Empty response body"}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
