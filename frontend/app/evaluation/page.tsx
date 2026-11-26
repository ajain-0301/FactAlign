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
  const [bLength, setBLength] = React.useState("short"); const [bLang, setBLang] = React.useState("all"); const [selectedBenchmark, setSelectedBenchmark] = React.useState("benchmark_01");

  const filters = React.useMemo(() => ({ language: language || undefined, strategy: strategy || undefined, scope: scope === "all" ? undefined : scope, mode: mode || undefined }), [language, strategy, scope, mode]);
  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try { const r = await api.metrics(filters); setM(r); setBench((b) => b ?? r.latest_evaluation); }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }, [filters]);
  React.useEffect(() => { load(); }, [load]);

  const runBench = async () => {
    setRunning(true);
    setRunError(null);

    try {
      const r = await api.runEvaluation({
        strategies: ["standard", "factuality"],
        length: bLength,
        language: bLang,
      });

      setBench(r);
      toast("Benchmark evaluation finished");
      load();
    } catch (e) {
      setRunError((e as Error).message);
    } finally {
      setRunning(false);
    }
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
          <p className="mt-1 max-w-2xl text-sm text-muted">Metrics computed from stored runs and benchmark data. Verifier precision, recall and F1 require author-labelled claims.</p>
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
            <CardHeader><div><CardTitle>Summary metrics by strategy</CardTitle></div></CardHeader>
            <CardContent className="overflow-x-auto scroll-thin">
              <table className="w-full min-w-[680px] text-sm">
                <thead><tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">{["Strategy", "Avg length", "Compression", "Inference", "Claim support", "ROUGE-L (n refs)"].map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}</tr></thead>
                <tbody>{Object.entries(m.by_strategy).map(([s, a]) => (<tr key={s} className="border-b border-border/60 last:border-0"><td className="py-2.5 pr-4 font-medium">{STRATEGY_LABEL[s]}</td>
                  <td className="pr-4">{num(a.avg_summary_words, 1)} words</td><td className="pr-4">{pct(a.avg_compression_ratio, 1)}</td><td className="pr-4">{ms(a.avg_inference_ms)}</td>
                  <td className="pr-4">{pct(a.claim_support_rate, 1)}</td>
                  <td className="pr-4">{a.rougeL_f1 != null ? `${num(a.rougeL_f1, 3)}` : "no references"}</td></tr>))}</tbody>
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
