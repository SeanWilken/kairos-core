import { useCallback, useMemo, useState, type MouseEvent, type ReactNode } from "react";
import { ArrowRight, CheckCheck } from "lucide-react";
import { Badge, Button } from "@kairosstack/ui";

import { INITIAL_STATE, STEP_DEFS, STEP_HEADER } from "./constants";
import { StepSidebar } from "./common";
import { buildPreflightChecks } from "./helpers";
import type { WizardState } from "./types";
import { StepRuntime } from "./steps/StepRuntime";
import { StepDeployment } from "./steps/StepDeployment";
import { StepSecrets } from "./steps/StepSecrets";
import { StepVector } from "./steps/StepVector";
import { StepConnectivity } from "./steps/StepConnectivity";
import { StepArtifacts } from "./steps/StepArtifacts";
import { StepReview } from "./steps/StepReview";
import { StepRuntimeVerifyDocs } from "./steps/StepRuntimeVerifyDocs";

export function SetupWizard() {
  const [step, setStep] = useState(1);
  const [completed, setCompleted] = useState<Set<number>>(new Set());
  const [state, setState] = useState<WizardState>(INITIAL_STATE);
  const [spotlight, setSpotlight] = useState({ x: 50, y: 50 });

  const update = useCallback((partial: Partial<WizardState>) => {
    setState((p) => ({ ...p, ...partial }));
  }, []);

  const runChecks = () => {
    const checks = buildPreflightChecks(state);
    update({ check_status: "done", check_results: checks });
  };

  const canContinue = useMemo(() => {
    if (step === 1) return state.tenant_name.trim() && state.model_modes.length > 0 && state.connections.every((c) => c.model_ref.trim());
    if (step === 5) return state.check_status === "done" && state.check_results.filter((r) => r.required).every((r) => r.status === "pass");
    if (step === 6) return state.gen_status === "done";
    if (step === 7) {
      const runtimeReady = state.runtime_check_results.length > 0 && state.runtime_check_results.filter((r) => r.required).every((r) => r.status === "pass");
      return runtimeReady && (!state.ingest_now || state.ingest_status === "done");
    }
    if (step === 8) return state.confirmed;
    return true;
  }, [step, state]);

  const goNext = () => {
    setCompleted((p) => new Set([...p, step]));
    if (step < 8) setStep((s) => s + 1);
  };

  const goPrev = () => {
    if (step > 1) setStep((s) => s - 1);
  };

  const stepForms: Record<number, ReactNode> = {
    1: <StepRuntime state={state} update={update} />,
    2: <StepDeployment state={state} update={update} />,
    3: <StepSecrets state={state} update={update} />,
    4: <StepVector state={state} update={update} />,
    5: <StepConnectivity state={state} runChecks={runChecks} />,
    6: <StepArtifacts state={state} update={update} />,
    7: <StepRuntimeVerifyDocs state={state} update={update} />,
    8: <StepReview state={state} update={update} />,
  };

  const stepDetail = useMemo(() => {
    if (step === 1) return `Tenant: ${state.tenant_name || "(unnamed)"} · Modes: ${state.model_modes.join(", ")}`;
    if (step === 2) return `Target: ${state.deployment_target} · Mode: ${state.execution_mode}`;
    if (step === 3) return `Secrets: ${state.secrets_mode} · Keys: ${state.required_keys.length}`;
    if (step === 4) return `Vector: ${state.vector_store_mode}${state.vector_store_mode === "enabled" ? ` (${state.vector_provider})` : ""}`;
    if (step === 5) return `Preflight: ${state.check_status} · Passed: ${state.check_results.filter((r) => r.status === "pass").length}`;
    if (step === 6) return `Artifacts: ${state.gen_status} · Files: ${state.artifacts.length}`;
    if (step === 7) return `Runtime checks: ${state.runtime_check_results.length} · Ingest: ${state.ingest_now ? state.ingest_status : "disabled"}`;
    return `Review readiness: ${state.confirmed ? "confirmed" : "pending"}`;
  }, [step, state]);

  const onSpotlightMove = (event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    setSpotlight({ x, y });
  };

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      <StepSidebar current={step} completed={completed} />

      <div className="flex-1 overflow-y-auto bg-zinc-50">
        <div className="w-full px-4 py-6 lg:px-8 xl:px-10">
          <div className="mb-6">
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-1">Step {step} of {STEP_DEFS.length}</p>
            <h1 className="text-2xl font-bold text-zinc-900">{STEP_HEADER[step].title}</h1>
            <p className="text-sm text-zinc-600 mt-1">{STEP_HEADER[step].description}</p>
          </div>

          <div
            className="relative mb-6 overflow-hidden rounded-xl border border-zinc-200 bg-white/90"
            onMouseMove={onSpotlightMove}
          >
            <div
              className="pointer-events-none absolute -top-20 -left-20 h-64 w-64 rounded-full bg-blue-200/40 blur-3xl transition-transform duration-200"
              style={{ transform: `translate(${(spotlight.x - 50) * 0.18}px, ${(spotlight.y - 50) * 0.16}px)` }}
            />
            <div
              className="pointer-events-none absolute -bottom-20 -right-16 h-64 w-64 rounded-full bg-violet-200/35 blur-3xl transition-transform duration-200"
              style={{ transform: `translate(${(50 - spotlight.x) * 0.14}px, ${(50 - spotlight.y) * 0.12}px)` }}
            />
            <div className="relative grid gap-4 p-5 md:grid-cols-[2fr_1fr] md:items-center md:gap-6 md:p-6">
              <div>
                <h2 className="text-lg font-semibold text-zinc-900">Core Bootstrap Configuration</h2>
                <p className="mt-1 text-sm text-zinc-600">
                  Build the deployment plan first, then verify runtime, then unlock document ingestion. This prevents fake readiness and keeps setup deterministic.
                </p>
              </div>
              <div className="rounded-lg border border-zinc-200/80 bg-white/80 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Current Context</p>
                <p className="mt-1 text-xs text-zinc-700">{stepDetail}</p>
              </div>
            </div>
          </div>

          <div className="border border-zinc-200 rounded-lg bg-white p-6 mb-6">{stepForms[step]}</div>

          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={goPrev} disabled={step === 1}>← Back</Button>

            <div className="flex items-center gap-3">
              {!canContinue && step < 8 && <Badge variant="secondary">Complete required fields</Badge>}

              {step < 8 ? (
                <Button onClick={goNext} disabled={!canContinue}>
                  Continue <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              ) : (
                <Button onClick={() => {}} disabled={!state.confirmed} className="bg-green-600 hover:bg-green-700 text-white">
                  <CheckCheck className="h-4 w-4 mr-1.5" /> Complete Setup
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
