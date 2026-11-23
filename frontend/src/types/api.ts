export type DiagnosticCategory =
  | "connectivity"
  | "authentication"
  | "request"
  | "schema"
  | "response"
  | "integration";

export type DiagnosticSeverity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "informational";

export type FindingStatus =
  | "confirmed"
  | "probable"
  | "possible"
  | "unverified";

export interface DiagnosticFinding {
  diagnostic_id: string;
  category: DiagnosticCategory;
  severity: DiagnosticSeverity;
  title: string;
  description: string;
  evidence: string[];
  recommendation: string;
  confidence: number;
  status: FindingStatus;
  metadata?: Record<string, unknown>;
}

export interface HTTPExchangeSnapshot {
  method: string;
  url: string;
  request_headers: Record<string, string>;
  query_params: Record<string, unknown>;
  request_body: unknown | null;
  response_status: number | null;
  response_headers: Record<string, string>;
  response_body: unknown | null;
  raw_response_text?: string | null;
  elapsed_ms: number | null;
  redirect_chain: string[];
  error_type: string | null;
  error_message: string | null;
  tls_verified: boolean;
}

export interface InvestigationPlanStep {
  step_index: number;
  tool_name: string;
  rationale: string;
  completed: boolean;
}

export interface InvestigationStepRecord {
  step_number: number;
  phase:
    | "understand"
    | "plan"
    | "execute_tool"
    | "analyze"
    | "remediate"
    | "apply_fix"
    | "verify";
  tool_name: string | null;
  summary: string;
  details: Record<string, unknown>;
  duration_ms: number;
  timestamp: string;
}

export interface RootCauseHypothesis {
  hypothesis_id: string;
  rank: number;
  title: string;
  category: DiagnosticCategory;
  confidence: number;
  status: FindingStatus;
  explanation: string;
  supporting_evidence: string[];
  related_diagnostic_ids: string[];
}

export interface RemediationPlanItem {
  fix_id: string;
  problem: string;
  evidence: string[];
  root_cause: string;
  recommended_solution: string;
  affected_files: string[];
  risk_level: "low" | "medium" | "high";
  repair_level: number;
  unified_diff: string | null;
  requires_approval: boolean;
  approved: boolean;
  applied: boolean;
  verification_procedure: string;
}

export interface VerificationReport {
  verified: boolean;
  fix_worked: boolean;
  passed_checks: string[];
  failed_checks: string[];
  remaining_problems: string[];
  unverified_assumptions: string[];
  summary: string;
}

export interface RepositoryFinding {
  file_path: string;
  line_number: number;
  language: string;
  client_library: string;
  pattern_type: string;
  snippet: string;
  note: string;
}

export interface RepositoryAnalysisResult {
  repository_path: string;
  files_scanned: number;
  languages_detected: string[];
  client_libraries_detected: string[];
  endpoints_discovered: string[];
  env_vars_referenced: string[];
  findings: RepositoryFinding[];
  diagnostic_findings: DiagnosticFinding[];
}

export interface InvestigationReport {
  investigation_id: string;
  title: string;
  prompt: string | null;
  status: "running" | "completed" | "resolved" | "failed" | "cancelled";
  created_at: string;
  completed_at: string | null;
  target_url: string | null;
  http_method: string;
  plan: InvestigationPlanStep[];
  timeline: InvestigationStepRecord[];
  http_exchange: HTTPExchangeSnapshot | null;
  findings: DiagnosticFinding[];
  root_causes: RootCauseHypothesis[];
  remediation_plan: RemediationPlanItem[];
  repository_analysis: RepositoryAnalysisResult | null;
  verification: VerificationReport | null;
  llm_assisted: boolean;
  llm_provider_used: string;
  summary: string;
}

export interface InvestigationRequestPayload {
  title?: string;
  prompt?: string;
  url?: string;
  method: string;
  headers?: Record<string, string>;
  query_params?: Record<string, unknown>;
  request_payload?: unknown;
  raw_request_text?: string;
  expected_status?: number;
  simulated_response_status?: number;
  simulated_response_headers?: Record<string, string>;
  simulated_response_body?: unknown;
  error_message?: string;
  openapi_spec?: string | Record<string, unknown>;
  expected_response_schema?: Record<string, unknown>;
  request_schema?: Record<string, unknown>;
  repository_path?: string;
  expected_base_url?: string;
  required_scopes?: string[];
  execute_live_request?: boolean;
  allow_localhost?: boolean;
}

export interface DashboardOverviewStats {
  total_investigations: number;
  successful_diagnoses: number;
  open_issues: number;
  resolved_issues: number;
  category_distribution: Record<string, number>;
  severity_distribution: Record<string, number>;
  recent_investigations: InvestigationReport[];
  recent_activity: InvestigationStepRecord[];
}

export interface AgentSettings {
  llm_provider: string;
  llm_model: string;
  llm_api_key_configured: boolean;
  llm_base_url: string;
  agent_max_iterations: number;
  http_timeout_seconds: number;
  block_private_networks: boolean;
  allow_localhost_targets: boolean;
  allow_repo_transmission_to_llm: boolean;
  require_approval_for_file_edits: boolean;
  redact_secrets: boolean;
  persist_request_bodies: boolean;
}

export interface AgentSettingsUpdate {
  llm_provider?: "none" | "openai" | "gemini" | "anthropic" | "local";
  llm_model?: string;
  llm_api_key?: string;
  llm_base_url?: string;
  agent_max_iterations?: number;
  http_timeout_seconds?: number;
  block_private_networks?: boolean;
  allow_localhost_targets?: boolean;
  allow_repo_transmission_to_llm?: boolean;
  require_approval_for_file_edits?: boolean;
  redact_secrets?: boolean;
  persist_request_bodies?: boolean;
}
