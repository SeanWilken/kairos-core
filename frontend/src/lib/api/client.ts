export type ApiScope = {
  tenantId?: string;
  orgId?: string;
};

type QueryValue = string | number | boolean | null | undefined;

type EnvelopeError = {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
};

type Envelope<T> = {
  meta?: {
    request_id?: string;
    trace_id?: string;
    [key: string]: unknown;
  };
  data?: T | null;
  error?: EnvelopeError | null;
};

export class CoreApiError extends Error {
  status: number;
  code?: string;
  details?: Record<string, unknown>;
  requestId?: string;
  traceId?: string;

  constructor(message: string, options: {
    status: number;
    code?: string;
    details?: Record<string, unknown>;
    requestId?: string;
    traceId?: string;
  }) {
    super(message);
    this.name = "CoreApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
    this.requestId = options.requestId;
    this.traceId = options.traceId;
  }
}

export type CoreApiClient = ReturnType<typeof createCoreApiClient>;

export function getDefaultCoreApiBaseUrl(): string {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env ?? {};
  return env.VITE_KAIROS_CORE_API_BASE_URL ?? "http://localhost:8000";
}

export function createCoreApiClient(config?: {
  baseUrl?: string;
  scope?: ApiScope;
  accessToken?: string;
  defaultHeaders?: Record<string, string>;
}) {
  const baseUrl = (config?.baseUrl ?? getDefaultCoreApiBaseUrl()).replace(/\/$/, "");
  const scope = config?.scope ?? {};
  const accessToken = config?.accessToken;
  const defaultHeaders = config?.defaultHeaders ?? {};

  const buildUrl = (path: string, query?: Record<string, QueryValue>) => {
    const url = new URL(path, `${baseUrl}/`);
    if (query) {
      Object.entries(query).forEach(([key, value]) => {
        if (value === undefined || value === null) return;
        url.searchParams.set(key, String(value));
      });
    }
    return url.toString();
  };

  const request = async <T>(
    path: string,
    options?: {
      method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
      query?: Record<string, QueryValue>;
      body?: unknown;
      headers?: Record<string, string>;
      signal?: AbortSignal;
    },
  ): Promise<T> => {
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...defaultHeaders,
      ...options?.headers,
    };

    if (scope.tenantId) headers["X-Tenant-ID"] = scope.tenantId;
    if (scope.orgId) headers["X-Org-ID"] = scope.orgId;
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

    const hasBody = options?.body !== undefined;
    if (hasBody) headers["Content-Type"] = "application/json";

    const response = await fetch(buildUrl(path, options?.query), {
      method: options?.method ?? "GET",
      headers,
      body: hasBody ? JSON.stringify(options?.body) : undefined,
      signal: options?.signal,
    });

    let rawBody: unknown = null;
    try {
      rawBody = await response.json();
    } catch {
      rawBody = null;
    }

    const envelope = rawBody && typeof rawBody === "object" ? (rawBody as Envelope<T>) : null;
    const message = envelope?.error?.message ?? (response.ok ? "Unexpected response." : "Request failed.");

    if (!response.ok) {
      throw new CoreApiError(message, {
        status: response.status,
        code: envelope?.error?.code,
        details: envelope?.error?.details,
        requestId: envelope?.meta?.request_id,
        traceId: envelope?.meta?.trace_id,
      });
    }

    if (envelope && "data" in envelope) {
      return envelope.data as T;
    }

    return rawBody as T;
  };

  return {
    baseUrl,
    scope,
    request,
    get: <T>(path: string, query?: Record<string, QueryValue>) =>
      request<T>(path, { method: "GET", query }),
    post: <T>(path: string, body?: unknown) =>
      request<T>(path, { method: "POST", body }),
    patch: <T>(path: string, body?: unknown) =>
      request<T>(path, { method: "PATCH", body }),
    put: <T>(path: string, body?: unknown) =>
      request<T>(path, { method: "PUT", body }),
    delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
    withScope: (nextScope: ApiScope) =>
      createCoreApiClient({
        baseUrl,
        accessToken,
        defaultHeaders,
        scope: {
          tenantId: nextScope.tenantId ?? scope.tenantId,
          orgId: nextScope.orgId ?? scope.orgId,
        },
      }),
  };
}
