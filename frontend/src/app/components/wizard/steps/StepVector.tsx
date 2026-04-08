import { AlertTriangle, Layers } from "lucide-react";
import { Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, cn } from "@kairosstack/ui";

import type { StepProps, VectorMode } from "../types";

export function StepVector({ state, update }: StepProps) {
  const pgvDep = state.vector_provider === "pgvector" && (!state.infra_components.includes("postgres") || !state.infra_components.includes("pgvector"));

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>Vector Store Mode</Label>
        <div className="grid grid-cols-2 gap-3">
          {(["disabled", "enabled"] as VectorMode[]).map((m) => (
            <button
              key={m}
              onClick={() => update({ vector_store_mode: m })}
              className={cn(
                "p-3.5 border rounded-lg text-sm font-medium transition-colors text-left",
                state.vector_store_mode === m ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-400"
              )}
            >
              {m === "enabled" ? "Enabled — configure RAG" : "Disabled"}
            </button>
          ))}
        </div>
      </div>

      {state.vector_store_mode === "enabled" && (
        <>
          <div className="space-y-2">
            <Label>Provider</Label>
            <div className="flex gap-3">
              {([
                { id: "pgvector", badge: "MVP" },
                { id: "pinecone", badge: "Soon" },
              ] as const).map(({ id, badge }) => (
                <button
                  key={id}
                  onClick={() => update({ vector_provider: id })}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2.5 border rounded-lg text-sm font-medium transition-colors",
                    state.vector_provider === id ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300"
                  )}
                >
                  <span className="font-mono">{id}</span>
                  <span className={cn("text-xs px-1.5 py-0.5 rounded", badge === "MVP" ? "bg-green-100 text-green-700" : "bg-zinc-100 text-zinc-500", state.vector_provider === id && "bg-white/20 text-white")}>{badge}</span>
                </button>
              ))}
            </div>
          </div>

          {pgvDep && (
            <div className="flex gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800">pgvector requires <code className="font-mono bg-amber-100 px-1 rounded">postgres</code> and <code className="font-mono bg-amber-100 px-1 rounded">pgvector</code> in Step 2.</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Namespace Pattern <span className="text-zinc-400 font-normal">(optional)</span></Label>
              <Input value={state.namespace_pattern} onChange={(e) => update({ namespace_pattern: e.target.value })} placeholder="{org}-{division}" className="font-mono text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label>Index Strategy</Label>
              <Select value={state.index_strategy} onValueChange={(v) => update({ index_strategy: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent className="kairos-overlay-content kairos-select-content">
                  <SelectItem value="flat" className="kairos-overlay-item">flat</SelectItem>
                  <SelectItem value="hnsw" className="kairos-overlay-item">hnsw</SelectItem>
                  <SelectItem value="ivfflat" className="kairos-overlay-item">ivfflat</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {state.vector_provider === "pinecone" && (
            <div className="space-y-1.5">
              <Label>Pinecone Endpoint <span className="text-red-500">*</span></Label>
              <Input
                value={state.vector_endpoint}
                onChange={(e) => update({ vector_endpoint: e.target.value })}
                placeholder="https://index.svc.environment.pinecone.io"
                className="font-mono text-sm"
              />
            </div>
          )}
        </>
      )}

      {state.vector_store_mode === "disabled" && (
        <div className="flex items-center justify-center py-8 text-sm text-zinc-400">
          <Layers className="h-4 w-4 mr-2" />
          Vector store disabled — RAG capabilities will not be available.
        </div>
      )}
    </div>
  );
}
