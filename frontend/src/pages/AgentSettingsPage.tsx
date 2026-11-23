import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Cpu, Lock, Save, Shield } from "lucide-react";
import { apiClient } from "../services/apiClient";
import type { AgentSettingsUpdate } from "../types/api";

export const AgentSettingsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["agent-settings"],
    queryFn: () => apiClient.getSettings(),
  });

  const [provider, setProvider] = useState<"none" | "openai" | "gemini" | "anthropic" | "local">("none");
  const [model, setModel] = useState("gpt-4o-mini");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [maxIterations, setMaxIterations] = useState(6);
  const [timeoutSec, setTimeoutSec] = useState(15);
  const [blockPrivate, setBlockPrivate] = useState(true);
  const [allowLocalhost, setAllowLocalhost] = useState(false);
  const [allowRepoLlm, setAllowRepoLlm] = useState(false);
  const [requireApproval, setRequireApproval] = useState(true);
  const [redactSecrets, setRedactSecrets] = useState(true);
  const [persistBodies, setPersistBodies] = useState(false);
  const [savedBanner, setSavedBanner] = useState(false);

  useEffect(() => {
    if (data) {
      setProvider(
        (data.llm_provider as "none" | "openai" | "gemini" | "anthropic" | "local") || "none"
      );
      setModel(data.llm_model);
      setBaseUrl(data.llm_base_url);
      setMaxIterations(data.agent_max_iterations);
      setTimeoutSec(data.http_timeout_seconds);
      setBlockPrivate(data.block_private_networks);
      setAllowLocalhost(data.allow_localhost_targets);
      setAllowRepoLlm(data.allow_repo_transmission_to_llm);
      setRequireApproval(data.require_approval_for_file_edits);
      setRedactSecrets(data.redact_secrets);
      setPersistBodies(data.persist_request_bodies);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (payload: AgentSettingsUpdate) => apiClient.updateSettings(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["agent-settings"], updated);
      setApiKey("");
      setSavedBanner(true);
      setTimeout(() => setSavedBanner(false), 3000);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: AgentSettingsUpdate = {
      llm_provider: provider,
      llm_model: model,
      llm_base_url: baseUrl,
      agent_max_iterations: maxIterations,
      http_timeout_seconds: timeoutSec,
      block_private_networks: blockPrivate,
      allow_localhost_targets: allowLocalhost,
      allow_repo_transmission_to_llm: allowRepoLlm,
      require_approval_for_file_edits: requireApproval,
      redact_secrets: redactSecrets,
      persist_request_bodies: persistBodies,
    };
    if (apiKey.trim()) {
      payload.llm_api_key = apiKey.trim();
    }
    mutation.mutate(payload);
  };

  if (isLoading) {
    return <div className="h-64 animate-pulse bg-slate-900 rounded-xl" />;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">
          Agent, Security & Privacy Settings
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Configure optional LLM synthesis providers, bounded investigation limits, SSRF network guards, and secret redaction policies.
        </p>
      </div>

      {savedBanner && (
        <div
          role="status"
          className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-800 text-emerald-200 text-xs flex items-center gap-2"
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>Configuration updated and applied to the runtime agent engine.</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Optional LLM Provider */}
        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200 uppercase tracking-wider">
            <Cpu className="w-4 h-4 text-blue-400" />
            <span>Optional LLM Provider Configuration</span>
          </div>
          <p className="text-xs text-slate-400">
            The deterministic diagnostic engine operates with 100% capability when LLM Provider is set to{" "}
            <code className="font-mono text-blue-300">none</code>.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="llm-provider-select" className="block text-xs font-medium text-slate-300 mb-1">
                LLM Provider
              </label>
              <select
                id="llm-provider-select"
                value={provider}
                onChange={(e) =>
                  setProvider(
                    e.target.value as "none" | "openai" | "gemini" | "anthropic" | "local"
                  )
                }
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-100"
              >
                <option value="none">None (Deterministic Engine Only)</option>
                <option value="openai">OpenAI / OpenAI-Compatible</option>
                <option value="gemini">Google Gemini</option>
                <option value="anthropic">Anthropic Claude</option>
                <option value="local">Local Model Endpoint (Ollama / vLLM)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Model Identifier
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="gpt-4o-mini / gemini-2.5-flash / claude-3-5-haiku-latest"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-100"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                API Key {data?.llm_api_key_configured ? "(Configured — enter to rotate)" : "(Not set)"}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-... (never exposed in responses)"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-100"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Custom Base URL (Optional)
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:11434/v1"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-100"
              />
            </div>
          </div>
        </div>

        {/* Agent Execution Limits */}
        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200 uppercase tracking-wider">
            <Shield className="w-4 h-4 text-purple-400" />
            <span>Bounded Investigation & Network Limits</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Maximum Investigation Iterations (1–20)
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={maxIterations}
                onChange={(e) => setMaxIterations(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-100"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                HTTP Request Timeout (Seconds)
              </label>
              <input
                type="number"
                min={1}
                max={120}
                step={0.5}
                value={timeoutSec}
                onChange={(e) => setTimeoutSec(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-100"
              />
            </div>
          </div>
        </div>

        {/* Security & Privacy Controls */}
        <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200 uppercase tracking-wider mb-2">
            <Lock className="w-4 h-4 text-emerald-400" />
            <span>SSRF Protection, Code Permissions & Privacy</span>
          </div>

          {[
            {
              label: "Block private network & link-local IP targets (SSRF protection)",
              checked: blockPrivate,
              onChange: setBlockPrivate,
            },
            {
              label: "Allow diagnosing localhost / 127.0.0.1 development servers",
              checked: allowLocalhost,
              onChange: setAllowLocalhost,
            },
            {
              label: "Require explicit developer approval before modifying source files (Level 3)",
              checked: requireApproval,
              onChange: setRequireApproval,
            },
            {
              label: "Automatically redact API keys, Bearer tokens, and secrets in logs & reports",
              checked: redactSecrets,
              onChange: setRedactSecrets,
            },
            {
              label: "Persist raw request payloads in database history",
              checked: persistBodies,
              onChange: setPersistBodies,
            },
            {
              label: "Permit transmitting sanitized repository snippets to external LLM provider",
              checked: allowRepoLlm,
              onChange: setAllowRepoLlm,
            },
          ].map((item, idx) => (
            <label key={idx} className="flex items-center gap-3 text-xs text-slate-200 cursor-pointer py-1">
              <input
                type="checkbox"
                checked={item.checked}
                onChange={(e) => item.onChange(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-blue-600"
              />
              <span>{item.label}</span>
            </label>
          ))}
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
          >
            <Save className="w-4 h-4" />
            <span>{mutation.isPending ? "Saving..." : "Save Configuration"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
