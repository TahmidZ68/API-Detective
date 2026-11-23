import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  BookOpen,
  FileCode2,
  FileDown,
  PlusCircle,
  SearchCheck,
  Settings,
  ShieldAlert,
} from "lucide-react";
import { cn } from "../utils/cn";

const navItems = [
  { to: "/", label: "Overview Dashboard", icon: Activity, end: true },
  { to: "/new", label: "New Investigation", icon: PlusCircle },
  { to: "/workspace", label: "Investigation Workspace", icon: SearchCheck },
  { to: "/inspector", label: "Request Inspector", icon: FileCode2 },
  { to: "/reports", label: "Diagnostic Reports", icon: FileDown },
  { to: "/settings", label: "Agent Settings", icon: Settings },
  { to: "/docs", label: "Documentation", icon: BookOpen },
];

export const DashboardLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex bg-[#070b14] text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800/80 bg-[#0b1120] flex flex-col shrink-0">
        <div className="p-5 border-b border-slate-800/80 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <span>API Detective</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800/60">
                v0.1-alpha.2
              </span>
            </div>
            <p className="text-xs text-slate-400">Agentic API Diagnostics</p>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-blue-600/15 text-blue-300 border border-blue-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
                  )
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800/80 text-xs text-slate-400 space-y-1.5">
          <div className="flex items-center justify-between">
            <span>Deterministic Engine</span>
            <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Active
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>SSRF & Redaction</span>
            <span className="text-blue-400 font-mono">Enforced</span>
          </div>
          <div className="text-[11px] text-slate-500 pt-1">
            Investigate • Diagnose • Plan • Fix • Verify
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="max-w-7xl w-full mx-auto p-6 md:p-8 flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
