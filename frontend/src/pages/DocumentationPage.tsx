import React from "react";
import { BookOpen, Shield, Terminal, Wrench } from "lucide-react";

const diagnosticCatalog = [
  { id: "CONN-001..008", category: "Connectivity", desc: "DNS resolution failures, connection refused, timeouts, TLS certificates, URL syntax, redirect loops/downgrades, CORS conflicts, and proxy errors." },
  { id: "AUTH-001..008", category: "Authentication", desc: "Missing API keys, invalid/placeholder Bearer tokens, expired JWT claims (inspected safely), duplicate scheme prefixes, OAuth 2.0 errors, query-string credential leaks, missing scopes, and 401/403 triage." },
  { id: "REQ-001..008", category: "Request", desc: "Disallowed HTTP methods (405), missing headers, Content-Type mismatches (415), malformed JSON syntax, unexpanded path parameters ({id}), invalid query literals (undefined/NaN), and serialization bugs." },
  { id: "SCH-001..006", category: "Schema", desc: "Missing required JSON Schema properties, unexpected additionalProperties, type mismatches, enum violations, OpenAPI response contract mismatches, and deprecated operations." },
  { id: "RES-001..008", category: "Response", desc: "HTTP status code triage (400/404/422/5xx), malformed response JSON, application errors masked behind HTTP 200 OK, empty 200 bodies, HTTP 429 rate limiting, pagination truncation, and unexpected HTML responses." },
  { id: "INT-001..007", category: "Integration", desc: "Base URL mismatches, unset/placeholder environment variables, undocumented endpoint paths with fuzzy matching, inconsistent API version prefixes, camelCase vs snake_case mismatches, and unsafe SDK settings." },
];

export const DocumentationPage: React.FC = () => {
  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">
          API Detective Documentation & Reference
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Core philosophy: <strong>Investigate. Diagnose. Plan. Fix. Verify.</strong>
        </p>
      </div>

      {/* 7-Step Lifecycle */}
      <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-3">
        <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-blue-400" />
          <span>7-Step Agentic Investigation Lifecycle</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-7 gap-2.5 text-xs">
          {[
            { step: "1. Understand", detail: "Extract endpoint, headers, payload, schema, and repo context." },
            { step: "2. Plan", detail: "Select relevant deterministic diagnostic tools." },
            { step: "3. Execute", detail: "Run SSRF-safe HTTP and contract analyzers." },
            { step: "4. Analyze", detail: "Rank root-cause hypotheses by evidence confidence." },
            { step: "5. Remediate", detail: "Generate Level 1 explanations and Level 2 unified diffs." },
            { step: "6. Apply Fix", detail: "Apply Level 3 code modifications only after approval." },
            { step: "7. Verify", detail: "Re-run Level 4 diagnostics and tests to confirm fix." },
          ].map((item) => (
            <div key={item.step} className="p-3 rounded-lg bg-slate-900 border border-slate-800">
              <div className="font-bold text-blue-300 mb-1">{item.step}</div>
              <p className="text-slate-400 leading-relaxed">{item.detail}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Diagnostic Catalog */}
      <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-4">
        <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Wrench className="w-4 h-4 text-emerald-400" />
          <span>Deterministic Diagnostic Catalog</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {diagnosticCatalog.map((cat) => (
            <div key={cat.id} className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-slate-100">{cat.category}</span>
                <span className="font-mono text-xs text-blue-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                  {cat.id}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{cat.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* CLI Cheat Sheet */}
      <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-3">
        <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Terminal className="w-4 h-4 text-purple-400" />
          <span>CLI Quick Reference</span>
        </h2>
        <pre className="p-4 rounded-lg bg-[#050811] border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto">
{`# Diagnose an endpoint offline or live
api-detective diagnose --url https://api.example.com/v1/users --method GET

# Inspect an OpenAPI 3.0/3.1 or Swagger specification
api-detective inspect --file examples/openapi.yaml

# Validate a request payload against a JSON Schema
api-detective validate --schema examples/schema.json --payload examples/request.json

# Run repository-aware investigation across Python/JS/TS projects
api-detective investigate --repo ./examples/sample_repo

# Export structured diagnostic reports (json, markdown, html)
api-detective report --format json`}
        </pre>
      </div>

      {/* Security Guarantees */}
      <div className="p-5 rounded-xl bg-[#0b1120] border border-slate-800/90 space-y-2">
        <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-400" />
          <span>Security & Privacy Guarantees</span>
        </h2>
        <ul className="list-disc list-inside text-xs text-slate-300 space-y-1.5">
          <li>All API keys, Bearer tokens, JWTs, and sensitive headers are masked before logging or storage.</li>
          <li>Outgoing requests validate DNS resolutions against loopback, private RFC1918, and cloud metadata IPs (169.254.169.254).</li>
          <li>Repair patches forbid disabling TLS verification (<code className="font-mono">verify=False</code>) or removing authentication.</li>
        </ul>
      </div>
    </div>
  );
};
