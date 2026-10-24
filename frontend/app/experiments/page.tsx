"use client";
import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FlaskConical, GitCompare, Plus, Search, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/components/app-provider";
import type { Experiment, ExperimentBody, Strategy } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorNote, InfoNote } from "@/components/ui/empty-state";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { MetricBars } from "@/components/features/charts";
import { formatDate, LANG_LABEL, ms, num, pct, STRATEGY_LABEL } from "@/lib/utils";

const schema = z.object({
  name: z.string().trim().min(1, "Give the experiment a name").max(200),
  description: z.string().max(1000).optional(),
  dataset: z.enum(["sample", "custom"]),
  language: z.enum(["all", "hi", "en", "hinglish"]),
  standard: z.boolean(), factuality: z.boolean(),
  length: z.enum(["short", "medium", "long"]),
  model: z.string().optional(),
  verify: z.boolean(),
  customDocs: z.string().optional(),
}).superRefine((v, ctx) => {
  if (!v.standard && !v.factuality) ctx.addIssue({ code: "custom", path: ["factuality"], message: "Select at least one strategy" });
  if (v.dataset === "custom" && !(v.customDocs ?? "").trim()) ctx.addIssue({ code: "custom", path: ["customDocs"], message: "Add at least one document" });
});
type FormValues = z.infer<typeof schema>;

function NewExperiment({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (e: Experiment) => void }) {
  const { settings } = useApp();
  const real = settings?.effective_mode === "real";
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", dataset: "sample", language: "all", standard: true, factuality: true, length: "short", model: "", verify: true, customDocs: "" },
  });
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const dataset = watch("dataset");
  const nStrat = Number(watch("standard")) + Number(watch("factuality"));
  const lang = watch("language");
  const nDocs = dataset === "sample" ? (lang === "all" ? 9 : 3) : (watch("customDocs") ?? "").split(/\n\s*---+\s*\n/).filter((s) => s.trim()).length;

  const submit = handleSubmit(async (v) => {
    setBusy(true); setErr(null);
    const strategies = ([v.standard && "standard", v.factuality && "factuality"].filter(Boolean)) as Strategy[];
    const body: ExperimentBody = {
      name: v.name, description: v.description || undefined, language: v.language, strategies, length: v.length,
      model: real && v.model ? v.model : undefined, dataset: v.dataset, verify: v.verify,
      documents: v.dataset === "custom" ? (v.customDocs ?? "").split(/\n\s*---+\s*\n/).map((t) => t.trim()).filter(Boolean).map((text, i) => ({ title: `Document ${i + 1}`, text })) : [],
    };
    try { onCreated(await api.createExperiment(body)); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  });

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !busy && onClose()} title="New experiment" description="Runs every selected strategy on every document and stores the results.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="Name" error={errors.name?.message}><Input {...register("name")} placeholder="e.g. Hinglish vs Hindi, short summaries" /></Field>
        <Field label="Notes (optional)"><Textarea {...register("description")} className="min-h-[60px]" /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Documents">
            <Select {...register("dataset")}><option value="sample">Built-in synthetic benchmark</option><option value="custom">My own documents</option></Select>
          </Field>
          <Field label="Language" hint={dataset === "sample" ? "Filters the benchmark (3 docs per language)." : "Applied to documents without their own language."}>
            <Select {...register("language")}>{Object.entries(LANG_LABEL).filter(([k]) => k !== "auto").map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
          </Field>
        </div>
        {dataset === "custom" && (
          <Field label="Documents" error={errors.customDocs?.message} hint="Separate documents with a line containing only ---">
            <Textarea {...register("customDocs")} className="min-h-[140px]" placeholder={"First document…\n---\nSecond document…"} />
          </Field>
        )}
        <fieldset className="space-y-2">
          <legend className="text-[13px] font-medium">Strategies</legend>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[hsl(var(--accent))]" {...register("standard")} />Standard</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[hsl(var(--accent))]" {...register("factuality")} />Factuality-aware</label>
          </div>
          {errors.factuality && <p className="text-xs text-bad" role="alert">{errors.factuality.message}</p>}
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Summary length"><Select {...register("length")}><option value="short">Short</option><option value="medium">Medium</option><option value="long">Long</option></Select></Field>
          <Field label="Model" hint={real ? "Overrides the default model for this experiment." : "Demo mode: rule-based engine, no model."}>
            <Select {...register("model")} disabled={!real}><option value="">{settings?.model ?? "Default"}</option>{settings?.model_options.map((m) => <option key={m} value={m}>{m}</option>)}</Select>
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[hsl(var(--accent))]" {...register("verify")} />Run factuality verification on every summary</label>
        <InfoNote tone={real ? "warn" : "accent"}>
          {real ? `This will make about ${nDocs * nStrat} model call${nDocs * nStrat === 1 ? "" : "s"} (plus verification calls) to a paid API and may take a few minutes.`
            : `Demo mode: ${nDocs * nStrat} rule-based run${nDocs * nStrat === 1 ? "" : "s"}; finishes in about a second and costs nothing.`}
        </InfoNote>
        {err && <ErrorNote message={err} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="primary" loading={busy}><FlaskConical className="h-4 w-4" />Run experiment</Button>
        </div>
      </form>
    </Dialog>
  );
}

function Detail({ id, onClose, onDeleted }: { id: number; onClose: () => void; onDeleted: (id: number) => void }) {
  const { toast } = useToast();
  const [e, setE] = React.useState<Experiment | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [confirm, setConfirm] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => { api.experiment(id).then(setE).catch((x) => setErr((x as Error).message)); }, [id]);
  const del = async () => {
    setBusy(true);
    try { await api.deleteExperiment(id); toast("Experiment deleted"); onDeleted(id); } catch (x) { toast((x as Error).message, "bad"); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} wide title={e?.name ?? "Experiment"} description={e ? `${formatDate(e.created_at)} · ${e.mode === "demo" ? "demo (rule-based)" : e.model}` : undefined}>
      {err && <ErrorNote message={err} />}
      {!e && !err && <Skeleton className="h-40" />}
      {e && (
        <div className="space-y-6">
          {e.status === "failed" && <ErrorNote message={`This experiment failed: ${e.error ?? "unknown error"}. ${e.results.n_runs ?? 0} of ${e.results.planned_runs ?? "?"} runs completed before the failure.`} />}
          {e.description && <p className="text-sm text-muted">{e.description}</p>}
          <div className="flex flex-wrap gap-2">
            <Badge tone={e.status === "completed" ? "ok" : "bad"}>{e.status}</Badge><Badge>{LANG_LABEL[e.language]}</Badge><Badge>length: {e.length}</Badge>
            {e.strategies.map((s) => <Badge key={s} tone="accent">{STRATEGY_LABEL[s]}</Badge>)}<Badge>{ms(e.duration_ms)} total</Badge>
            {e.mode === "demo" && <Badge tone="warn">demo engine</Badge>}
          </div>
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[560px] text-sm">
              <thead><tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                {["Strategy", "Runs", "Avg words", "Compression", "Inference", "Claim support", "ROUGE-L"].map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}</tr></thead>
              <tbody>{Object.entries(e.results.by_strategy ?? {}).map(([s, a]) => (
                <tr key={s} className="border-b border-border/60"><td className="py-2.5 pr-4 font-medium">{STRATEGY_LABEL[s]}</td><td className="pr-4">{a.n_runs}</td>
                  <td className="pr-4">{num(a.avg_summary_words, 0)}</td><td className="pr-4">{pct(a.avg_compression_ratio, 1)}</td><td className="pr-4">{ms(a.avg_inference_ms)}</td>
                  <td className="pr-4">{pct(a.claim_support_rate, 1)}</td><td className="pr-4">{a.rougeL_f1 != null ? num(a.rougeL_f1, 3) : "no refs"}</td></tr>))}</tbody>
            </table>
          </div>
          <div>
            <h4 className="mb-2 font-serif text-lg">Runs</h4>
            <div className="max-h-72 overflow-auto scroll-thin rounded-xl border border-border">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="sticky top-0 bg-surface"><tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  {["Document", "Strategy", "Lang", "Words", "Compression", "Support"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
                <tbody>{(e.runs ?? []).map((r) => (
                  <tr key={r.id} className="border-b border-border/60 last:border-0"><td className="max-w-[220px] truncate px-3 py-2" title={r.title ?? ""}>{r.title || `#${r.id}`}</td>
                    <td className="px-3">{STRATEGY_LABEL[r.strategy]}</td><td className="px-3">{r.language_detected}</td><td className="px-3">{r.summary_words}</td>
                    <td className="px-3">{pct(r.compression_ratio, 1)}</td><td className="px-3">{r.verification_metrics ? `${r.verification_metrics.supported}/${r.verification_metrics.n_claims}` : "—"}</td></tr>))}</tbody>
              </table>
            </div>
          </div>
          <details className="text-xs text-muted"><summary className="cursor-pointer">Saved configuration</summary><pre className="mt-2 overflow-x-auto rounded-lg bg-sunken p-3 font-mono">{JSON.stringify({ language: e.language, strategies: e.strategies, length: e.length, model: e.model, ...e.config }, null, 2)}</pre></details>
          <div className="flex justify-end"><Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" />Delete experiment</Button></div>
          <ConfirmDialog open={confirm} onOpenChange={setConfirm} busy={busy} title="Delete this experiment?" description="The experiment and all of its runs will be permanently removed." onConfirm={del} />
        </div>
      )}
    </Dialog>
  );
}

const METRICS = [
  { key: "avg_compression_ratio", label: "Compression ratio", fmt: (v: number) => `${(v * 100).toFixed(1)}%` },
  { key: "avg_summary_words", label: "Summary words", fmt: (v: number) => v.toFixed(1) },
  { key: "avg_inference_ms", label: "Inference (ms)", fmt: (v: number) => v.toFixed(1) },
  { key: "claim_support_rate", label: "Claim-support rate", fmt: (v: number) => `${(v * 100).toFixed(1)}%` },
  { key: "rougeL_f1", label: "ROUGE-L F1", fmt: (v: number) => v.toFixed(3) },
] as const;

export default function ExperimentsPage() {
  const { backendDown } = useApp();
  const { toast } = useToast();
  const [items, setItems] = React.useState<Experiment[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [q, setQ] = React.useState(""); const [language, setLanguage] = React.useState(""); const [strategy, setStrategy] = React.useState(""); const [status, setStatus] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  const [openId, setOpenId] = React.useState<number | null>(null);
  const [sel, setSel] = React.useState<number[]>([]);
  const [metric, setMetric] = React.useState<(typeof METRICS)[number]["key"]>("avg_compression_ratio");

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try { setItems((await api.experiments({ q: q || undefined, language: language || undefined, strategy: strategy || undefined, status: status || undefined })).items); }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }, [q, language, strategy, status]);
  React.useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const toggle = (id: number) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length >= 4 ? s : [...s, id]));
  const chosen = items.filter((e) => sel.includes(e.id));
  const m = METRICS.find((x) => x.key === metric)!;
  const cmpRows = chosen.flatMap((e) => Object.entries(e.results.by_strategy ?? {}).map(([s, a]) => ({ exp: e, s, a })));
  const filters = !!(q || language || strategy || status);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-serif text-3xl tracking-tight">Experiments</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">Configure a run over a set of documents, store the configuration and results, and compare experiments side by side.</p>
        </div>
        <Button variant="primary" onClick={() => setCreating(true)} disabled={backendDown}><Plus className="h-4 w-4" />New experiment</Button>
      </div>

      <Card><CardContent className="grid gap-3 pt-5 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr]">
        <div className="relative"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" aria-hidden />
          <Input aria-label="Search experiments" className="pl-9" placeholder="Search name or notes…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Select aria-label="Language" value={language} onChange={(e) => setLanguage(e.target.value)}><option value="">All languages</option><option value="all">Mixed (all)</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hinglish</option></Select>
        <Select aria-label="Strategy" value={strategy} onChange={(e) => setStrategy(e.target.value)}><option value="">All strategies</option><option value="standard">Standard</option><option value="factuality">Factuality-aware</option></Select>
        <Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Any status</option><option value="completed">Completed</option><option value="failed">Failed</option></Select>
      </CardContent></Card>

      {error && <ErrorNote message={error} />}
      {loading && items.length === 0 && <div className="grid gap-4 md:grid-cols-2">{[0, 1].map((i) => <Skeleton key={i} className="h-36" />)}</div>}
      {!loading && !error && items.length === 0 && (filters
        ? <EmptyState icon={<Search className="h-6 w-6" />} title="No matching experiments" description="Try different filters." />
        : <EmptyState icon={<FlaskConical className="h-6 w-6" />} title="No experiments yet" description="Create your first experiment to compare standard and factuality-aware summarization across Hindi, English and Hinglish documents.">
            <Button variant="primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" />New experiment</Button></EmptyState>)}

      <div className="grid gap-4 md:grid-cols-2">
        {items.map((e) => (
          <Card key={e.id} className={sel.includes(e.id) ? "ring-2 ring-accent/40" : ""}>
            <CardHeader>
              <div className="min-w-0"><CardTitle className="truncate">{e.name}</CardTitle><CardDescription>{formatDate(e.created_at)}</CardDescription></div>
              <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted"><input type="checkbox" className="h-4 w-4 accent-[hsl(var(--accent))]" checked={sel.includes(e.id)} onChange={() => toggle(e.id)} aria-label={`Select ${e.name} for comparison`} />Compare</label>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                <Badge tone={e.status === "completed" ? "ok" : "bad"}>{e.status}</Badge><Badge>{LANG_LABEL[e.language]}</Badge>
                {e.strategies.map((s) => <Badge key={s} tone="accent">{STRATEGY_LABEL[s]}</Badge>)}{e.mode === "demo" && <Badge tone="warn">demo</Badge>}
              </div>
              <p className="text-sm text-muted">{e.results.n_runs ?? 0} runs · compression {pct(e.results.overall?.avg_compression_ratio, 1)} · support {pct(e.results.overall?.claim_support_rate, 0)}</p>
              {e.error && <p className="text-xs text-bad">{e.error}</p>}
              <Button size="sm" onClick={() => setOpenId(e.id)}>Open details</Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {chosen.length >= 2 ? (
        <Card>
          <CardHeader>
            <div><CardTitle>Comparison</CardTitle><CardDescription>{chosen.length} experiments selected</CardDescription></div>
            <Select aria-label="Metric" className="w-auto" value={metric} onChange={(e) => setMetric(e.target.value as typeof metric)}>{METRICS.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}</Select>
          </CardHeader>
          <CardContent className="space-y-5">
            <MetricBars label={`${m.label} by experiment`} data={chosen.map((e) => ({ name: e.name.slice(0, 18), ...Object.fromEntries(Object.entries(e.results.by_strategy ?? {}).map(([s, a]) => [s, (a[m.key as keyof typeof a] as number | null | undefined) ?? null])) }))}
              series={[{ key: "standard", name: "Standard" }, { key: "factuality", name: "Factuality-aware" }]} format={m.fmt} />
            <div className="overflow-x-auto scroll-thin"><table className="w-full min-w-[560px] text-sm">
              <thead><tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">{["Experiment", "Strategy", "Mode", "Runs", "Words", "Compression", "Inference", "Support", "ROUGE-L"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}</tr></thead>
              <tbody>{cmpRows.map(({ exp, s, a }) => (<tr key={`${exp.id}-${s}`} className="border-b border-border/60"><td className="py-2 pr-3 font-medium">{exp.name}</td><td className="pr-3">{STRATEGY_LABEL[s]}</td><td className="pr-3">{exp.mode}</td><td className="pr-3">{a.n_runs}</td>
                <td className="pr-3">{num(a.avg_summary_words, 0)}</td><td className="pr-3">{pct(a.avg_compression_ratio, 1)}</td><td className="pr-3">{ms(a.avg_inference_ms)}</td><td className="pr-3">{pct(a.claim_support_rate, 1)}</td><td className="pr-3">{a.rougeL_f1 != null ? num(a.rougeL_f1, 3) : "—"}</td></tr>))}</tbody></table></div>
            {new Set(chosen.map((e) => e.mode)).size > 1 && <InfoNote>You are comparing a demo (rule-based) experiment with a real-AI experiment; the numbers are not like-for-like.</InfoNote>}
          </CardContent>
        </Card>
      ) : sel.length === 1 ? (
        <p className="flex items-center gap-2 text-sm text-muted"><GitCompare className="h-4 w-4" />Select one more experiment to compare.</p>
      ) : null}

      <NewExperiment open={creating} onClose={() => setCreating(false)} onCreated={(e) => {
        setCreating(false); load(); setOpenId(e.id);
        toast(e.status === "completed" ? `Experiment finished: ${e.results.n_runs} runs` : "Experiment failed — see details", e.status === "completed" ? "ok" : "bad");
      }} />
      {openId !== null && <Detail id={openId} onClose={() => setOpenId(null)} onDeleted={(id) => { setOpenId(null); setSel((s) => s.filter((x) => x !== id)); load(); }} />}
    </div>
  );
}
