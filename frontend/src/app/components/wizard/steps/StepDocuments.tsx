import { FileText, FileUp, Layers } from "lucide-react";
import { Button, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Switch, cn } from "@myai-tech/myui";

import type { StepProps } from "../types";

const FAKE_FILES = [".rfc/rfc-001.md", "docs/architecture.md", "docs/api-reference.md"];

export function StepDocuments({ state, update }: StepProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between p-4 border border-zinc-200 rounded-lg bg-white">
        <div>
          <p className="text-sm font-medium text-zinc-900">Bootstrap document corpus now</p>
          <p className="text-xs text-zinc-500 mt-0.5">Ingest documents into your vector store as part of this setup session</p>
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
                  <p className="text-xs text-zinc-400 mt-1">or drag and drop</p>
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
                  <p className="text-xs text-zinc-400 mt-2 text-center">Click to add more files</p>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Chunking Profile</Label>
              <Select value={state.chunking_profile} onValueChange={(v) => update({ chunking_profile: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent className="myai-overlay-content myai-select-content">
                  <SelectItem value="recursive_512" className="myai-overlay-item">recursive_512 (default)</SelectItem>
                  <SelectItem value="markdown_sections" className="myai-overlay-item">markdown_sections</SelectItem>
                  <SelectItem value="sentence_window" className="myai-overlay-item">sentence_window</SelectItem>
                  <SelectItem value="fixed_256" className="myai-overlay-item">fixed_256</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Embedding Profile</Label>
              <Select value={state.embedding_profile} onValueChange={(v) => update({ embedding_profile: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent className="myai-overlay-content myai-select-content">
                  <SelectItem value="default" className="myai-overlay-item">default (provider default)</SelectItem>
                  <SelectItem value="text-embedding-3-small" className="myai-overlay-item">text-embedding-3-small</SelectItem>
                  <SelectItem value="text-embedding-3-large" className="myai-overlay-item">text-embedding-3-large</SelectItem>
                  <SelectItem value="nomic-embed-text" className="myai-overlay-item">nomic-embed-text (local)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {state.ingest_status === "done" ? (
            <div className="flex gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
              <FileUp className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-green-900">Ingest complete</p>
                <p className="text-xs text-zinc-600 mt-0.5">{state.doc_files.length} file(s) ingested · profile: {state.chunking_profile}</p>
              </div>
            </div>
          ) : state.doc_files.length > 0 ? (
            <Button onClick={() => update({ ingest_status: "done" })}>Run Ingest</Button>
          ) : null}
        </>
      )}

      {!state.ingest_now && (
        <div className="flex flex-col items-center justify-center py-10 text-center text-zinc-400">
          <Layers className="h-8 w-8 mb-3" />
          <p className="text-sm">Document bootstrap disabled.</p>
          <p className="text-xs mt-1">You can ingest documents later from the Knowledge module.</p>
        </div>
      )}
    </div>
  );
}
