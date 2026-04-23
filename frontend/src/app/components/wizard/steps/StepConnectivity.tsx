import { AlertTriangle, CheckCheck, ShieldCheck } from "lucide-react";
import { Button, cn } from "@kairosstack/ui";

import { buildPreflightChecks } from "../helpers";
import type { WizardState } from "../types";

export function StepConnectivity({ state, runChecks }: { state: WizardState; runChecks: () => void }) {
  const allDone = state.check_status === "done";
  const allReqPassed = state.check_results.filter((r) => r.required).every((r) => r.status === "pass");
  const statusColor = {
    pass: "text-green-600",
    warn: "text-amber-600",
    fail: "text-red-600",
    pending: "text-zinc-400",
  } as const;
  const statusBg = {
    pass: "bg-green-50 border-green-200",
    warn: "bg-amber-50 border-amber-200",
    fail: "bg-red-50 border-red-200",
    pending: "bg-zinc-50 border-zinc-200",
  } as const;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-zinc-700">Run preflight validation before generating artifacts.</p>
          <p className="text-xs text-zinc-500 mt-1">{buildPreflightChecks(state).length} config checks derived from current selections</p>
        </div>
        <Button onClick={runChecks} className="flex-shrink-0">
          Run Preflight
        </Button>
      </div>

      {state.check_results.length > 0 && (
        <div className="space-y-2">
          {state.check_results.map((c, i) => (
            <div key={`${c.name}-${i}`} className={cn("flex items-center gap-3 p-3 border rounded-lg", statusBg[c.status])}>
              <div className={cn("h-2 w-2 rounded-full flex-shrink-0", {
                "bg-green-500": c.status === "pass",
                "bg-amber-500": c.status === "warn",
                "bg-red-500": c.status === "fail",
                "bg-zinc-300": c.status === "pending",
              })} />
              <span className="text-sm font-medium text-zinc-900 w-44 flex-shrink-0">{c.label}</span>
              <span className="text-xs text-zinc-600 flex-1">{c.message || "—"}</span>
              <span className={cn("text-xs font-semibold", statusColor[c.status])}>{c.status}</span>
            </div>
          ))}
        </div>
      )}

      {state.check_status === "idle" && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <ShieldCheck className="h-8 w-8 text-zinc-300 mb-3" />
          <p className="text-sm text-zinc-500">No preflight run yet.</p>
          <p className="text-xs text-zinc-400 mt-1">Run preflight to validate configuration dependencies.</p>
        </div>
      )}

      {allDone && (
        <div className={cn("flex gap-3 p-4 rounded-lg border", allReqPassed ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200")}>
          {allReqPassed ? <CheckCheck className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" /> : <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />}
          <div>
            <p className={cn("text-sm font-semibold", allReqPassed ? "text-green-900" : "text-amber-900")}>
              {allReqPassed ? "All required preflight checks passed" : "Resolve required failures before continuing"}
            </p>
            <p className="text-xs text-zinc-600 mt-0.5">
              {state.check_results.filter((r) => r.status === "pass").length} passed · {state.check_results.filter((r) => r.status === "fail").length} failed
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
