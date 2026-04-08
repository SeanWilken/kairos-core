import { useState } from "react";
import { CheckCircle2, ChevronRight, Circle } from "lucide-react";
import { Button, Input, Progress, cn } from "@kairosstack/ui";

import { STEP_DEFS } from "./constants";

export function StepSidebar({ current, completed }: { current: number; completed: Set<number> }) {
  return (
    <div className="w-56 lg:w-60 flex-shrink-0 border-r border-zinc-200 bg-white overflow-y-auto">
      <div className="p-5 border-b border-zinc-200">
        <h2 className="text-sm font-semibold text-zinc-900">Environment Setup</h2>
        <p className="text-xs text-zinc-500 mt-0.5">Configure your core runtime</p>
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-zinc-600 mb-1.5">
            <span>{completed.size} of {STEP_DEFS.length} complete</span>
            <span>{Math.round((completed.size / STEP_DEFS.length) * 100)}%</span>
          </div>
          <Progress value={(completed.size / STEP_DEFS.length) * 100} className="h-1.5" />
        </div>
      </div>
      <nav className="p-3 space-y-0.5">
        {STEP_DEFS.map((step) => {
          const done = completed.has(step.id);
          const active = current === step.id;
          const Icon = step.icon;
          return (
            <div
              key={step.id}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors",
                active ? "bg-zinc-900 text-white" : done ? "text-zinc-700 hover:bg-zinc-50" : "text-zinc-400"
              )}
            >
              <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                {done && !active ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : active ? (
                  <Icon className="h-4 w-4" />
                ) : (
                  <Circle className="h-4 w-4" />
                )}
              </div>
              <div className="min-w-0">
                <div className={cn("text-sm font-medium leading-none", active ? "text-white" : done ? "text-zinc-800" : "text-zinc-400")}>
                  {step.label}
                </div>
                <div className={cn("text-xs mt-0.5", active ? "text-zinc-300" : "text-zinc-400")}>
                  {step.description}
                </div>
              </div>
              {active && <ChevronRight className="h-3.5 w-3.5 ml-auto flex-shrink-0 text-zinc-300" />}
            </div>
          );
        })}
      </nav>
    </div>
  );
}

export function TagInput({ values, onChange, placeholder }: { values: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [v, setV] = useState("");
  const add = () => {
    const t = v.trim();
    if (t && !values.includes(t)) {
      onChange([...values, t]);
      setV("");
    }
  };
  return (
    <div className="space-y-2">
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((x) => (
            <span key={x} className="inline-flex items-center gap-1 px-2 py-0.5 bg-zinc-100 border border-zinc-200 rounded text-xs text-zinc-700">
              {x}
              <button onClick={() => onChange(values.filter((i) => i !== x))} className="text-zinc-400 hover:text-zinc-700 transition-colors ml-0.5">×</button>
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <Input
          value={v}
          onChange={(e) => setV(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder ?? "Type and press Enter"}
          className="text-sm"
        />
        <Button variant="outline" size="sm" onClick={add} className="flex-shrink-0">Add</Button>
      </div>
    </div>
  );
}
