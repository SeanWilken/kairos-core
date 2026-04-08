import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, cn } from "@kairosstack/ui";

import { TagInput } from "../common";
import type { StepProps } from "../types";

export function StepSecrets({ state, update }: StepProps) {
  useEffect(() => {
    const auto: string[] = [];
    state.connections.forEach((c) => {
      if (c.mode === "api_provider") {
        const keyMap: Record<string, string> = {
          openai: "OPENAI_API_KEY",
          anthropic: "ANTHROPIC_API_KEY",
          google: "GOOGLE_AI_API_KEY",
          azure_openai: "AZURE_OPENAI_API_KEY",
        };
        const key = keyMap[c.provider];
        if (key && !auto.includes(key)) auto.push(key);
      }
    });
    if (state.infra_components.includes("postgres") && !auto.includes("POSTGRES_PASSWORD")) auto.push("POSTGRES_PASSWORD");
    const merged = [...new Set([...auto, ...state.required_keys])];
    if (merged.join() !== state.required_keys.join()) update({ required_keys: merged });
  }, [state.connections, state.infra_components, state.required_keys, update]);

  const modes = [
    { id: "template_only", label: "Template Only", desc: "Generate .env.template — no values collected" },
    { id: "transient_validate_only", label: "Transient Validate", desc: "Values used for checks then immediately discarded" },
    { id: "pipeline_injected", label: "Pipeline Injected", desc: "CI/CD injects values at runtime" },
  ] as const;

  return (
    <div className="space-y-6">
      <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-amber-900 leading-relaxed">
          <strong>Security policy:</strong> Raw secret values are never persisted. This wizard stores only key names (auth refs). Values are injected via your chosen storage target at deploy time.
        </div>
      </div>

      <div className="space-y-2">
        <Label>Secrets Mode</Label>
        <div className="space-y-2">
          {modes.map((m) => (
            <label key={m.id} className={cn("flex items-start gap-3 p-3.5 border rounded-lg cursor-pointer transition-colors", state.secrets_mode === m.id ? "border-zinc-900 bg-zinc-50" : "border-zinc-200 bg-white hover:border-zinc-300")}>
              <input type="radio" name="secrets_mode" value={m.id} checked={state.secrets_mode === m.id} onChange={() => update({ secrets_mode: m.id })} className="mt-0.5" />
              <div>
                <div className="text-sm font-medium text-zinc-900">{m.label}</div>
                <p className="text-xs text-zinc-500 mt-0.5">{m.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>Storage Target</Label>
        <Select value={state.storage_target} onValueChange={(v) => update({ storage_target: v })}>
          <SelectTrigger className="w-64"><SelectValue /></SelectTrigger>
          <SelectContent className="kairos-overlay-content kairos-select-content">
            <SelectItem value="env_file" className="kairos-overlay-item">.env file</SelectItem>
            <SelectItem value="vault" className="kairos-overlay-item">HashiCorp Vault</SelectItem>
            <SelectItem value="aws_ssm" className="kairos-overlay-item">AWS SSM Parameter Store</SelectItem>
            <SelectItem value="github_secrets" className="kairos-overlay-item">GitHub Secrets</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Required Key Names</Label>
        <p className="text-xs text-zinc-500">Auto-populated from runtime config. Add additional keys as needed.</p>
        <TagInput values={state.required_keys} onChange={(v) => update({ required_keys: v })} placeholder="MY_CUSTOM_KEY" />
      </div>
    </div>
  );
}
