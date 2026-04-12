import type { CoreApiClient } from "./client";

export type IngestJobCreatePayload = {
  session_id: string;
  source_files: Array<Record<string, string>>;
  chunking_profile: string;
  embedding_profile: string;
  namespace?: string;
};

export type IngestJob = {
  job_id?: string;
  status?: string;
  created_at?: string;
  [key: string]: unknown;
};

export const ingestApi = {
  createJob: (client: CoreApiClient, payload: IngestJobCreatePayload) =>
    client.post<IngestJob>("/v1/ingest/jobs", payload),

  getJob: (client: CoreApiClient, jobId: string) =>
    client.get<IngestJob>(`/v1/ingest/jobs/${jobId}`),
};
