import { Checkbox, Label, cn } from "@kairosstack/ui";

import type { FrontendService, StepProps } from "../types";

const FRONTEND_OPTIONS: Array<{ id: FrontendService; label: string; description: string; port: string }> = [
  {
    id: "kros_core_frontend",
    label: "kros_core_frontend",
    description: "Core operator UI wired to kairos-core API",
    port: "8080",
  },
  {
    id: "kros_studio_frontend",
    label: "kros_studio_frontend",
    description: "Studio workflow UI wired to kairos-core API",
    port: "8081",
  },
  {
    id: "kros_council_frontend",
    label: "kros_council_frontend",
    description: "Council governance UI wired to kairos-core API",
    port: "8082",
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
          Selected services are added directly to generated compose with API wiring to `core_api`.
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
