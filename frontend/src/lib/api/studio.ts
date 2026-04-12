import type { CoreApiClient } from "./client";

export type StudioOrganization = {
  id: string;
  tenant_id?: string;
  name: string;
  slug: string;
  mode?: string;
  owner_user_id?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type StudioUser = {
  id: string;
  tenant_id?: string;
  org_id?: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  status?: string;
  is_global_admin?: boolean;
  role?: string;
  created_at?: string;
  updated_at?: string;
};

export type StudioMembership = {
  id: string;
  org_id: string;
  user_id: string;
  role: string;
  status: string;
  created_at?: string;
  updated_at?: string;
};

export type StudioOrganizationCreatePayload = {
  name: string;
  slug: string;
  mode?: string;
  owner_user_id?: string | null;
};

export type StudioUserCreatePayload = {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  status?: string;
  is_global_admin?: boolean;
  org_id?: string | null;
  role?: string;
};

export type StudioMembershipCreatePayload = {
  org_id: string;
  user_id: string;
  role?: string;
  status?: string;
};

export type StudioMembershipPatchPayload = {
  role?: string;
  status?: string;
};

export const studioApi = {
  listOrganizations: (client: CoreApiClient) =>
    client.get<{ items: StudioOrganization[] }>("/v1/studio/organizations"),

  createOrganization: (client: CoreApiClient, payload: StudioOrganizationCreatePayload) =>
    client.post<StudioOrganization>("/v1/studio/organizations", payload),

  getOrganization: (client: CoreApiClient, orgId: string) =>
    client.get<StudioOrganization>(`/v1/studio/organizations/${orgId}`),

  listUsers: (client: CoreApiClient, options?: { orgId?: string }) =>
    client.get<{ items: StudioUser[] }>("/v1/studio/users", {
      org_id: options?.orgId,
    }),

  createUser: (client: CoreApiClient, payload: StudioUserCreatePayload) =>
    client.post<StudioUser>("/v1/studio/users", payload),

  getUser: (client: CoreApiClient, userId: string) =>
    client.get<StudioUser>(`/v1/studio/users/${userId}`),

  createMembership: (client: CoreApiClient, payload: StudioMembershipCreatePayload) =>
    client.post<StudioMembership>("/v1/studio/memberships", payload),

  patchMembership: (client: CoreApiClient, membershipId: string, payload: StudioMembershipPatchPayload) =>
    client.patch<StudioMembership>(`/v1/studio/memberships/${membershipId}`, payload),
};
