import { AlertCircle, AlertTriangle, Plus, Trash2 } from "lucide-react";
import { Badge, Button, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, cn } from "@myai-tech/myui";

import type { Connection, ModelMode, StepProps } from "../types";

const API_DEFAULTS: Record<string, { endpoint: string; model: string }> = {
  openai: { endpoint: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  anthropic: { endpoint: "https://api.anthropic.com", model: "claude-3-5-sonnet-latest" },
  google: { endpoint: "https://generativelanguage.googleapis.com/v1beta", model: "gemini-2.5-flash" },
  custom: { endpoint: "https://api.example.com/v1", model: "model-name" },
};

const LOCAL_DEFAULTS: Record<string, { endpoint: string; model: string }> = {
  ollama: { endpoint: "http://localhost:11434", model: "llama3.1" },
  lmstudio: { endpoint: "http://localhost:1234", model: "local-model" },
  custom: { endpoint: "http://localhost:9000", model: "local-model" },
};

export function StepRuntime({ state, update }: StepProps) {
  const toggleMode = (m: ModelMode) => {
    const next = state.model_modes.includes(m) ? state.model_modes.filter((x) => x !== m) : [...state.model_modes, m];
    if (next.length === 0) return;
    update({ model_modes: next });
  };

  const addConn = (mode: ModelMode) => {
    update({
      connections: [
        ...state.connections,
        {
          id: Date.now().toString(),
          mode,
          provider: mode === "api_provider" ? "openai" : "ollama",
          endpoint: mode === "api_provider" ? "https://api.openai.com/v1" : "http://localhost:11434",
          model_ref: "",
          priority: state.connections.length + 1,
        },
      ],
    });
  };

  const updConn = (id: string, key: keyof Connection, value: string | number) => {
    if (key === "provider") {
      const conn = state.connections.find((c) => c.id === id);
      if (!conn) return;
      const defaults = conn.mode === "api_provider" ? API_DEFAULTS[String(value)] : LOCAL_DEFAULTS[String(value)];
      update({
        connections: state.connections.map((c) =>
          c.id === id
            ? {
                ...c,
                provider: value as Connection["provider"],
                endpoint: defaults?.endpoint ?? c.endpoint,
                model_ref: defaults?.model ?? c.model_ref,
              }
            : c
        ),
      });
      return;
    }
    update({ connections: state.connections.map((c) => (c.id === id ? { ...c, [key]: value } : c)) });
  };

  const delConn = (id: string) => {
    update({ connections: state.connections.filter((c) => c.id !== id) });
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label>Tenant Name</Label>
          <Input value={state.tenant_name} onChange={(e) => update({ tenant_name: e.target.value })} placeholder="my-ai-workspace" />
        </div>
        <div className="space-y-1.5">
          <Label>Tenant Type</Label>
          <Select value={state.tenant_type} onValueChange={(v) => update({ tenant_type: v as "company" | "individual" })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent className="myai-overlay-content myai-select-content">
              <SelectItem value="company" className="myai-overlay-item">Company</SelectItem>
              <SelectItem value="individual" className="myai-overlay-item">Individual</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label>Model Modes</Label>
        <p className="text-xs text-zinc-500">Select all deployment modes you want to configure.</p>
        <div className="flex gap-3">
          {(["api_provider", "local_model"] as ModelMode[]).map((m) => (
            <button
              key={m}
              onClick={() => toggleMode(m)}
              className={cn(
                "flex-1 px-4 py-3 rounded-lg border text-sm font-medium text-left transition-colors",
                state.model_modes.includes(m) ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-400"
              )}
            >
              {m === "api_provider" ? "API Provider" : "Local Model"}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label>Connections</Label>
          <div className="flex gap-2">
            {state.model_modes.includes("api_provider") && (
              <Button variant="outline" size="sm" onClick={() => addConn("api_provider")} className="text-xs">
                <Plus className="h-3.5 w-3.5 mr-1" /> API Connection
              </Button>
            )}
            {state.model_modes.includes("local_model") && (
              <Button variant="outline" size="sm" onClick={() => addConn("local_model")} className="text-xs">
                <Plus className="h-3.5 w-3.5 mr-1" /> Local Connection
              </Button>
            )}
          </div>
        </div>
        <div className="space-y-3">
          {state.connections.map((conn) => (
            <div key={conn.id} className="border border-zinc-200 rounded-lg p-4 bg-white space-y-3">
              <div className="flex items-center justify-between">
                <Badge variant={conn.mode === "api_provider" ? "default" : "secondary"} className="text-xs">
                  {conn.mode === "api_provider" ? "API" : "Local"}
                </Badge>
                {state.connections.length > 1 && (
                  <Button variant="ghost" size="sm" onClick={() => delConn(conn.id)} className="h-7 w-7 p-0 text-zinc-400 hover:text-red-500">
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Provider</Label>
                  <Select value={conn.provider} onValueChange={(v) => updConn(conn.id, "provider", v)}>
                    <SelectTrigger className="text-xs h-8"><SelectValue /></SelectTrigger>
                    <SelectContent className="myai-overlay-content myai-select-content">
                      {conn.mode === "api_provider"
                        ? ["openai", "anthropic", "google", "custom"].map((p) => <SelectItem key={p} value={p} className="myai-overlay-item text-xs">{p}</SelectItem>)
                        : ["ollama", "lmstudio", "custom"].map((p) => <SelectItem key={p} value={p} className="myai-overlay-item text-xs">{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Endpoint</Label>
                  <Input value={conn.endpoint} onChange={(e) => updConn(conn.id, "endpoint", e.target.value)} className="text-xs h-8 font-mono" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Model Ref</Label>
                  <Input value={conn.model_ref} onChange={(e) => updConn(conn.id, "model_ref", e.target.value)} placeholder="gpt-4o-mini" className="text-xs h-8 font-mono" />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Label className="text-xs text-zinc-500">Priority</Label>
                <Input
                  type="number"
                  value={conn.priority}
                  onChange={(e) => updConn(conn.id, "priority", Number.parseInt(e.target.value, 10) || 1)}
                  min={1}
                  max={10}
                  className="w-16 h-7 text-xs"
                />
                <span className="text-xs text-zinc-400">(1 = primary)</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {state.model_modes.includes("api_provider") && (
        <div className="flex gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <AlertCircle className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-blue-800">OpenAI, Anthropic, and Google are supported out of the box. API keys are configured in Step 3; only key names are stored in this session.</p>
        </div>
      )}

      {state.model_modes.includes("local_model") && (
        <div className="flex gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-800">Add <code className="font-mono bg-amber-100 px-1 rounded">local_model_runtime</code> in Step 2 to scaffold runtime services.</p>
        </div>
      )}
    </div>
  );
}
