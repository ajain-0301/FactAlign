import type {
  CompareResponse, EvaluationRunOut, Experiment, ExperimentBody, Health, HistoryResponse, MetricsResponse, Preferences,
  Run, SamplesResponse, SettingsState, SummarizeBody, Verification, VerifyMethod,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const where = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== "body").join(".") : "";
        return `${where ? where + ": " : ""}${d?.msg ?? "invalid value"}`;
      })
      .join("; ");
  }
  return "Unexpected error";
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 300_000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
    if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
    const res = await fetch(`${API_URL}${path}`, { ...init, headers, signal: ctrl.signal, cache: "no-store" });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        detail = (await res.json()).detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(describe(detail), res.status);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") throw new ApiError("The request timed out.", 0);
    throw new ApiError(
      `Cannot reach the FactAlign backend at ${API_URL || "the frontend API proxy"}. Make sure it is running (start.bat) and try again.`, 0);
  } finally {
    clearTimeout(timer);
  }
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && u.set(k, String(v)));
  const s = u.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<Health>("/api/health", {}, 8000),
  samples: () => request<SamplesResponse>("/api/samples"),
  summarize: (b: SummarizeBody) => request<Run>("/api/summarize", { method: "POST", body: JSON.stringify(b) }),
  compare: (b: SummarizeBody) => request<CompareResponse>("/api/summarize/compare", { method: "POST", body: JSON.stringify(b) }),
  verify: (b: { source: string; summary: string; method?: VerifyMethod; run_id?: number; source_pages?: import("./types").SourcePage[] }) =>
    request<Verification>("/api/verify", { method: "POST", body: JSON.stringify(b) }),
  extract: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ filename: string; text: string; chars: number; words: number; pages: import("./types").SourcePage[] | null }>("/api/extract", { method: "POST", body: fd });
  },
  history: (p: Record<string, string | number | undefined>) => request<HistoryResponse>(`/api/history${qs(p)}`),
  run: (id: number) => request<Run>(`/api/history/${id}`),
  saveRun: (id: number) => request<Run>(`/api/history/${id}/save`, { method: "POST" }),
  deleteRun: (id: number) => request<{ deleted: number }>(`/api/history/${id}`, { method: "DELETE" }),
  historyExportUrl: (format: "csv" | "json", p: Record<string, string | undefined>) => `${API_URL}/api/history/export${qs({ format, ...p })}`,
  metrics: (p: Record<string, string | undefined>) => request<MetricsResponse>(`/api/evaluation/metrics${qs(p)}`),
  runEvaluation: (b: { strategies: string[]; length: string; language: string; verify_method?: string }) =>
    request<EvaluationRunOut>("/api/evaluation/run", { method: "POST", body: JSON.stringify(b) }),
  evaluationExportUrl: (kind: "runs" | "benchmark", format: "csv" | "json", p: Record<string, string | undefined> = {}) =>
    `${API_URL}/api/evaluation/export${qs({ kind, format, ...p })}`,
  experiments: (p: Record<string, string | undefined> = {}) =>
    request<{ total: number; items: Experiment[] }>(`/api/experiments${qs(p)}`),
  experiment: (id: number) => request<Experiment>(`/api/experiments/${id}`),
  createExperiment: (b: ExperimentBody) => request<Experiment>("/api/experiments", { method: "POST", body: JSON.stringify(b) }),
  deleteExperiment: (id: number) => request<{ deleted: number }>(`/api/experiments/${id}`, { method: "DELETE" }),
  settings: () => request<SettingsState>("/api/settings"),
  updateSettings: (b: Partial<Preferences>) => request<SettingsState>("/api/settings", { method: "PUT", body: JSON.stringify(b) }),
  testConnection: (model?: string) =>
    request<{ ok: boolean; model: string; latency_ms: number }>("/api/settings/test-connection", { method: "POST", body: JSON.stringify({ model }) }, 120_000),
};
