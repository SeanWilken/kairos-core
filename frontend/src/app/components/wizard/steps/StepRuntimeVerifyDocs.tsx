import { useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, FileUp, Loader2 } from "lucide-react";
import { Button, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Switch, cn } from "@kairosstack/ui";

import { runRuntimeChecks } from "../helpers";
import type { StepProps } from "../types";

const FAKE_FILES = [".rfc/rfc-001.md", "docs/architecture.md", "docs/api-reference.md"];

export function StepRuntimeVerifyDocs({ state, update }: StepProps) {
  const [running, setRunning] = useState(false);
  const runtimeReady = state.runtime_check_results.length > 0 && state.runtime_check_results.filter((r) => r.required).every((r) => r.status === "pass");

  const onRunRuntimeChecks = async () => {
    setRunning(true);
    update({ runtime_check_status: "running" });
    const results = await runRuntimeChecks(state);
    update({ runtime_check_results: results, runtime_check_status: "done" });
    setRunning(false);
  };

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Label>Core Base URL</Label>
        <Input
          value={state.runtime_base_url}
          onChange={(e) => update({ runtime_base_url: e.target.value })}
          placeholder="http://localhost:8000"
          className="font-mono"
        />
        <div className="flex items-center gap-3">
          <Button onClick={onRunRuntimeChecks} disabled={running}>
            {running ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Running Checks…</> : "Run Runtime Checks"}
          </Button>
          <span className="text-xs text-zinc-500">Runs only checks relevant to your selected options.</span>
        </div>
      </div>

      {state.runtime_check_results.length > 0 && (
        <div className="space-y-2">
          {state.runtime_check_results.map((c, i) => (
            <div key={`${c.name}-${i}`} className={cn("flex items-center gap-3 p-3 border rounded-lg", c.status === "pass" ? "bg-green-50 border-green-200" : c.status === "fail" ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200")}>
              <div className={cn("h-2 w-2 rounded-full", c.status === "pass" ? "bg-green-500" : c.status === "fail" ? "bg-red-500" : "bg-amber-500")} />
              <span className="text-sm font-medium text-zinc-900 w-56 flex-shrink-0">{c.label}</span>
              <span className="text-xs text-zinc-600 flex-1">{c.message}</span>
              <span className="text-xs font-semibold uppercase text-zinc-600">{c.status}</span>
            </div>
          ))}
        </div>
      )}

      {!runtimeReady && (
        <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-900">Document upload remains locked until all required runtime checks pass.</p>
        </div>
      )}

      {runtimeReady && (
        <>
          <div className="flex items-center justify-between p-4 border border-zinc-200 rounded-lg bg-white">
            <div>
              <p className="text-sm font-medium text-zinc-900">Bootstrap document corpus now</p>
              <p className="text-xs text-zinc-500 mt-0.5">Upload documents only after runtime and DB/vector checks are passing.</p>
            </div>
            <Switch checked={state.ingest_now} onCheckedChange={(v) => update({ ingest_now: v })} />
          </div>

          {state.ingest_now && (
            <>
              <div className="space-y-2">
                <Label>Source Files</Label>
                <div
                  className={cn("border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors", state.doc_files.length > 0 ? "border-zinc-300 bg-zinc-50" : "border-zinc-200 hover:border-zinc-300 bg-white")}
                  onClick={() => state.doc_files.length === 0 && update({ doc_files: FAKE_FILES })}
                >
                  {state.doc_files.length === 0 ? (
                    <div>
                      <FileUp className="h-6 w-6 text-zinc-400 mx-auto mb-2" />
                      <p className="text-sm text-zinc-600 font-medium">Click to select files</p>
                    </div>
                  ) : (
                    <div className="space-y-2 text-left">
                      {state.doc_files.map((f) => (
                        <div key={f} className="flex items-center gap-2 px-3 py-2 bg-white border border-zinc-200 rounded">
                          <FileText className="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
                          <span className="text-xs text-zinc-700 flex-1 font-mono">{f}</span>
                          <button onClick={(e) => { e.stopPropagation(); update({ doc_files: state.doc_files.filter((x) => x !== f) }); }} className="text-zinc-400 hover:text-red-500 transition-colors text-xs">✕</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>Chunking Profile</Label>
                  <Select value={state.chunking_profile} onValueChange={(v) => update({ chunking_profile: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent className="kairos-overlay-content kairos-select-content">
                      <SelectItem value="recursive_512" className="kairos-overlay-item">recursive_512 (default)</SelectItem>
                      <SelectItem value="markdown_sections" className="kairos-overlay-item">markdown_sections</SelectItem>
                      <SelectItem value="sentence_window" className="kairos-overlay-item">sentence_window</SelectItem>
                      <SelectItem value="fixed_256" className="kairos-overlay-item">fixed_256</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Embedding Profile</Label>
                  <Select value={state.embedding_profile} onValueChange={(v) => update({ embedding_profile: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent className="kairos-overlay-content kairos-select-content">
                      <SelectItem value="default" className="kairos-overlay-item">default (provider default)</SelectItem>
                      <SelectItem value="text-embedding-3-small" className="kairos-overlay-item">text-embedding-3-small</SelectItem>
                      <SelectItem value="text-embedding-3-large" className="kairos-overlay-item">text-embedding-3-large</SelectItem>
                      <SelectItem value="nomic-embed-text" className="kairos-overlay-item">nomic-embed-text (local)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {state.ingest_status === "done" ? (
                <div className="flex gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
                  <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-green-900">Ingest complete</p>
                    <p className="text-xs text-zinc-600 mt-0.5">{state.doc_files.length} file(s) staged for ingest · profile: {state.chunking_profile}</p>
                  </div>
                </div>
              ) : state.doc_files.length > 0 ? (
                <Button onClick={() => update({ ingest_status: "done" })}>Run Ingest</Button>
              ) : null}
            </>
          )}
        </>
      )}
    </div>
  );
}
