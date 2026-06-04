import { Checkbox, Label, cn } from "@myai-tech/myui";

import type { FrontendService, StepProps } from "../types";

const FRONTEND_OPTIONS: Array<{ id: FrontendService; label: string; description: string; port: string }> = [
  {
    id: "myai_core_frontend",
    label: "myai_core_frontend",
    description: "Core operator UI wired to myai-core API",
    port: "8080",
  },
  {
    id: "myai_studio_frontend",
    label: "myai_studio_frontend",
    description: "Studio workflow UI wired to myai-core API",
    port: "8081",
  },
  {
    id: "myai_council_frontend",
    label: "myai_council_frontend",
    description: "Council governance UI wired to myai-core API",
    port: "8082",
  },
  {
    id: "myai_de_frontend",
    label: "myai_de_frontend",
    description: "myAIDE frontend wired to myai-core API",
    port: "8083",
  },
  {
    id: "myai_knowledger_frontend",
    label: "myai_knowledger_frontend",
    description: "Knowledger frontend wired to myai-core API",
    port: "8084",
  },
];

export function StepFrontends({ state, update }: StepProps) {
  const toggleService = (id: FrontendService) => {
    const next = state.frontend_services.includes(id)
      ? state.frontend_services.filter((serviceId) => serviceId !== id)
      : [...state.frontend_services, id];
    update({ frontend_services: next });
  };

  return (
    <div className="space-y-4">
      <div>
        <Label>Install Frontend Services (multiple select)</Label>
        <p className="mt-1 text-xs text-zinc-500">
          Selected services are added directly to generated compose. You can run all services in one stack, or split by selecting only the services you want now.
        </p>
        <p className="mt-1 text-xs text-zinc-500">
          `myai_de_frontend` targets `myai_de_api` when that server is selected in Deployment; otherwise it falls back to `core_api`.
        </p>
      </div>

      <div className="space-y-2">
        {FRONTEND_OPTIONS.map((option) => (
          <div
            key={option.id}
            className={cn(
              "flex items-center gap-3 rounded-lg border p-3",
              state.frontend_services.includes(option.id)
                ? "border-zinc-300 bg-zinc-50"
                : "border-zinc-200 bg-white hover:border-zinc-300"
            )}
            onClick={() => toggleService(option.id)}
          >
            <Checkbox
              checked={state.frontend_services.includes(option.id)}
              onClick={(event) => event.stopPropagation()}
              onCheckedChange={() => toggleService(option.id)}
            />
            <div className="flex-1">
              <p className="font-mono text-sm font-medium text-zinc-900">{option.label}</p>
              <p className="mt-0.5 text-xs text-zinc-500">{option.description}</p>
            </div>
            <span className="rounded bg-zinc-100 px-2 py-0.5 text-[11px] text-zinc-600">:{option.port}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
