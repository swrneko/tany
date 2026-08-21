export type AuthMode = "builtin" | "proxy" | "disabled";

export interface SetupStatus {
  needs_setup: boolean;
  auth_mode: AuthMode;
}

export interface User {
  id: string;
  username: string;
  is_admin: boolean;
}

export type JobStatus = "queued" | "running" | "cancelling" | "cancelled" | "done" | "failed";

export const TERMINAL_STATUSES: readonly JobStatus[] = ["done", "failed", "cancelled"];

export interface Job {
  id: string;
  title: string;
  source_type: string;
  status: JobStatus;
  progress: number;
  language: string | null;
  duration_sec: number | null;
  error_code: string | null;
  error_params: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
}

export interface TranscriptSegment {
  idx: number;
  start: number;
  end: number;
  text: string;
  speaker: string | null;
}

export interface Transcript {
  job_id: string;
  language: string | null;
  text: string;
  segments: TranscriptSegment[];
}

export interface Preset {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  user_template: string;
  model_override: string | null;
  provider_id: string | null;
  temperature: number | null;
  output_format: string;
  is_builtin: boolean;
  /** Set on builtins. The UI translates this; `name` is the English fallback. */
  builtin_key: string | null;
}

export type PresetDraft = Omit<Preset, "id" | "is_builtin" | "builtin_key">;

export interface Summary {
  id: string;
  job_id: string;
  preset_id: string | null;
  preset_name: string;
  status: JobStatus;
  progress: number;
  content: string;
  partials_json: string | null;
  model_used: string | null;
  error_code: string | null;
  error_params: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
}

export interface Provider {
  id: string;
  kind: "stt" | "llm";
  name: string;
  base_url: string;
  default_model: string | null;
  context_tokens: number | null;
  is_default: boolean;
  api_key: string | null;
}

/**
 * The API answers with a stable `code`; the UI is multilingual, so the message
 * the user reads comes from the translation bundle, never from the wire.
 */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    readonly params: Record<string, unknown> = {},
  ) {
    super(code);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const isJson = typeof init?.body === "string";
    response = await fetch(path, {
      credentials: "same-origin",
      headers: isJson ? { "Content-Type": "application/json" } : undefined,
      ...init,
    });
  } catch {
    throw new ApiError("network", 0);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(error?.code ?? "unknown", response.status, error?.params ?? {});
  }

  return body as T;
}

export const api = {
  setupStatus: () => request<SetupStatus>("/api/setup/status"),

  createFirstAdmin: (username: string, password: string) =>
    request<User>("/api/setup", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  login: (username: string, password: string) =>
    request<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  me: () => request<User>("/api/auth/me"),

  listJobs: () => request<Job[]>("/api/jobs"),

  readJob: (id: string) => request<Job>(`/api/jobs/${id}`),

  readTranscript: (id: string) => request<Transcript>(`/api/jobs/${id}/transcript`),

  uploadJob: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    // No Content-Type header: the browser has to set the multipart boundary.
    return request<Job>("/api/jobs", { method: "POST", body });
  },

  cancelJob: (id: string) => request<Job>(`/api/jobs/${id}/cancel`, { method: "POST" }),

  audioUrl: (id: string) => `/api/jobs/${id}/audio`,

  /** Live job list. One connection for every job, not one per job: browsers cap
   * concurrent requests per origin, and a queue of ten would starve. */
  watchJobs: (onJobs: (jobs: Job[]) => void): (() => void) => {
    const source = new EventSource("/api/jobs/events");
    source.onmessage = (event) => onJobs(JSON.parse(event.data) as Job[]);
    // The server closes the stream once everything is terminal; EventSource
    // would reconnect forever, so close it on the way out.
    source.onerror = () => source.close();
    return () => source.close();
  },

  listProviders: () => request<Provider[]>("/api/providers"),

  listPresets: () => request<Preset[]>("/api/presets"),

  createPreset: (draft: PresetDraft) =>
    request<Preset>("/api/presets", { method: "POST", body: JSON.stringify(draft) }),

  updatePreset: (id: string, draft: PresetDraft) =>
    request<Preset>(`/api/presets/${id}`, { method: "PUT", body: JSON.stringify(draft) }),

  deletePreset: (id: string) => request<void>(`/api/presets/${id}`, { method: "DELETE" }),

  listSummaries: (jobId: string) => request<Summary[]>(`/api/jobs/${jobId}/summaries`),

  createSummary: (jobId: string, presetId: string) =>
    request<Summary>(`/api/jobs/${jobId}/summaries`, {
      method: "POST",
      body: JSON.stringify({ preset_id: presetId }),
    }),

  deleteSummary: (id: string) => request<void>(`/api/summaries/${id}`, { method: "DELETE" }),

  /** Follow one summary as the worker writes it. */
  watchSummary: (id: string, onSummary: (summary: Summary) => void): (() => void) => {
    const source = new EventSource(`/api/summaries/${id}/events`);
    source.onmessage = (event) => onSummary(JSON.parse(event.data) as Summary);
    source.onerror = () => source.close();
    return () => source.close();
  },
};
