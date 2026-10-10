import type {
  AnalysisList,
  AnalysisResponse,
  DeleteResponse,
  ErrorResponse,
  HealthResponse,
  RewriteRequest,
  RewriteResponse,
} from "@/types/api";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const BASE = `${API_URL}/api/v1`;

/** Error carrying the backend's `{ error: { code, message } }` payload. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(
      0,
      "network_error",
      `Could not reach the ResumeLens API at ${API_URL}. Check that the backend is running and that CORS allows this site.`,
    );
  }

  let body: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  if (!response.ok) {
    if (isErrorResponse(body)) throw new ApiError(response.status, body.error.code, body.error.message);
    throw new ApiError(response.status, "http_error", `The server responded with status ${response.status}.`);
  }
  return body as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export function analyzeResume(
  resume: File,
  jdText: string,
  save: boolean,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append("resume", resume, resume.name);
  form.append("jd_text", jdText);
  form.append("save", save ? "true" : "false");
  return request<AnalysisResponse>("/analyze", { method: "POST", body: form, signal });
}

export function listAnalyses(limit = 20, offset = 0, signal?: AbortSignal): Promise<AnalysisList> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return request<AnalysisList>(`/analyses?${params.toString()}`, { signal });
}

export function getAnalysis(id: string, signal?: AbortSignal): Promise<AnalysisResponse> {
  return request<AnalysisResponse>(`/analyses/${encodeURIComponent(id)}`, { signal });
}

export function deleteAnalysis(id: string): Promise<DeleteResponse> {
  return request<DeleteResponse>(`/analyses/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function deleteAllAnalyses(): Promise<DeleteResponse> {
  return request<DeleteResponse>("/analyses", { method: "DELETE" });
}

export function rewriteBullet(body: RewriteRequest): Promise<RewriteResponse> {
  return request<RewriteResponse>("/rewrite-bullet", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Turn any thrown value into a user-facing message. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Try again.";
}
