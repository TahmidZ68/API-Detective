import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  FileJson,
  Play,
  Plus,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { apiClient } from "../services/apiClient";
import type { InvestigationRequestPayload } from "../types/api";

interface KeyValuePair {
  key: string;
  value: string;
}

export const NewInvestigationPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [url, setUrl] = useState("https://api.orders.example.com/v1/orders");
  const [method, setMethod] = useState("POST");
  const [headers, setHeaders] = useState<KeyValuePair[]>([
    { key: "Content-Type", value: "application/json" },
    { key: "Accept", value: "application/json" },
  ]);
  const [queryParams, setQueryParams] = useState<KeyValuePair[]>([]);
  const [requestBody, setRequestBody] = useState(
    '{\n  "customer_id": "cust_104",\n  "amount": "invalid_number"\n}'
  );
  const [openapiSpecText, setOpenapiSpecText] = useState("");
  const [expectedSchemaText, setExpectedSchemaText] = useState("");
  const [simulatedStatus, setSimulatedStatus] = useState<string>("401");
  const [executeLive, setExecuteLive] = useState(false);
  const [repositoryPath, setRepositoryPath] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: InvestigationRequestPayload) =>
      apiClient.createInvestigation(payload),
    onSuccess: (report) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
      navigate(`/workspace/${report.investigation_id}`);
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const handleSpecFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setOpenapiSpecText(reader.result);
      }
    };
    reader.readAsText(file);
  };

  const applyPresetScenario = (preset: "auth401" | "schema422" | "corsHtml") => {
    setFormError(null);
    if (preset === "auth401") {
      setTitle("Diagnose HTTP 401 & Duplicate Bearer Header");
      setPrompt("Why is my API returning 401 Unauthorized on GET /v1/accounts?");
      setMethod("GET");
      setUrl("https://api.payments.example.com/v1/accounts");
      setHeaders([
        { key: "Authorization", value: "Bearer Bearer token_sample_123456" },
        { key: "Accept", value: "application/json" },
      ]);
      setRequestBody("");
      setSimulatedStatus("401");
      setExecuteLive(false);
    } else if (preset === "schema422") {
      setTitle("Diagnose Schema Type & Missing Required Property");
      setPrompt("Find the cause of this schema validation error on POST /v1/users");
      setMethod("POST");
      setUrl("https://api.users.example.com/v1/users");
      setHeaders([{ key: "Content-Type", value: "application/json" }]);
      setRequestBody('{\n  "username": "ada",\n  "age": "twenty-eight"\n}');
      setExpectedSchemaText(
        JSON.stringify(
          {
            type: "object",
            required: ["username", "email", "age"],
            properties: {
              username: { type: "string" },
              email: { type: "string" },
              age: { type: "integer" },
            },
          },
          null,
          2
        )
      );
      setSimulatedStatus("422");
      setExecuteLive(false);
    } else if (preset === "corsHtml") {
      setTitle("Diagnose Unexpected HTML Response & Unexpanded Path Template");
      setPrompt("Why is my frontend receiving unexpected HTML instead of JSON?");
      setMethod("GET");
      setUrl("https://api.catalog.example.com/v1/items/{item_id}");
      setHeaders([
        { key: "Accept", value: "application/json" },
        { key: "Origin", value: "https://app.catalog.example.com" },
      ]);
      setQueryParams([{ key: "page", value: "0" }]);
      setSimulatedStatus("200");
      setExecuteLive(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!url.trim() && !repositoryPath.trim()) {
      setFormError("Please provide an API endpoint URL or a repository path to investigate.");
      return;
    }

    const headersMap: Record<string, string> = {};
    headers.forEach((h) => {
      if (h.key.trim()) headersMap[h.key.trim()] = h.value;
    });

    const queryMap: Record<string, string> = {};
    queryParams.forEach((q) => {
      if (q.key.trim()) queryMap[q.key.trim()] = q.value;
    });

    let parsedBody: unknown = undefined;
    if (requestBody.trim()) {
      try {
        parsedBody = JSON.parse(requestBody);
      } catch {
        // Keep raw_request_text so Request Analyzer detects malformed JSON (REQ-004)
        parsedBody = undefined;
      }
    }

    let parsedExpectedSchema: Record<string, unknown> | undefined = undefined;
    if (expectedSchemaText.trim()) {
      try {
        parsedExpectedSchema = JSON.parse(expectedSchemaText);
      } catch {
        setFormError("Expected JSON Schema is not valid JSON.");
        return;
      }
    }

    const simCode =
      !executeLive && simulatedStatus.trim() ? parseInt(simulatedStatus.trim(), 10) : undefined;

    const payload: InvestigationRequestPayload = {
      title: title.trim() || undefined,
      prompt: prompt.trim() || undefined,
      url: url.trim() || undefined,
      method,
      headers: headersMap,
      query_params: queryMap,
      request_payload: parsedBody,
      raw_request_text: requestBody.trim() || undefined,
      openapi_spec: openapiSpecText.trim() || undefined,
      request_schema: parsedExpectedSchema,
      repository_path: repositoryPath.trim() || undefined,
      simulated_response_status: Number.isNaN(simCode) ? undefined : simCode,
      execute_live_request: executeLive,
    };

    mutation.mutate(payload);
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            Start New API Investigation
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Configure the endpoint, headers, payload, and contract to launch a multi-step agent diagnosis.
          </p>
        </div>

        {/* Scenario presets */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            Presets:
          </span>
          <button
            type="button"
            onClick={() => applyPresetScenario("auth401")}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700"
          >
            401 Auth Failure
          </button>
          <button
            type="button"
            onClick={() => applyPresetScenario("schema422")}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700"
          >
            422 Schema Mismatch
          </button>
          <button
            type="button"
            onClick={() => applyPresetScenario("corsHtml")}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700"
          >
            Path & Pagination Issue
          </button>
        </div>
      </div>

      {formError && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-red-950/40 border border-red-800/80 text-red-200 text-sm flex items-center gap-2.5"
        >
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{formError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Problem Context */}
        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            1. Investigation Context & Target Endpoint
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Investigation Title (Optional)
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. POST /v1/orders returning 401 Unauthorized"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700/80 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Diagnostic Question / Symptom Prompt
              </label>
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. Why is my API returning 401 or failing schema validation?"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700/80 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <div className="sm:w-36">
              <label
                htmlFor="http-method-select"
                className="block text-xs font-medium text-slate-300 mb-1"
              >
                HTTP Method
              </label>
              <select
                id="http-method-select"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700/80 text-sm font-mono text-slate-100 focus:outline-none focus:border-blue-500"
              >
                {["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1">
              <label
                htmlFor="endpoint-url-input"
                className="block text-xs font-medium text-slate-300 mb-1"
              >
                API Endpoint URL
              </label>
              <input
                id="endpoint-url-input"
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://api.example.com/v1/resource"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700/80 text-sm font-mono text-slate-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            <div className="flex items-center gap-2.5">
              <input
                id="execute-live-checkbox"
                type="checkbox"
                checked={executeLive}
                onChange={(e) => setExecuteLive(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-blue-600"
              />
              <label htmlFor="execute-live-checkbox" className="text-xs text-slate-300">
                Execute live network request (SSRF-protected)
              </label>
            </div>

            {!executeLive && (
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Observed / Simulated HTTP Status Code
                </label>
                <input
                  type="number"
                  value={simulatedStatus}
                  onChange={(e) => setSimulatedStatus(e.target.value)}
                  placeholder="401"
                  className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Local Repository Path (Optional)
              </label>
              <input
                type="text"
                value={repositoryPath}
                onChange={(e) => setRepositoryPath(e.target.value)}
                placeholder="./examples/sample_repo"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100"
              />
            </div>
          </div>
        </div>

        {/* Headers & Query Parameters */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                2. Request Headers
              </h2>
              <button
                type="button"
                onClick={() => setHeaders([...headers, { key: "", value: "" }])}
                className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
              >
                <Plus className="w-3.5 h-3.5" /> Add Header
              </button>
            </div>
            <p className="text-[11px] text-slate-400">
              Secrets and Authorization tokens are automatically redacted before persistence.
            </p>
            <div className="space-y-2">
              {headers.map((h, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={h.key}
                    onChange={(e) => {
                      const next = [...headers];
                      next[i].key = e.target.value;
                      setHeaders(next);
                    }}
                    placeholder="Header Name"
                    className="w-2/5 px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100"
                  />
                  <input
                    type="text"
                    value={h.value}
                    onChange={(e) => {
                      const next = [...headers];
                      next[i].value = e.target.value;
                      setHeaders(next);
                    }}
                    placeholder="Value"
                    className="flex-1 px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100"
                  />
                  <button
                    type="button"
                    onClick={() => setHeaders(headers.filter((_, idx) => idx !== i))}
                    className="p-1 text-slate-500 hover:text-red-400"
                    aria-label="Remove header"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                3. Query Parameters
              </h2>
              <button
                type="button"
                onClick={() => setQueryParams([...queryParams, { key: "", value: "" }])}
                className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
              >
                <Plus className="w-3.5 h-3.5" /> Add Parameter
              </button>
            </div>
            <div className="space-y-2">
              {queryParams.length === 0 ? (
                <p className="text-xs text-slate-500 py-2">No query parameters configured.</p>
              ) : (
                queryParams.map((q, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={q.key}
                      onChange={(e) => {
                        const next = [...queryParams];
                        next[i].key = e.target.value;
                        setQueryParams(next);
                      }}
                      placeholder="Param key"
                      className="w-2/5 px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100"
                    />
                    <input
                      type="text"
                      value={q.value}
                      onChange={(e) => {
                        const next = [...queryParams];
                        next[i].value = e.target.value;
                        setQueryParams(next);
                      }}
                      placeholder="Value"
                      className="flex-1 px-2.5 py-1.5 rounded bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100"
                    />
                    <button
                      type="button"
                      onClick={() => setQueryParams(queryParams.filter((_, idx) => idx !== i))}
                      className="p-1 text-slate-500 hover:text-red-400"
                      aria-label="Remove query parameter"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Request Payload & OpenAPI / Schema */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                4. Request Payload (JSON)
              </h2>
              <FileJson className="w-4 h-4 text-slate-400" />
            </div>
            <textarea
              rows={7}
              value={requestBody}
              onChange={(e) => setRequestBody(e.target.value)}
              placeholder='{"key": "value"}'
              className="w-full p-3 rounded-lg bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                5. OpenAPI Spec or JSON Schema
              </h2>
              <label className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 cursor-pointer">
                <Upload className="w-3.5 h-3.5" />
                <span>Upload YAML/JSON</span>
                <input
                  type="file"
                  accept=".yaml,.yml,.json"
                  onChange={handleSpecFileUpload}
                  className="hidden"
                />
              </label>
            </div>
            <textarea
              rows={3}
              value={openapiSpecText}
              onChange={(e) => setOpenapiSpecText(e.target.value)}
              placeholder="Paste OpenAPI 3.0/3.1 YAML or JSON specification here..."
              className="w-full p-2.5 rounded-lg bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100 focus:outline-none focus:border-blue-500"
            />
            <textarea
              rows={3}
              value={expectedSchemaText}
              onChange={(e) => setExpectedSchemaText(e.target.value)}
              placeholder='Or paste expected JSON Schema: {"type": "object", "required": ["id"]}'
              className="w-full p-2.5 rounded-lg bg-slate-900 border border-slate-700/80 text-xs font-mono text-slate-100 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold transition-colors shadow-sm"
          >
            <Play className="w-4 h-4" />
            <span>
              {mutation.isPending ? "Running Multi-Step Investigation..." : "Launch Investigation"}
            </span>
          </button>
        </div>
      </form>
    </div>
  );
};
