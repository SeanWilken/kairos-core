import type { CoreApiClient } from "./client";

export type RuntimeCheckStatus = "pass" | "warn" | "fail" | "pending";

export type RuntimeCheck = {
  check_id?: string;
  label?: string;
  required?: boolean;
  status?: RuntimeCheckStatus;
  message?: string;
};

export type RuntimeStatus = {
  checks?: RuntimeCheck[];
  summary?: {
    required_passed?: number;
    required_failed?: number;
    required_pending?: number;
  };
  [key: string]: unknown;
};

export type RuntimeChecksRunPayload = {
  session_id: string;
  check_ids?: string[];
};

export const systemApi = {
  getStatus: (client: CoreApiClient, sessionId: string) =>
    client.get<RuntimeStatus>("/v1/system/status", { session_id: sessionId }),

  runChecks: (client: CoreApiClient, payload: RuntimeChecksRunPayload) =>
    client.post<RuntimeStatus>("/v1/system/checks/run", payload),
};
