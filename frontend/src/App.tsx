import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { OverviewDashboard } from "./pages/OverviewDashboard";
import { NewInvestigationPage } from "./pages/NewInvestigationPage";
import { InvestigationWorkspacePage } from "./pages/InvestigationWorkspacePage";
import { RequestInspectorPage } from "./pages/RequestInspectorPage";
import { DiagnosticReportsPage } from "./pages/DiagnosticReportsPage";
import { AgentSettingsPage } from "./pages/AgentSettingsPage";
import { DocumentationPage } from "./pages/DocumentationPage";

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route path="/" element={<OverviewDashboard />} />
        <Route path="/new" element={<NewInvestigationPage />} />
        <Route path="/workspace" element={<InvestigationWorkspacePage />} />
        <Route path="/workspace/:id" element={<InvestigationWorkspacePage />} />
        <Route path="/inspector" element={<RequestInspectorPage />} />
        <Route path="/reports" element={<DiagnosticReportsPage />} />
        <Route path="/settings" element={<AgentSettingsPage />} />
        <Route path="/docs" element={<DocumentationPage />} />
      </Route>
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
};

export default App;
