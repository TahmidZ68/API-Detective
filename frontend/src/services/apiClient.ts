import type {
  AgentSettings,
  AgentSettingsUpdate,
  DashboardOverviewStats,
  InvestigationReport,
  InvestigationRequestPayload,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

async function requestJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    let errMessage = `HTTP ${response.status}`;
    try {
      const errBody = await response.json();
      if (errBody?.detail?.message) {
        errMessage = errBody.detail.message;
      } else if (errBody?.message) {
        errMessage = errBody.message;
      } else if (typeof errBody?.detail === "string") {
        errMessage = errBody.detail;
      }
    } catch {
      // keep default status text
    }
    throw new Error(errMessage);
  }
  return (await response.json()) as T;
}

export const apiClient = {
  getDashboardOverview(): Promise<DashboardOverviewStats> {
    return requestJSON<DashboardOverviewStats>("/dashboard/overview");
  },

  listInvestigations(limit = 50): Promise<InvestigationReport[]> {
    return requestJSON<InvestigationReport[]>(`/investigations?limit=${limit}`);
  },

  getInvestigation(id: string): Promise<InvestigationReport> {
    return requestJSON<InvestigationReport>(`/investigations/${encodeURIComponent(id)}`);
  },

  createInvestigation(payload: InvestigationRequestPayload): Promise<InvestigationReport> {
    return requestJSON<InvestigationReport>("/investigations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  approveFix(
    investigationId: string,
    fixId: string,
    applyChanges = true,
    runVerification = true
  ): Promise<InvestigationReport> {
    return requestJSON<InvestigationReport>(
      `/investigations/${encodeURIComponent(investigationId)}/approve-fix`,
      {
        method: "POST",
        body: JSON.stringify({
          fix_id: fixId,
          approved: true,
          apply_changes: applyChanges,
          run_verification: runVerification,
        }),
      }
    );
  },

  async exportReport(
    investigationId: string,
    format: "json" | "markdown" | "html"
  ): Promise<string> {
    const response = await fetch(
      `${API_BASE}/investigations/${encodeURIComponent(investigationId)}/export?format=${format}`
    );
    if (!response.ok) {
      throw new Error(`Failed to export report (HTTP ${response.status})`);
    }
    return await response.text();
  },

  getSettings(): Promise<AgentSettings> {
    return requestJSON<AgentSettings>("/settings");
  },

  updateSettings(payload: AgentSettingsUpdate): Promise<AgentSettings> {
    return requestJSON<AgentSettings>("/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
};
