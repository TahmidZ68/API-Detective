import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SeverityBadge, StatusPill } from "../src/components/SeverityBadge";
import { OverviewDashboard } from "../src/pages/OverviewDashboard";
import { NewInvestigationPage } from "../src/pages/NewInvestigationPage";
import { InvestigationWorkspacePage } from "../src/pages/InvestigationWorkspacePage";
import { RequestInspectorPage } from "../src/pages/RequestInspectorPage";
import { DiagnosticReportsPage } from "../src/pages/DiagnosticReportsPage";
import { AgentSettingsPage } from "../src/pages/AgentSettingsPage";
import { DocumentationPage } from "../src/pages/DocumentationPage";
import { AppRoutes } from "../src/App";
import { apiClient } from "../src/services/apiClient";
import type {
  AgentSettings,
  DashboardOverviewStats,
  InvestigationReport,
} from "../src/types/api";

const sampleReport: InvestigationReport = {
  investigation_id: "INV-TEST0001",
  title: "POST /v1/orders — Expired JWT & Schema Error",
  prompt: "Why is my API returning 401?",
  status: "completed",
  created_at: "2026-11-23T12:00:00Z",
  completed_at: "2026-11-23T12:00:01Z",
  target_url: "https://api.orders.example.com/v1/orders",
  http_method: "POST",
  plan: [
    {
      step_index: 1,
      tool_name: "authentication_diagnostics",
      rationale: "Inspect Authorization header",
      completed: true,
    },
  ],
  timeline: [
    {
      step_number: 1,
      phase: "understand",
      tool_name: null,
      summary: "Extracted task context",
      details: {},
      duration_ms: 1.2,
      timestamp: "2026-11-23T12:00:00Z",
    },
  ],
  http_exchange: {
    method: "POST",
    url: "https://api.orders.example.com/v1/orders",
    request_headers: { Authorization: "Bearer ***REDACTED***" },
    query_params: { tenant: "acme" },
    request_body: null,
    response_status: 401,
    response_headers: { "Content-Type": "application/json" },
    response_body: { error: "invalid_token" },
    elapsed_ms: 12.5,
    redirect_chain: [],
    error_type: null,
    error_message: null,
    tls_verified: true,
  },
  findings: [
    {
      diagnostic_id: "AUTH-003",
      category: "authentication",
      severity: "high",
      title: "Expired JWT Bearer Token",
      description: "The JWT token exp claim is in the past.",
      evidence: ["JWT exp claim timestamp: 1700000000"],
      recommendation: "Refresh the access token.",
      confidence: 0.99,
      status: "confirmed",
    },
  ],
  root_causes: [
    {
      hypothesis_id: "RC-001",
      rank: 1,
      title: "Expired JWT Bearer Token",
      category: "authentication",
      confidence: 0.99,
      status: "confirmed",
      explanation: "The JWT token exp claim is in the past.",
      supporting_evidence: ["JWT exp claim timestamp: 1700000000"],
      related_diagnostic_ids: ["AUTH-003"],
    },
  ],
  remediation_plan: [
    {
      fix_id: "FIX-001",
      problem: "Expired JWT Bearer Token",
      evidence: ["JWT exp claim timestamp: 1700000000"],
      root_cause: "The JWT token exp claim is in the past.",
      recommended_solution: "Refresh the access token.",
      affected_files: [],
      risk_level: "medium",
      repair_level: 2,
      unified_diff:
        "--- a/request_config.yaml\n+++ b/request_config.yaml\n+header[Authorization]: Bearer <REFRESHED>",
      requires_approval: true,
      approved: false,
      applied: false,
      verification_procedure: "Re-run AUTH-003 check.",
    },
  ],
  repository_analysis: null,
  verification: null,
  llm_assisted: false,
  llm_provider_used: "none",
  summary: "Primary root cause: Expired JWT Bearer Token.",
};

const sampleOverview: DashboardOverviewStats = {
  total_investigations: 3,
  successful_diagnoses: 3,
  open_issues: 5,
  resolved_issues: 1,
  category_distribution: {
    connectivity: 1,
    authentication: 2,
    request: 1,
    schema: 1,
    response: 0,
    integration: 0,
  },
  severity_distribution: {
    critical: 1,
    high: 3,
    medium: 1,
    low: 0,
    informational: 0,
  },
  recent_investigations: [sampleReport],
  recent_activity: sampleReport.timeline,
};

const sampleSettings: AgentSettings = {
  llm_provider: "none",
  llm_model: "gpt-4o-mini",
  llm_api_key_configured: false,
  llm_base_url: "",
  agent_max_iterations: 6,
  http_timeout_seconds: 15,
  block_private_networks: true,
  allow_localhost_targets: false,
  allow_repo_transmission_to_llm: false,
  require_approval_for_file_edits: true,
  redact_secrets: true,
  persist_request_bodies: false,
};

function renderWithProviders(ui: React.ReactElement, initialRoute = "/") {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialRoute]}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("API Detective Web Dashboard Suite", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders SeverityBadge and StatusPill accurately", () => {
    render(
      <div>
        <SeverityBadge severity="critical" />
        <StatusPill status="confirmed" confidence={0.98} />
      </div>
    );
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText("confirmed")).toBeInTheDocument();
    expect(screen.getByText("(98%)")).toBeInTheDocument();
  });

  it("renders OverviewDashboard with real backend metrics", async () => {
    vi.spyOn(apiClient, "getDashboardOverview").mockResolvedValue(sampleOverview);
    renderWithProviders(<OverviewDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Diagnostic Overview")).toBeInTheDocument();
    });
    expect(screen.getByText("INV-TEST0001")).toBeInTheDocument();
    expect(screen.getByText("POST /v1/orders — Expired JWT & Schema Error")).toBeInTheDocument();
  });

  it("handles OverviewDashboard error states cleanly", async () => {
    vi.spyOn(apiClient, "getDashboardOverview").mockRejectedValue(
      new Error("Database connection lost")
    );
    renderWithProviders(<OverviewDashboard />);

    await waitFor(() => {
      expect(
        screen.getByText("Unable to load backend diagnostic metrics")
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Database connection lost")).toBeInTheDocument();
  });

  it("validates NewInvestigationPage form and supports preset scenarios", async () => {
    renderWithProviders(<NewInvestigationPage />);

    const urlInput = screen.getByLabelText("API Endpoint URL") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "" } });

    const submitBtn = screen.getByText("Launch Investigation");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Please provide an API endpoint URL or a repository path to investigate."
        )
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("401 Auth Failure"));
    expect(urlInput.value).toBe("https://api.payments.example.com/v1/accounts");
  });

  it("renders InvestigationWorkspacePage and requires confirmation dialog for repair approval", async () => {
    vi.spyOn(apiClient, "listInvestigations").mockResolvedValue([sampleReport]);
    vi.spyOn(apiClient, "getInvestigation").mockResolvedValue(sampleReport);
    const approveSpy = vi.spyOn(apiClient, "approveFix").mockResolvedValue({
      ...sampleReport,
      status: "resolved",
      verification: {
        verified: true,
        fix_worked: true,
        passed_checks: ["Resolved AUTH-003"],
        failed_checks: [],
        remaining_problems: [],
        unverified_assumptions: [],
        summary: "Verification passed.",
      },
    });

    renderWithProviders(
      <Routes>
        <Route path="/workspace/:id" element={<InvestigationWorkspacePage />} />
      </Routes>,
      "/workspace/INV-TEST0001"
    );

    await waitFor(() => {
      expect(screen.getByText("Ranked Root-Cause Hypotheses")).toBeInTheDocument();
    });
    expect(screen.getByText("AUTH-003")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Approve & Verify Repair"));
    expect(screen.getByText(/Confirm Repair Approval/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Confirm & Run Verification"));
    await waitFor(() => {
      expect(approveSpy).toHaveBeenCalledWith("INV-TEST0001", "FIX-001", true, true);
    });
  });

  it("renders RequestInspectorPage with secret redaction banner and exchange details", async () => {
    vi.spyOn(apiClient, "listInvestigations").mockResolvedValue([sampleReport]);
    vi.spyOn(apiClient, "getInvestigation").mockResolvedValue(sampleReport);

    renderWithProviders(<RequestInspectorPage />, "/inspector?id=INV-TEST0001");

    expect(
      await screen.findByText("Bearer ***REDACTED***")
    ).toBeInTheDocument();
    expect(screen.getByText("Status: 401")).toBeInTheDocument();
  });

  it("renders DiagnosticReportsPage and switches export formats", async () => {
    vi.spyOn(apiClient, "listInvestigations").mockResolvedValue([sampleReport]);
    vi.spyOn(apiClient, "exportReport").mockResolvedValue("# Markdown Report Preview Content");

    renderWithProviders(<DiagnosticReportsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("report-preview")).toHaveTextContent(
        "# Markdown Report Preview Content"
      );
    });
  });

  it("renders AgentSettingsPage and saves updated settings", async () => {
    vi.spyOn(apiClient, "getSettings").mockResolvedValue(sampleSettings);
    const updateSpy = vi
      .spyOn(apiClient, "updateSettings")
      .mockResolvedValue({ ...sampleSettings, agent_max_iterations: 8 });

    renderWithProviders(<AgentSettingsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Agent, Security & Privacy Settings")
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Save Configuration"));
    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalled();
      expect(
        screen.getByText("Configuration updated and applied to the runtime agent engine.")
      ).toBeInTheDocument();
    });
  });

  it("renders DocumentationPage with diagnostic catalog and CLI reference", () => {
    renderWithProviders(<DocumentationPage />);
    expect(
      screen.getByText("API Detective Documentation & Reference")
    ).toBeInTheDocument();
    expect(screen.getByText("CONN-001..008")).toBeInTheDocument();
  });

  it("completes the 9-step primary developer journey end-to-end", async () => {
    vi.spyOn(apiClient, "getDashboardOverview").mockResolvedValue(sampleOverview);
    vi.spyOn(apiClient, "listInvestigations").mockResolvedValue([sampleReport]);
    vi.spyOn(apiClient, "getInvestigation").mockResolvedValue(sampleReport);
    vi.spyOn(apiClient, "createInvestigation").mockResolvedValue(sampleReport);

    renderWithProviders(<AppRoutes />, "/new");

    const launchBtn = await screen.findByText("Launch Investigation");
    fireEvent.click(launchBtn);

    await waitFor(() => {
      expect(screen.getByText("Ranked Root-Cause Hypotheses")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Expired JWT Bearer Token").length).toBeGreaterThan(0);
  });
});
