import { useCallback, useMemo, useState, type MouseEvent, type ReactNode } from "react";
import { ArrowRight, CheckCheck } from "lucide-react";
import { Badge, Button } from "@myai-tech/myui";

import { INITIAL_STATE, RUNTIME_WIZARD_STEP_IDS, STEP_DEFS, STEP_HEADER } from "./constants";
import { StepSidebar } from "./common";
import { buildPreflightChecks, buildRuntimeChecks } from "./helpers";
import type { WizardState } from "./types";
import { StepRuntime } from "./steps/StepRuntime";
import { StepDeployment } from "./steps/StepDeployment";
import { StepFrontends } from "./steps/StepFrontends";
import { StepSecrets } from "./steps/StepSecrets";
import { StepVector } from "./steps/StepVector";
import { StepConnectivity } from "./steps/StepConnectivity";
import { StepArtifacts } from "./steps/StepArtifacts";
import { StepReview } from "./steps/StepReview";
import { StepRuntimeVerifyDocs } from "./steps/StepRuntimeVerifyDocs";

export function SetupWizard() {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<"bootstrap" | "runtime">("bootstrap");
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
    if (step === 2) {
      if (state.core_api_runtime_mode === "custom_image") return state.core_api_custom_image.trim().length > 0;
      return true;
    }
    if (step === 6) return state.check_status === "done" && state.check_results.filter((r) => r.required).every((r) => r.status === "pass");
    if (step === 7) return state.gen_status === "done";
    if (step === 8) {
      const runtimeReady = state.runtime_check_results.length > 0 && state.runtime_check_results.filter((r) => r.required).every((r) => r.status === "pass");
      return runtimeReady && (!state.ingest_now || state.ingest_status === "done");
    }
    if (step === 9) return state.confirmed;
    return true;
  }, [step, state]);

  const activeStepIds = useMemo(
    () => (mode === "bootstrap" ? STEP_DEFS.map((s) => s.id) : [...RUNTIME_WIZARD_STEP_IDS]),
    [mode]
  );

  const activeSteps = useMemo(() => STEP_DEFS.filter((s) => activeStepIds.includes(s.id)), [activeStepIds]);

  const currentStepIndex = useMemo(() => activeStepIds.indexOf(step), [activeStepIds, step]);

  const setFlowMode = (nextMode: "bootstrap" | "runtime") => {
    setMode(nextMode);
    const nextIds = nextMode === "bootstrap" ? STEP_DEFS.map((s) => s.id) : [...RUNTIME_WIZARD_STEP_IDS];
    setStep((prev) => (nextIds.includes(prev) ? prev : nextIds[0]));
  };

  const goNext = () => {
    setCompleted((p) => new Set([...p, step]));
    if (currentStepIndex >= 0 && currentStepIndex < activeStepIds.length - 1) {
      setStep(activeStepIds[currentStepIndex + 1]);
    }
  };

  const goPrev = () => {
    if (currentStepIndex > 0) setStep(activeStepIds[currentStepIndex - 1]);
  };

  const stepForms: Record<number, ReactNode> = {
    1: <StepRuntime state={state} update={update} />,
    2: <StepDeployment state={state} update={update} />,
    3: <StepFrontends state={state} update={update} />,
    4: <StepSecrets state={state} update={update} />,
    5: <StepVector state={state} update={update} />,
    6: <StepConnectivity state={state} runChecks={runChecks} />,
    7: <StepArtifacts state={state} update={update} />,
    8: <StepRuntimeVerifyDocs state={state} update={update} />,
    9: <StepReview state={state} update={update} />,
  };

  const stepDetail = useMemo(() => {
    if (step === 1) return `Tenant: ${state.tenant_name || "(unnamed)"} · Modes: ${state.model_modes.join(", ")}`;
    if (step === 2) return `Target: ${state.deployment_target} · Engine: ${state.container_engine} · Core: ${state.core_api_runtime_mode} · Mode: ${state.execution_mode}`;
    if (step === 3) return `Frontends: ${state.frontend_services.length === 0 ? "none" : state.frontend_services.join(", ")}`;
    if (step === 4) return `Secrets: ${state.secrets_mode} · Keys: ${state.required_keys.length}`;
    if (step === 5) return `Vector: ${state.vector_store_mode}${state.vector_store_mode === "enabled" ? ` (${state.vector_provider})` : ""}`;
    if (step === 6) return `Preflight: ${state.check_status} · Passed: ${state.check_results.filter((r) => r.status === "pass").length}`;
    if (step === 7) return `Artifacts: ${state.gen_status} · Files: ${state.artifacts.length}`;
    if (step === 8) {
      const expectedRequired = buildRuntimeChecks(state).filter((check) => check.required).length;
      const completedRequired = state.runtime_check_results.filter((check) => check.required).length;
      return `Runtime checks: ${completedRequired}/${expectedRequired} required · Ingest: ${state.ingest_now ? state.ingest_status : "disabled"}`;
    }
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
      <StepSidebar current={step} completed={completed} steps={activeSteps} mode={mode} onModeChange={setFlowMode} />

      <div className="flex-1 overflow-y-auto bg-zinc-50">
        <div className="w-full px-4 py-6 lg:px-8 xl:px-10">
          <div className="mb-6">
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-1">Step {Math.max(1, currentStepIndex + 1)} of {activeStepIds.length}</p>
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
            <Button variant="outline" onClick={goPrev} disabled={currentStepIndex <= 0}>← Back</Button>

            <div className="flex items-center gap-3">
              {!canContinue && step !== activeStepIds[activeStepIds.length - 1] && <Badge variant="secondary">Complete required fields</Badge>}

              {step !== activeStepIds[activeStepIds.length - 1] ? (
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
