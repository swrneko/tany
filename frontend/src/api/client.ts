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
    response = await fetch(path, {
      credentials: "same-origin",
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
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
};
