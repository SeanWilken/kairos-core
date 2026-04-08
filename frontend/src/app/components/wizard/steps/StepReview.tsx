import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Checkbox, cn } from "@kairosstack/ui";

import type { StepProps } from "../types";

export function StepReview({ state, update }: StepProps) {
  const rows = [
    { label: "Tenant", value: `${state.tenant_name || "—"} (${state.tenant_type})` },
    { label: "Model Modes", value: state.model_modes.join(", ") || "—" },
    { label: "Connections", value: `${state.connections.length} configured` },
    { label: "Deploy Target", value: `${state.deployment_target} · ${state.execution_mode}` },
    { label: "Infra Components", value: state.infra_components.join(", ") },
    { label: "Secrets Mode", value: `${state.secrets_mode} → ${state.storage_target}` },
    { label: "Required Keys", value: state.required_keys.length ? state.required_keys.join(", ") : "none" },
    {
      label: "Vector Store",
      value:
        state.vector_store_mode === "enabled"
          ? `${state.vector_provider}${state.namespace_pattern ? ` · ${state.namespace_pattern}` : ""}`
          : "disabled",
    },
    {
      label: "Preflight",
      value:
        state.check_status === "done"
          ? `${state.check_results.filter((r) => r.status === "pass").length} passed, ${state.check_results.filter((r) => r.status === "fail").length} failed`
          : "not run",
    },
    {
      label: "Runtime Verify",
      value:
        state.runtime_check_results.length > 0
          ? `${state.runtime_check_results.filter((r) => r.status === "pass").length} passed, ${state.runtime_check_results.filter((r) => r.status !== "pass").length} not-passed`
          : "not run",
    },
    { label: "Doc Bootstrap", value: state.ingest_now ? `${state.doc_files.length} files · ${state.chunking_profile}` : "disabled" },
    { label: "Artifacts", value: state.gen_status === "done" ? `${state.artifacts.length} files generated` : "not generated" },
  ];

  return (
    <div className="space-y-5">
      {state.gen_status !== "done" && (
        <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-900">Artifacts haven't been generated yet. Go back to Step 6 before completing.</p>
        </div>
      )}

      <div className="border border-zinc-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-zinc-200 bg-zinc-50">
          <h3 className="text-sm font-semibold text-zinc-900">Session Summary</h3>
        </div>
        <div className="divide-y divide-zinc-100">
          {rows.map((r, i) => (
            <div key={`${r.label}-${i}`} className="flex gap-4 px-4 py-2.5">
              <span className="text-xs text-zinc-500 w-36 flex-shrink-0 pt-0.5">{r.label}</span>
              <span className="text-xs text-zinc-800 font-mono break-all">{r.value}</span>
            </div>
          ))}
        </div>
      </div>

      <label className={cn("flex items-start gap-3 p-4 border rounded-lg cursor-pointer transition-colors", state.confirmed ? "border-zinc-900 bg-zinc-50" : "border-zinc-200 bg-white hover:border-zinc-300")}>
        <Checkbox checked={state.confirmed} onCheckedChange={(v) => update({ confirmed: !!v })} className="mt-0.5" />
        <div>
          <p className="text-sm font-medium text-zinc-900">I confirm this configuration is correct and ready to bootstrap</p>
          <p className="text-xs text-zinc-500 mt-0.5">This marks the session as <code className="font-mono bg-zinc-100 px-1 rounded">completed</code> and generates a Studio handoff reference.</p>
        </div>
      </label>

      {state.confirmed && (
        <div className="flex gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
          <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-green-900">Bootstrap session complete</p>
            <p className="text-xs text-zinc-600 mt-0.5">
              <code className="font-mono">BootstrapSession.status = completed</code> · tenant: {state.tenant_name || "unnamed"} · target: {state.deployment_target}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
