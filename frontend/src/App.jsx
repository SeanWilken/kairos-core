import { useEffect, useState } from "react";
import { RouterProvider } from "react-router-dom";

import { router } from "./routes";
import { authApi } from "./lib/api/auth";
import {
  clearCoreTokens,
  createCoreApiClient,
  getDefaultTenantId,
  getStoredAccessToken,
  storeCoreTokens,
} from "./lib/api/client";

function AuthScreen({ mode, tenantId, onAuthenticated }) {
  const [form, setForm] = useState({ email: "", password: "", firstName: "", lastName: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const client = createCoreApiClient({ scope: { tenantId } });
      const response = mode === "register"
        ? await authApi.register(client, {
            tenant_id: tenantId,
            email: form.email,
            password: form.password,
            first_name: form.firstName,
            last_name: form.lastName,
            is_global_admin: true,
            role: "global_admin",
          })
        : await authApi.login(client, { tenant_id: tenantId, email: form.email, password: form.password });
      if (!response?.user?.is_global_admin) {
        throw new Error("A Core administrator account is required.");
      }
      storeCoreTokens(response);
      onAuthenticated();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Authentication failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-16 text-zinc-100">
      <div className="mx-auto grid max-w-5xl gap-12 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
        <section>
          <img src="/myAI.svg" alt="MyAI" className="mb-8 h-14 w-14 rounded-xl bg-white p-2" />
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-blue-400">MyAI control plane</p>
          <h1 className="max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">
            {mode === "register" ? "Create the first Core administrator." : "Core is locked."}
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-zinc-400">
            {mode === "register"
              ? "This account controls setup, policy, knowledge, and suite administration. After it is created, Core requires authentication."
              : "Sign in with an administrator account to access setup, recovery, backups, and runtime controls."}
          </p>
        </section>
        <form onSubmit={submit} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-7 shadow-2xl">
          <h2 className="text-xl font-semibold">{mode === "register" ? "Administrator setup" : "Administrator login"}</h2>
          <p className="mt-1 text-sm text-zinc-400">Tenant: <code>{tenantId}</code></p>
          {mode === "register" && (
            <div className="mt-6 grid grid-cols-2 gap-3">
              <input required placeholder="First name" value={form.firstName} onChange={(event) => setForm({ ...form, firstName: event.target.value })} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm outline-none focus:border-blue-500" />
              <input required placeholder="Last name" value={form.lastName} onChange={(event) => setForm({ ...form, lastName: event.target.value })} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm outline-none focus:border-blue-500" />
            </div>
          )}
          <input required type="email" placeholder="Email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} className="mt-3 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm outline-none focus:border-blue-500" />
          <input required minLength={8} type="password" placeholder="Password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} className="mt-3 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm outline-none focus:border-blue-500" />
          {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
          <button disabled={submitting} className="mt-5 w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-60">
            {submitting ? "Please wait..." : mode === "register" ? "Create administrator" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}

export default function App() {
  const [state, setState] = useState({ loading: true, unavailable: false, tenantConfigured: false, adminConfigured: false, authenticated: false, tenantId: getDefaultTenantId() });

  const loadState = async () => {
    try {
      const client = createCoreApiClient({ scope: { tenantId: getDefaultTenantId() } });
      const status = await authApi.status(client);
      let authenticated = false;
      if (status.admin_configured && getStoredAccessToken()) {
        try {
          const identity = await authApi.me(client);
          authenticated = Boolean(identity?.auth?.is_global_admin);
          if (!authenticated) clearCoreTokens();
        } catch {
          clearCoreTokens();
        }
      }
      setState({ loading: false, unavailable: false, tenantConfigured: status.tenant_configured, adminConfigured: status.admin_configured, authenticated, tenantId: status.tenant_id || getDefaultTenantId() });
    } catch {
      setState((current) => ({ ...current, loading: false, unavailable: true }));
    }
  };

  useEffect(() => { void loadState(); }, []);

  if (state.loading) return <div className="grid min-h-screen place-items-center bg-zinc-950 text-sm text-zinc-400">Checking Core access...</div>;
  if (state.unavailable) return <div className="grid min-h-screen place-items-center bg-zinc-950 px-6 text-center text-sm text-zinc-400">Core access state could not be verified. Access remains locked until the API is available.</div>;
  if (!state.tenantConfigured) return <RouterProvider router={router} />;
  if (!state.adminConfigured) return <AuthScreen mode="register" tenantId={state.tenantId} onAuthenticated={loadState} />;
  if (!state.authenticated) return <AuthScreen mode="login" tenantId={state.tenantId} onAuthenticated={loadState} />;
  return <RouterProvider router={router} />;
}
