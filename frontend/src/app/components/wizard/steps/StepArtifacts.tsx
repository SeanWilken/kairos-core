import { useState } from "react";
import { CheckCircle2, Download, Loader2, Terminal } from "lucide-react";
import { Button, cn } from "@kairosstack/ui";

import { buildArtifacts } from "../helpers";
import type { StepProps } from "../types";

export function StepArtifacts({ state, update }: StepProps) {
  const [activeTab, setActiveTab] = useState(0);
  const includesPopulatedEnv = state.artifacts.some((a) => a.name === ".env");
  const allViewIndex = state.artifacts.length;

  const allFilesView = state.artifacts
    .map((a) => `# ===== ${a.name} =====\n${a.content}`)
    .join("\n\n");

  const downloadCurrent = () => {
    const artifact = state.artifacts[activeTab];
    if (!artifact) return;
    const blob = new Blob([artifact.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const generate = () => {
    update({ gen_status: "generating" });
    setTimeout(() => update({ gen_status: "done", artifacts: buildArtifacts(state) }), 1400);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-zinc-700">Generate deployment artifacts from your configuration.</p>
          <p className="text-xs text-zinc-500 mt-1">Output: .env.template · scripts · docker-compose.yml · bootstrap-report.json (uses repo migrations/*.sql)</p>
        </div>
        <Button onClick={generate} disabled={state.gen_status === "generating" || state.gen_status === "done"}>
          {state.gen_status === "generating" ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating…</>
          ) : state.gen_status === "done" ? (
            <><CheckCircle2 className="h-4 w-4 mr-2" />Generated</>
          ) : (
            "Generate Artifacts"
          )}
        </Button>
      </div>

      {state.gen_status === "done" && state.artifacts.length > 0 && (
        <div className="space-y-4">
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-xs text-blue-900 leading-relaxed">
            <p className="font-semibold">Local bootstrap instructions</p>
            <p className="mt-1">Recommended: place generated files in the repository root (or an infra subfolder), rename <code className="font-mono bg-blue-100 px-1 rounded">.env.template</code> to <code className="font-mono bg-blue-100 px-1 rounded">.env</code>, then run <code className="font-mono bg-blue-100 px-1 rounded">bootstrap-local</code>. In local-source mode this builds Core from <code className="font-mono bg-blue-100 px-1 rounded">../backend/Dockerfile</code>; image modes use <code className="font-mono bg-blue-100 px-1 rounded">CORE_API_IMAGE</code>.</p>
            <p className="mt-2"><span className="font-medium">Privacy disclosure:</span> if you configure OpenAI or Anthropic, prompts and retrieved context sent to those providers are processed under their policies. Keep sensitive data local unless your policy allows external processing.</p>
          </div>

          {includesPopulatedEnv && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900 leading-relaxed">
              <p className="font-semibold">Secret handling notice</p>
              <p className="mt-1">You generated a populated <code className="font-mono bg-amber-100 px-1 rounded">.env</code> file containing local values. Do not commit this file or share it outside your trusted local environment.</p>
            </div>
          )}

          <div className="border border-zinc-200 rounded-lg overflow-hidden bg-white">
            <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 px-2 pt-1">
              <div className="flex">
            {state.artifacts.map((a, i) => (
              <button
                key={`${a.name}-${i}`}
                onClick={() => setActiveTab(i)}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-t transition-colors font-mono",
                  activeTab === i ? "bg-white border border-b-white border-zinc-200 text-zinc-900" : "text-zinc-500 hover:text-zinc-700"
                )}
              >
                {a.name}
              </button>
            ))}
            <button
              onClick={() => setActiveTab(allViewIndex)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-t transition-colors font-mono",
                activeTab === allViewIndex ? "bg-white border border-b-white border-zinc-200 text-zinc-900" : "text-zinc-500 hover:text-zinc-700"
              )}
            >
              all
            </button>
              </div>
              <div className="mb-1 mr-1 flex items-center gap-1">
                {activeTab < allViewIndex ? (
                  <Button variant="outline" size="sm" className="h-7 text-xs" onClick={downloadCurrent}>
                    <Download className="h-3.5 w-3.5 mr-1" /> Download
                  </Button>
                ) : null}
              </div>
            </div>
            <div className="relative">
              <pre className="p-4 text-xs font-mono text-zinc-700 leading-relaxed overflow-auto max-h-72 bg-white whitespace-pre-wrap break-words">
                {activeTab < allViewIndex ? state.artifacts[activeTab]?.content : allFilesView}
              </pre>
            </div>
          </div>
        </div>
      )}

      {state.gen_status === "idle" && (
        <div className="flex flex-col items-center justify-center py-10 text-center text-zinc-400">
          <Terminal className="h-8 w-8 mb-3" />
          <p className="text-sm">Click Generate Artifacts to produce output files.</p>
        </div>
      )}
    </div>
  );
}
