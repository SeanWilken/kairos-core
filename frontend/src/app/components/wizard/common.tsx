import { useState } from "react";
import { CheckCircle2, ChevronRight, Circle } from "lucide-react";
import { Button, Input, Progress, cn } from "@kairosstack/ui";

type SidebarStep = {
  id: number;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
};

export function StepSidebar({
  current,
  completed,
  steps,
  mode,
  onModeChange,
}: {
  current: number;
  completed: Set<number>;
  steps: SidebarStep[];
  mode: "bootstrap" | "runtime";
  onModeChange: (mode: "bootstrap" | "runtime") => void;
}) {
  const completedCount = steps.filter((s) => completed.has(s.id)).length;
  const progress = steps.length > 0 ? (completedCount / steps.length) * 100 : 0;

  return (
    <div className="w-56 lg:w-60 flex-shrink-0 border-r border-zinc-200 bg-white overflow-y-auto">
      <div className="p-5 border-b border-zinc-200">
        <h2 className="text-sm font-semibold text-zinc-900">{mode === "bootstrap" ? "Environment Setup" : "Runtime Wizard"}</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          {mode === "bootstrap" ? "Configure and bootstrap your core runtime" : "Validate and use an existing runtime"}
        </p>

        <div className="mt-3 grid grid-cols-2 gap-1 rounded-md border border-zinc-200 p-1 bg-zinc-50">
          <button
            type="button"
            onClick={() => onModeChange("bootstrap")}
            className={cn(
              "text-[11px] font-semibold rounded px-2 py-1 transition-colors",
              mode === "bootstrap" ? "bg-white text-zinc-900 border border-zinc-200" : "text-zinc-500 hover:text-zinc-700"
            )}
          >
            setup
          </button>
          <button
            type="button"
            onClick={() => onModeChange("runtime")}
            className={cn(
              "text-[11px] font-semibold rounded px-2 py-1 transition-colors",
              mode === "runtime" ? "bg-white text-zinc-900 border border-zinc-200" : "text-zinc-500 hover:text-zinc-700"
            )}
          >
            runtime
          </button>
        </div>

        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-zinc-600 mb-1.5">
            <span>{completedCount} of {steps.length} complete</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-1.5" />
        </div>
      </div>
      <nav className="p-3 space-y-0.5">
        {steps.map((step) => {
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
              <button onClick={() => onChange(values.filter((i) => i !== x))} className="text-zinc-400 hover:text-zinc-700 transition-colors ml-0.5">x</button>
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
