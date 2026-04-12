import type { CoreApiClient } from "./client";

export const healthApi = {
  getHealth: (client: CoreApiClient) => client.get<Record<string, unknown>>("/v1/health"),
  getProtectedPing: (client: CoreApiClient) => client.get<Record<string, unknown>>("/v1/protected/ping"),
};
