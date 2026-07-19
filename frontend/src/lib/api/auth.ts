import type { CoreApiClient } from "./client";

export type RegisterPayload = {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  tenant_id?: string | null;
  org_id?: string | null;
  is_global_admin?: boolean;
  role?: string;
};

export type LoginPayload = {
  email: string;
  password: string;
  tenant_id?: string | null;
  org_id?: string | null;
};

export type RefreshPayload = {
  refresh_token: string;
};

export type AuthTokenSet = {
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  [key: string]: unknown;
};

export type AuthStatus = {
  tenant_configured: boolean;
  tenant_id?: string | null;
  admin_configured: boolean;
  login_required: boolean;
};

export const authApi = {
  status: (client: CoreApiClient) => client.get<AuthStatus>("/v1/auth/status"),

  register: (client: CoreApiClient, payload: RegisterPayload) =>
    client.post<AuthTokenSet | Record<string, unknown>>("/v1/auth/register", payload),

  login: (client: CoreApiClient, payload: LoginPayload) =>
    client.post<AuthTokenSet | Record<string, unknown>>("/v1/auth/login", payload),

  refresh: (client: CoreApiClient, payload: RefreshPayload) =>
    client.post<AuthTokenSet | Record<string, unknown>>("/v1/auth/refresh", payload),

  logout: (client: CoreApiClient, payload: RefreshPayload) =>
    client.post<Record<string, unknown>>("/v1/auth/logout", payload),

  me: (client: CoreApiClient) => client.get<Record<string, unknown>>("/v1/auth/me"),
};
