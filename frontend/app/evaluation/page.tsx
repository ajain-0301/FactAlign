"use client";
import * as React from "react";
import { BarChart3, Download, Play } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/components/app-provider";
import type { EvaluationRunOut, GroupAgg, MetricsResponse, VerifierEval } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNote, InfoNote } from "@/components/ui/empty-state";
import { Field, Select } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { Lines, MetricBars } from "@/components/features/charts";
import { formatDate, LANG_SHORT, ms, num, pct, STRATEGY_LABEL } from "@/lib/utils";

type Row = GroupAgg & { strategy: string; language: string };
const METRICS: { key: keyof GroupAgg; series?: string; label: string; fmt: (v: number) => string; note?: string }[] = [
  { key: "avg_compression_ratio", series: "compression_ratio", label: "Compression ratio (summary ÷ source)", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "avg_summary_words", series: "summary_words", label: "Average summary length (words)", fmt: (v) => v.toFixed(1) },
  { key: "avg_inference_ms", series: "inference_ms", label: "Inference time (ms)", fmt: (v) => v.toFixed(1) },
  { key: "claim_support_rate", series: "claim_support_rate", label: "Claim-support rate (automatic estimate)", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "rougeL_f1", series: "rougeL_f1", label: "ROUGE-L F1 (needs references)", fmt: (v) => v.toFixed(3) },
  { key: "avg_cmi", series: "cmi", label: "Code-Mixing Index (CMI)", fmt: (v) => v.toFixed(1) },
];

function Cm({ e }: { e: VerifierEval }) {
  const labels = ["supported", "contradicted", "unverifiable"];
  return (
    <table className="text-sm"><thead><tr><th className="pr-3 text-left text-xs font-normal text-muted">gold ↓ / predicted →</th>{labels.map((l) => <th key={l} className="px-3 text-xs font-medium capitalize">{l}</th>)}</tr></thead>
      <tbody>{labels.map((g) => (<tr key={g} className="border-t border-border/60"><th className="py-2 pr-3 text-left text-xs font-medium capitalize">{g}</th>
        {labels.map((p) => <td key={p} className={`px-3 py-2 text-center ${g === p ? "font-semibold text-ok" : e.confusion[g][p] ? "text-bad" : "text-muted"}`}>{e.confusion[g][p]}</td>)}</tr>))}</tbody></table>
  );
}

export default function EvaluationPage() {
  const { backendDown, settings } = useApp();
  const { toast } = useToast();
  const [language, setLanguage] = React.useState(""); const [strategy, setStrategy] = React.useState("");
  const [scope, setScope] = React.useState("all"); const [mode, setMode] = React.useState("");
  const [m, setM] = React.useState<MetricsResponse | null>(null);
  const [loading, setLoading] = React.useState(true); const [error, setError] = React.useState<string | null>(null);
  const [metric, setMetric] = React.useState(0);
  const [bench, setBench] = React.useState<EvaluationRunOut | null>(null);
  const [running, setRunning] = React.useState(false); const [runError, setRunError] = React.useState<string | null>(null);
  const [bLength, setBLength] = React.useState("short"); const [bLang, setBLang] = React.useState("all");

  const filters = React.useMemo(() => ({ language: language || undefined, strategy: strategy || undefined, scope: scope === "all" ? undefined : scope, mode: mode || undefined }), [language, strategy, scope, mode]);
  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try { const r = await api.metrics(filters); setM(r); setBench((b) => b ?? r.latest_evaluation); }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }, [filters]);
  React.useEffect(() => { load(); }, [load]);

  const runBench = async () => {
    setRunning(true); setRunError(null);
    try { const r = await api.runEvaluation({ strategies: ["standard", "factuality"], length: bLength, language: bLang }); setBench(r); toast("Benchmark evaluation finished"); load(); }
    catch (e) { setRunError((e as Error).message); } finally { setRunning(false); }
  };

  const cur = METRICS[metric];
  const langs = m ? Array.from(new Set((m.by_strategy_language as Row[]).map((r) => r.language))) : [];
  const barData = langs.map((l) => ({ name: LANG_SHORT[l] ?? l, ...Object.fromEntries((m!.by_strategy_language as Row[]).filter((r) => r.language === l).map((r) => [r.strategy, (r[cur.key] as number | null | undefined) ?? null])) }));
  const lineData = (m?.series ?? []).map((s) => ({ x: s.run_id, [s.strategy]: (s as unknown as Record<string, number | null>)[cur.series ?? ""] ?? null }));
  const exportParams = { language: filters.language, strategy: filters.strategy, scope: filters.scope, mode: filters.mode } as Record<string, string | undefined>;
  const v = bench?.results.verifier;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-serif text-3xl tracking-tight">Evaluation</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">Metrics computed from stored runs, plus a labelled benchmark for precision, recall and F1. Each number says what data it needs.</p>
        </div>
        <div className="flex gap-2">
          <a href={api.evaluationExportUrl("runs", "csv", exportParams)} download><Button size="sm" tabIndex={-1}><Download className="h-4 w-4" />Runs CSV</Button></a>
          <a href={api.evaluationExportUrl("runs", "json", exportParams)} download><Button size="sm" tabIndex={-1}><Download className="h-4 w-4" />Runs JSON</Button></a>
        </div>
      </div>

      <Card><CardContent className="grid gap-3 pt-5 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Language"><Select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="">All</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hinglish</option></Select></Field>
        <Field label="Strategy"><Select value={strategy} onChange={(e) => setStrategy(e.target.value)}><option value="">All</option><option value="standard">Standard</option><option value="factuality">Factuality-aware</option></Select></Field>
        <Field label="Source of runs"><Select value={scope} onChange={(e) => setScope(e.target.value)}><option value="all">Everything</option><option value="workspace">Workspace only</option><option value="experiments">Experiments</option><option value="evaluation">Benchmark runs</option></Select></Field>
        <Field label="Engine"><Select value={mode} onChange={(e) => setMode(e.target.value)}><option value="">Demo + real</option><option value="real">Real AI only</option><option value="demo">Demo only</option></Select></Field>
      </CardContent></Card>

      {error && <ErrorNote message={backendDown ? "The backend is offline." : error} />}
      {loading && !m && <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-72" /></div>}

      {m && m.totals.n_runs === 0 && (
        <EmptyState icon={<BarChart3 className="h-6 w-6" />} title="No runs match these filters" description="Metrics appear once summaries exist. Run the sample benchmark below to generate evaluation data, or create a summary first." />
      )}

      {m && m.totals.n_runs > 0 && (
        <>
          <Card>
            <CardHeader><div><CardTitle>Summary metrics by strategy</CardTitle><CardDescription>{m.totals.n_runs} runs · {m.counts.demo} demo / {m.counts.real} real in the database</CardDescription></div></CardHeader>
            <CardContent className="overflow-x-auto scroll-thin">
              <table className="w-full min-w-[680px] text-sm">
                <thead><tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">{["Strategy", "Runs", "Avg length", "Compression", "Inference", "Claim support", "ROUGE-L (n refs)"].map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}</tr></thead>
                <tbody>{Object.entries(m.by_strategy).map(([s, a]) => (<tr key={s} className="border-b border-border/60 last:border-0"><td className="py-2.5 pr-4 font-medium">{STRATEGY_LABEL[s]}</td><td className="pr-4">{a.n_runs}</td>
                  <td className="pr-4">{num(a.avg_summary_words, 1)} words</td><td className="pr-4">{pct(a.avg_compression_ratio, 1)}</td><td className="pr-4">{ms(a.avg_inference_ms)}</td>
                  <td className="pr-4">{pct(a.claim_support_rate, 1)} <span className="text-xs text-muted">({a.n_claims ?? 0} claims)</span></td>
                  <td className="pr-4">{a.rougeL_f1 != null ? `${num(a.rougeL_f1, 3)} (${a.n_with_reference})` : "no references"}</td></tr>))}</tbody>
              </table>
            </CardContent>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader><div><CardTitle>By language</CardTitle><CardDescription>{cur.label}</CardDescription></div>
                <Select aria-label="Metric" className="w-auto max-w-[210px]" value={metric} onChange={(e) => setMetric(Number(e.target.value))}>{METRICS.map((x, i) => <option key={x.key} value={i}>{x.label.split(" (")[0]}</option>)}</Select></CardHeader>
              <CardContent><MetricBars label={cur.label} data={barData} series={[{ key: "standard", name: "Standard" }, { key: "factuality", name: "Factuality-aware" }]} format={cur.fmt} /></CardContent>
            </Card>
            <Card>
              <CardHeader><div><CardTitle>Per run</CardTitle><CardDescription>{cur.label}, in run order</CardDescription></div></CardHeader>
              <CardContent><Lines label={`${cur.label} per run`} data={lineData} series={[{ key: "standard", name: "Standard" }, { key: "factuality", name: "Factuality-aware" }]} format={cur.fmt} /></CardContent>
            </Card>
          </div>
        </>
      )}

      <Card>
        <CardHeader><div><CardTitle>Labelled benchmark &amp; code-mixing analysis</CardTitle>
          <CardDescription>Runs the built-in synthetic parallel set (Hindi / Hinglish / English) through both strategies, then scores the verifier on author-labelled claims.</CardDescription></div></CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Length" className="w-36"><Select value={bLength} onChange={(e) => setBLength(e.target.value)}><option value="short">Short</option><option value="medium">Medium</option><option value="long">Long</option></Select></Field>
            <Field label="Language" className="w-44"><Select value={bLang} onChange={(e) => setBLang(e.target.value)}><option value="all">All (9 docs)</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hinglish</option></Select></Field>
            <Button variant="primary" onClick={runBench} loading={running} disabled={backendDown}><Play className="h-4 w-4" />Run benchmark</Button>
            {bench && <>
              <a href={api.evaluationExportUrl("benchmark", "csv")} download><Button size="sm" tabIndex={-1}><Download className="h-4 w-4" />CSV</Button></a>
              <a href={api.evaluationExportUrl("benchmark", "json")} download><Button size="sm" tabIndex={-1}><Download className="h-4 w-4" />JSON</Button></a></>}
          </div>
          {settings?.effective_mode === "real" && <InfoNote>Real AI mode: this makes ~{bLang === "all" ? 18 : 6} summarization calls plus verification calls to the paid API.</InfoNote>}
          {runError && <ErrorNote message={runError} />}

          {!bench && !running && <p className="text-sm text-muted">No benchmark has been run yet. Press “Run benchmark”; nothing below is shown until real results exist.</p>}
          {bench && v && (
            <div className="space-y-6">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge tone={bench.mode === "demo" ? "warn" : "ok"}>{bench.mode === "demo" ? "Demo engine (extractive)" : bench.model}</Badge>
                <span className="text-muted">Run #{bench.id} · {formatDate(bench.created_at)} · {bench.dataset} · verifier: {v.method}</span>
              </div>
              <div className="space-y-2">{bench.results.notes.filter(Boolean).map((n, i) => <InfoNote key={i} tone={i === 0 ? "warn" : "accent"}>{n}</InfoNote>)}</div>

              <div>
                <h4 className="mb-3 font-serif text-lg">Verifier precision / recall / F1 <span className="text-sm font-normal text-muted">on {v.overall.n_labeled_claims} labelled claims</span></h4>
                <div className="grid gap-5 lg:grid-cols-2">
                  <div className="overflow-x-auto scroll-thin"><table className="w-full min-w-[420px] text-sm">
                    <thead><tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">{["Class", "Precision", "Recall", "F1", "TP / FP / FN"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}</tr></thead>
                    <tbody>{Object.entries(v.overall.per_class).map(([c, p]) => (<tr key={c} className="border-b border-border/60"><td className="py-2 pr-3 font-medium capitalize">{c}</td><td className="pr-3">{p.precision != null ? num(p.precision, 3) : "n/a"}</td><td className="pr-3">{p.recall != null ? num(p.recall, 3) : "n/a"}</td><td className="pr-3">{p.f1 != null ? num(p.f1, 3) : "n/a"}</td><td className="pr-3 text-muted">{p.tp} / {p.fp} / {p.fn}</td></tr>))}
                      <tr className="border-b border-border/60"><td className="py-2 pr-3 font-medium">Unsupported detection*</td><td className="pr-3">{num(v.overall.unsupported_detection.precision, 3)}</td><td className="pr-3">{num(v.overall.unsupported_detection.recall, 3)}</td><td className="pr-3">{num(v.overall.unsupported_detection.f1, 3)}</td><td className="pr-3 text-muted">{v.overall.unsupported_detection.tp} / {v.overall.unsupported_detection.fp} / {v.overall.unsupported_detection.fn}</td></tr>
                      <tr><td className="py-2 pr-3 font-medium">Macro-F1 · accuracy</td><td colSpan={4} className="pr-3">{num(v.overall.macro_f1, 3)} · {pct(v.overall.accuracy, 1)}</td></tr></tbody></table>
                    <p className="mt-2 text-xs text-muted">*Positive class = contradicted or unverifiable (i.e. “not supported”).</p></div>
                  <div><Cm e={v.overall} /></div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-sm">{Object.entries(v.by_language).map(([l, e]) => <Badge key={l}>{LANG_SHORT[l]}: accuracy {pct(e.accuracy, 0)} · macro-F1 {num(e.macro_f1, 2)}</Badge>)}</div>
              </div>

              <div>
                <h4 className="mb-3 font-serif text-lg">Summarizer metrics by strategy × language</h4>
                <div className="overflow-x-auto scroll-thin"><table className="w-full min-w-[760px] text-sm">
                  <thead><tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">{["Strategy", "Lang", "n", "Words", "Compression", "ROUGE-1", "ROUGE-2", "ROUGE-L", "Fact prec.", "Fact recall (ref)", "Claim support", "CMI"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}</tr></thead>
                  <tbody>{[...bench.results.by_strategy_language].sort((a, b) => a.strategy.localeCompare(b.strategy) || a.language.localeCompare(b.language)).map((r) => (
                    <tr key={r.strategy + r.language} className="border-b border-border/60"><td className="py-2 pr-3 font-medium">{STRATEGY_LABEL[r.strategy]}</td><td className="pr-3">{LANG_SHORT[r.language]}</td><td className="pr-3">{r.n}</td><td className="pr-3">{num(r.avg_summary_words, 1)}</td><td className="pr-3">{pct(r.avg_compression_ratio, 1)}</td>
                      <td className="pr-3">{num(r.rouge1_f1, 3)}</td><td className="pr-3">{num(r.rouge2_f1, 3)}</td><td className="pr-3">{num(r.rougeL_f1, 3)}</td><td className="pr-3">{pct(r.fact_precision, 0)}</td><td className="pr-3">{pct(r.fact_recall_ref, 0)}</td><td className="pr-3">{pct(r.claim_support_rate, 0)}</td><td className="pr-3">{num(r.avg_cmi, 1)}</td></tr>))}</tbody></table></div>
              </div>

              {bench.results.code_mixing_gap.length > 0 && (
                <div>
                  <h4 className="mb-1 font-serif text-lg">Code-mixing effect (Hinglish − Hindi, same facts)</h4>
                  <p className="mb-3 text-sm text-muted">Each topic exists in both Devanagari Hindi and Hinglish. Negative values mean the code-mixed version scored lower. With 3 pairs this is illustrative only.</p>
                  <MetricBars label="Mean Hinglish minus Hindi difference" height={240}
                    data={[{ key: "rougeL_f1", name: "ROUGE-L F1" }, { key: "claim_support_rate", name: "Claim support" }, { key: "fact_precision", name: "Fact precision" }, { key: "compression_ratio", name: "Compression" }]
                      .map((k) => ({ name: k.name, ...Object.fromEntries(bench.results.code_mixing_gap.map((g) => [g.strategy, g.mean_delta[k.key]])) }))}
                    series={[{ key: "standard", name: "Standard" }, { key: "factuality", name: "Factuality-aware" }]} format={(x) => x.toFixed(3)} />
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {m && (
        <Card>
          <CardHeader><div><CardTitle>How each metric is computed</CardTitle></div></CardHeader>
          <CardContent>
            <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">{Object.entries(m.formulas).map(([k, f]) => (<div key={k}><dt className="font-medium">{k.replace(/_/g, " ")}</dt><dd className="mt-0.5 leading-relaxed text-muted">{f}</dd></div>))}</dl>
            <ul className="mt-5 list-disc space-y-1 pl-5 text-xs text-muted">{m.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
