import { useState } from "react";
import { CheckCircle2, Loader2, Terminal } from "lucide-react";
import { Button, cn } from "@kairosstack/ui";

import { buildArtifacts } from "../helpers";
import type { StepProps } from "../types";

export function StepArtifacts({ state, update }: StepProps) {
  const [activeTab, setActiveTab] = useState(0);

  const generate = () => {
    update({ gen_status: "generating" });
    setTimeout(() => update({ gen_status: "done", artifacts: buildArtifacts(state) }), 1400);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-zinc-700">Generate deployment artifacts from your configuration.</p>
          <p className="text-xs text-zinc-500 mt-1">Output: .env.template · docker-compose.yml · bootstrap-report.json</p>
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
        <div className="border border-zinc-200 rounded-lg overflow-hidden bg-white">
          <div className="flex border-b border-zinc-200 bg-zinc-50 px-1 pt-1">
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
          </div>
          <div className="relative">
            <pre className="p-4 text-xs font-mono text-zinc-700 leading-relaxed overflow-auto max-h-72 bg-white whitespace-pre-wrap break-words">
              {state.artifacts[activeTab]?.content}
            </pre>
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
