"use client";
import * as React from "react";
import Link from "next/link";
import { BarChart3, FlaskConical, LayoutDashboard, SquarePen } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/components/app-provider";
import type { Experiment, MetricsResponse, Run } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNote, InfoNote, Stat } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Donut, MetricBars } from "@/components/features/charts";
import { formatDate, LANG_SHORT, ms, num, pct, STRATEGY_LABEL } from "@/lib/utils";

export default function OverviewPage() {
  const { backendDown } = useApp();
  const [m, setM] = React.useState<MetricsResponse | null>(null);
  const [recent, setRecent] = React.useState<Run[]>([]);
  const [exps, setExps] = React.useState<Experiment[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    Promise.all([api.metrics({}), api.history({ limit: 5 }), api.experiments()])
      .then(([mm, h, e]) => { setM(mm); setRecent(h.items); setExps(e.items.slice(0, 5)); })
      .catch((e) => setError((e as Error).message)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-4"><div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div><Skeleton className="h-72" /></div>;
  if (error) return <ErrorNote message={backendDown ? "The backend is offline, so there is nothing to show yet." : error} />;
  if (!m || m.totals.n_runs === 0) {
    return (
      <EmptyState icon={<LayoutDashboard className="h-6 w-6" />} title="No summarization runs yet"
        description="This dashboard is built only from runs stored in your local database, so it is empty until you create some. Summarize a document, or run the sample benchmark to see the full evaluation.">
        <Link href="/"><Button variant="primary"><SquarePen className="h-4 w-4" />New summary</Button></Link>
        <Link href="/evaluation"><Button><BarChart3 className="h-4 w-4" />Run sample evaluation</Button></Link>
      </EmptyState>
    );
  }
  const t = m.totals;
  const strategies = Object.entries(m.by_strategy);
  const stratData = (key: keyof typeof t, scale = 1) => strategies.map(([s, a]) => ({ name: STRATEGY_LABEL[s], value: a[key as keyof typeof a] == null ? null : Number(a[key as keyof typeof a]) * scale }));
  const lang = Object.entries(m.language_distribution).map(([k, v]) => ({ name: LANG_SHORT[k] ?? k, value: v }));

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-serif text-3xl tracking-tight">Overview</h2>
        <p className="mt-1 text-sm text-muted">Live statistics from your local database. {m.counts.demo} demo run{m.counts.demo === 1 ? "" : "s"} · {m.counts.real} real-AI run{m.counts.real === 1 ? "" : "s"}.</p>
      </div>
      {m.counts.demo > 0 && <InfoNote>{m.counts.demo} of {m.counts.all} runs used the rule-based demo engine. Their numbers describe that baseline, not an LLM. Use Evaluation to filter by mode.</InfoNote>}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <Stat label="Total runs" value={m.counts.all} sub={`${m.counts.workspace} workspace · ${m.counts.experiments} experiment · ${m.counts.evaluation} benchmark`} />
        <Stat label="Avg summary length" value={`${num(t.avg_summary_words, 0)}`} sub="words" />
        <Stat label="Avg compression" value={pct(t.avg_compression_ratio, 1)} sub="summary ÷ source" hint="Lower means a shorter summary" />
        <Stat label="Avg inference" value={ms(t.avg_inference_ms)} sub={`median ${ms(t.median_inference_ms)}`} />
        <Stat label="Claim-support rate" value={pct(t.claim_support_rate, 1)} sub={t.n_claims ? `${t.n_claims} claims · ${t.n_verified_runs} runs verified` : "no verified runs yet"} hint="Automatic estimate, not ground truth" />
        <Stat label="With reference" value={t.n_with_reference ?? 0} sub={t.rougeL_f1 != null ? `ROUGE-L ${num(t.rougeL_f1, 3)}` : "ROUGE needs references"} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader><div><CardTitle>Language distribution</CardTitle><CardDescription>Detected language per run</CardDescription></div></CardHeader>
          <CardContent><Donut data={lang} label="Runs by language" /></CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader><div><CardTitle>Strategy comparison</CardTitle><CardDescription>Averages over all stored runs per strategy</CardDescription></div></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            {([["Compression (%)", "avg_compression_ratio", 100, (v: number) => `${v.toFixed(0)}%`],
               ["Inference (ms)", "avg_inference_ms", 1, (v: number) => `${v.toFixed(0)}`],
               ["Claim support (%)", "claim_support_rate", 100, (v: number) => `${v.toFixed(0)}%`]] as const).map(([title, key, scale, fmt]) => (
              <div key={title}>
                <div className="mb-1 text-center text-xs font-medium text-muted">{title}</div>
                <MetricBars label={title} height={200} data={stratData(key, scale)} series={[{ key: "value", name: title }]} format={fmt} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Recent summaries</CardTitle><Link href="/history" className="text-sm text-accent hover:underline">View all</Link></CardHeader>
          <CardContent>
            {recent.length === 0 ? <p className="text-sm text-muted">No saved summaries yet.</p> : (
              <ul className="divide-y divide-border">{recent.map((r) => (
                <li key={r.id} className="py-3">
                  <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{r.title || `#${r.id}`}</span>
                    <Badge tone="accent">{STRATEGY_LABEL[r.strategy]}</Badge><Badge>{LANG_SHORT[r.language_detected]}</Badge></div>
                  <p className="mt-1 line-clamp-1 text-sm text-muted">{r.summary}</p>
                  <p className="mt-0.5 text-xs text-muted">{formatDate(r.created_at)}</p>
                </li>))}</ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Recent experiments</CardTitle><Link href="/experiments" className="text-sm text-accent hover:underline">View all</Link></CardHeader>
          <CardContent>
            {exps.length === 0 ? (
              <div className="flex flex-col items-start gap-3 text-sm text-muted"><p>No experiments yet.</p><Link href="/experiments"><Button size="sm"><FlaskConical className="h-4 w-4" />Create one</Button></Link></div>
            ) : (
              <ul className="divide-y divide-border">{exps.map((e) => (
                <li key={e.id} className="py-3">
                  <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{e.name}</span>
                    <Badge tone={e.status === "completed" ? "ok" : "bad"}>{e.status}</Badge>{e.mode === "demo" && <Badge tone="warn">demo</Badge>}</div>
                  <p className="mt-0.5 text-xs text-muted">{formatDate(e.created_at)} · {e.results.n_runs ?? 0} runs · support {pct(e.results.overall?.claim_support_rate, 0)}</p>
                </li>))}</ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
