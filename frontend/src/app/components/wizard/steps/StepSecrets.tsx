import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Switch, cn } from "@myai-tech/myui";

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
          google: "GEMINI_API_KEY",
          custom: "CUSTOM_API_KEY",
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

  const setLocalSecretValue = (key: string, value: string) => {
    update({ local_secret_values: { ...state.local_secret_values, [key]: value } });
  };

  const setLocalOverride = (key: string, value: string) => {
    update({ local_env_overrides: { ...state.local_env_overrides, [key]: value } });
  };

  const isSensitiveKey = (key: string) => /password|secret|token|api_key/i.test(key);

  return (
    <div className="space-y-6">
      <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-amber-900 leading-relaxed">
          <strong>Security policy:</strong> Raw secret values are never persisted server-side. This wizard stores only key names (auth refs). If you choose local file generation, values are used only on your machine to materialize local `.env` files.
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
          <SelectContent className="myai-overlay-content myai-select-content">
            <SelectItem value="env_file" className="myai-overlay-item">.env file</SelectItem>
            <SelectItem value="vault" className="myai-overlay-item">HashiCorp Vault</SelectItem>
            <SelectItem value="aws_ssm" className="myai-overlay-item">AWS SSM Parameter Store</SelectItem>
            <SelectItem value="github_secrets" className="myai-overlay-item">GitHub Secrets</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Required Key Names</Label>
        <p className="text-xs text-zinc-500">Auto-populated from runtime config. Add additional keys as needed.</p>
        <TagInput values={state.required_keys} onChange={(v) => update({ required_keys: v })} placeholder="MY_CUSTOM_KEY" />
      </div>

      <div className="space-y-3 border border-zinc-200 rounded-lg bg-zinc-50 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-zinc-900">Generate populated local <code className="font-mono bg-zinc-200 px-1 rounded">.env</code></p>
            <p className="text-xs text-zinc-500 mt-1">Optional for local setup convenience. Values remain local in your browser session and are only written to generated files when enabled.</p>
          </div>
          <Switch checked={state.materialize_local_env} onCheckedChange={(v) => update({ materialize_local_env: v })} />
        </div>

        {state.materialize_local_env && (
          <div className="space-y-4">
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              Generated <code className="font-mono bg-amber-100 px-1 rounded">.env</code> files can contain secrets. Keep them local and never commit them.
            </div>

            {state.infra_components.includes("postgres") && (
              <div className="space-y-2">
                <Label>PostgreSQL Local Overrides</Label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    ["POSTGRES_HOST", "localhost"],
                    ["POSTGRES_PORT", "5432"],
                    ["POSTGRES_DB", "myai"],
                    ["POSTGRES_USER", "myai"],
                  ].map(([key, fallback]) => (
                    <div key={key} className="space-y-1">
                      <Label className="text-xs text-zinc-600">{key}</Label>
                      <Input
                        value={state.local_env_overrides[key] ?? fallback}
                        onChange={(e) => setLocalOverride(key, e.target.value)}
                        className="font-mono text-xs"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label>Key Values for Local Materialization</Label>
              {state.required_keys.length === 0 ? (
                <p className="text-xs text-zinc-500">No required keys detected yet.</p>
              ) : (
                <div className="space-y-2">
                  {state.required_keys.map((key) => (
                    <div key={key} className="grid grid-cols-[210px_1fr] items-center gap-3">
                      <code className="text-xs font-mono text-zinc-700">{key}</code>
                      <Input
                        type={isSensitiveKey(key) ? "password" : "text"}
                        value={state.local_secret_values[key] ?? ""}
                        onChange={(e) => setLocalSecretValue(key, e.target.value)}
                        placeholder={isSensitiveKey(key) ? "paste value" : "optional"}
                        className="font-mono text-xs"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
