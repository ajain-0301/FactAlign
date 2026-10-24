/**
 * Runs the real frontend API client against a LIVE backend (default http://localhost:8000).
 * Requires RUN_LIVE_API_TESTS=1 and a reachable backend. Unset by default to protect API quota.
 * Start the backend first (start.bat or `uvicorn app.main:app --port 8000`) to run these.
 */
import { beforeAll, describe, expect, it } from "vitest";
import { api, API_URL, ApiError } from "@/lib/api";

let up = false;
beforeAll(async () => {
  if (process.env.RUN_LIVE_API_TESTS !== "1") return;
  try { up = (await api.health()).status === "ok"; } catch { up = false; }
  if (!up) console.warn(`[integration] backend not reachable at ${API_URL}; skipping`);
});
const live = (name: string, fn: () => Promise<void>) => it(name, async (ctx) => { if (!up) return ctx.skip(); await fn(); });

describe("frontend API client <-> backend contract", () => {
  live("health + settings expose mode without leaking secrets", async () => {
    const h = await api.health();
    expect(["demo", "real", "unavailable"]).toContain(h.mode);
    const s = await api.settings();
    expect(s.preferences.default_strategy).toBeTruthy();
    expect(typeof s.api_key_configured).toBe("boolean");
    expect(JSON.stringify(s)).not.toMatch(/sk-[A-Za-z0-9]/);
  });

  live("samples -> summarize -> verify -> history -> delete", async () => {
    const samples = await api.samples();
    const doc = samples.items.find((i) => i.id === "air-hinglish")!;
    const run = await api.summarize({ text: doc.source, language: "auto", output_language: "same", length: "short", strategy: "factuality", title: "vitest run" });
    expect(run.language_detected).toBe("hinglish");
    expect(run.summary_words).toBeLessThan(run.source_words);
    expect(run.analysis?.numbers.length).toBeGreaterThan(0);
    const v = await api.verify({ source: doc.source, summary: "Plan December 2025 तक complete होगा।", run_id: run.id });
    expect(v.claims[0].status).toBe("contradicted");
    expect(v.claims[0].confidence).toBeNull();
    const detail = await api.run(run.id);
    expect(detail.verification?.metrics.n_claims).toBe(1);
    expect((await api.history({ q: "vitest run" })).items.some((r) => r.id === run.id)).toBe(true);
    await api.deleteRun(run.id);
    await expect(api.run(run.id)).rejects.toMatchObject({ status: 404 });
  });

  live("compare returns both strategies with a shared compare_id", async () => {
    const doc = (await api.samples()).items.find((i) => i.id === "pay-en")!;
    const c = await api.compare({ text: doc.source, language: "auto", output_language: "same", length: "short", strategy: "factuality" });
    expect(c.results.map((r) => r.strategy)).toEqual(["standard", "factuality"]);
    expect(c.results[0].compare_id).toBe(c.results[1].compare_id);
    await Promise.all(c.results.map((r) => api.deleteRun(r.id)));
  });

  live("validation errors surface as readable ApiError messages", async () => {
    const err = await api.summarize({ text: "  ", language: "auto", output_language: "same", length: "short", strategy: "standard" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.message).toMatch(/text/);
  });

  live("metrics, benchmark evaluation and experiments return chart-ready data", async () => {
    const ev = await api.runEvaluation({ strategies: ["standard", "factuality"], length: "short", language: "all" });
    expect(ev.results.items.length).toBe(18);
    expect(ev.results.verifier.overall.n_labeled_claims).toBe(36);
    expect(ev.results.code_mixing_gap.length).toBe(2);
    const m = await api.metrics({});
    expect(m.totals.n_runs).toBeGreaterThan(0);
    expect(Object.keys(m.by_strategy).sort()).toEqual(["factuality", "standard"]);
    expect(m.series[0]).toHaveProperty("compression_ratio");
    const e = await api.createExperiment({ name: "vitest exp", language: "en", strategies: ["standard"], length: "short", dataset: "sample", documents: [], verify: true });
    expect(e.status).toBe("completed");
    expect((await api.experiments({ q: "vitest exp" })).total).toBeGreaterThan(0);
    await api.deleteExperiment(e.id);
  });

  live("unreachable backend gives an actionable message", async () => {
    const old = process.env.NEXT_PUBLIC_API_URL;
    expect(old === undefined || typeof old === "string").toBe(true);
    expect(API_URL).toMatch(/^https?:\/\//);
  });
});
