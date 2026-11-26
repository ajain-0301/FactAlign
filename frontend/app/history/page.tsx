"use client";
import * as React from "react";
import Link from "next/link";
import { Download, History as HistoryIcon, Search, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorNote } from "@/components/ui/empty-state";
import { Input, Select } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { SummaryCard } from "@/components/features/summary-card";
import { formatDate, LANG_SHORT, STRATEGY_LABEL } from "@/lib/utils";

const PAGE = 20;

export default function HistoryPage() {
  const { toast } = useToast();
  const [q, setQ] = React.useState("");
  const [language, setLanguage] = React.useState("");
  const [strategy, setStrategy] = React.useState("");
  const [from, setFrom] = React.useState("");
  const [to, setTo] = React.useState("");
  const [items, setItems] = React.useState<Run[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState<Run | null>(null);
  const [opening, setOpening] = React.useState(false);
  const [del, setDel] = React.useState<Run | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const params = React.useMemo(() => ({ q: q || undefined, language: language || undefined, strategy: strategy || undefined, date_from: from || undefined, date_to: to || undefined }), [q, language, strategy, from, to]);

  const load = React.useCallback(async (offset = 0, append = false) => {
    setLoading(true); setError(null);
    try {
      const r = await api.history({ ...params, limit: PAGE, offset });
      setItems((cur) => (append ? [...cur, ...r.items] : r.items)); setTotal(r.total);
    } catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }, [params]);

  React.useEffect(() => { const t = setTimeout(() => load(0), 250); return () => clearTimeout(t); }, [load]);

  const openRun = async (r: Run) => {
    setOpening(true);
    try { setOpen(await api.run(r.id)); } catch (e) { toast((e as Error).message, "bad"); } finally { setOpening(false); }
  };
  const confirmDelete = async () => {
    if (!del) return;
    setDeleting(true);
    try {
      await api.deleteRun(del.id);
      setItems((s) => s.filter((x) => x.id !== del.id)); setTotal((t) => t - 1);
      if (open?.id === del.id) setOpen(null);
      toast("Deleted from history"); setDel(null);
    } catch (e) { toast((e as Error).message, "bad"); } finally { setDeleting(false); }
  };
  const exportParams = { q: q || undefined, language: language || undefined, strategy: strategy || undefined, date_from: from || undefined, date_to: to || undefined } as Record<string, string | undefined>;
  const filtersActive = !!(q || language || strategy || from || to);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-serif text-3xl tracking-tight">History</h2>
          <p className="mt-1 text-sm text-muted">Every summary you saved, stored locally in SQLite.</p>
        </div>
        <div className="flex gap-2">
          <a href={api.historyExportUrl("csv", exportParams)} download><Button size="sm" tabIndex={-1}><Download className="h-4 w-4" />CSV</Button></a>
          <a href={api.historyExportUrl("json", exportParams)} download><Button size="sm" tabIndex={-1}><Download className="h-4 w-4" />JSON</Button></a>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-3 pt-5 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_1fr]">
          <div className="relative sm:col-span-2 lg:col-span-1">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" aria-hidden />
            <Input aria-label="Search history" className="pl-9" placeholder="Search title, source or summary…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Select aria-label="Language" value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="">All languages</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hinglish</option>
          </Select>
          <Select aria-label="Strategy" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            <option value="">All strategies</option><option value="standard">Standard</option><option value="factuality">Factuality-aware</option>
          </Select>
          <Input type="date" aria-label="From date" value={from} onChange={(e) => setFrom(e.target.value)} />
          <Input type="date" aria-label="To date" value={to} onChange={(e) => setTo(e.target.value)} />
        </CardContent>
      </Card>

      {error && <ErrorNote message={error} />}
      {loading && items.length === 0 && <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div>}

      {!loading && !error && items.length === 0 && (
        filtersActive
          ? <EmptyState icon={<Search className="h-6 w-6" />} title="No matches" description="No saved summaries match these filters." >
              <Button onClick={() => { setQ(""); setLanguage(""); setStrategy(""); setFrom(""); setTo(""); }}>Clear filters</Button></EmptyState>
          : <EmptyState icon={<HistoryIcon className="h-6 w-6" />} title="Nothing saved yet" description="Summaries you generate are saved here (change this in Settings → Auto-save)." >
              <Link href="/"><Button variant="primary">Write a summary</Button></Link></EmptyState>
      )}

      <ul className="space-y-3">
        {items.map((r) => (
          <li key={r.id}>
            <Card className="transition-shadow hover:shadow-pop">
              <CardContent className="flex flex-col gap-3 pt-4 sm:flex-row sm:items-start">
                <button type="button" onClick={() => openRun(r)} className="min-w-0 flex-1 rounded-lg text-left" aria-label={`Open ${r.title || "summary"} ${r.id}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{r.title || `Untitled · #${r.id}`}</span>
                    <Badge tone="accent">{STRATEGY_LABEL[r.strategy]}</Badge>
                    <Badge>{LANG_SHORT[r.language_detected]}</Badge>
                    {r.mode === "demo" ? <Badge tone="warn">demo</Badge> : <Badge tone="ok">AI</Badge>}
                    {r.verification_metrics && <Badge tone={r.verification_metrics.contradicted ? "bad" : r.verification_metrics.unverifiable ? "warn" : "ok"}>
                      {r.verification_metrics.supported}/{r.verification_metrics.n_claims} claims supported</Badge>}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted">{r.summary}</p>
                  <p className="mt-1.5 text-xs text-muted">{formatDate(r.created_at)} · {r.source_words} → {r.summary_words} words</p>
                </button>
                <Button size="icon" variant="ghost" aria-label={`Delete ${r.title || "summary"} ${r.id}`} onClick={() => setDel(r)}><Trash2 className="h-4 w-4" /></Button>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
      {items.length < total && <div className="flex justify-center"><Button onClick={() => load(items.length, true)} loading={loading}>Load more</Button></div>}
      {opening && <p className="text-center text-sm text-muted" role="status">Opening…</p>}

      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)} wide title={open?.title || `Summary #${open?.id ?? ""}`} description={open ? `${formatDate(open.created_at)} · ${open.model}` : undefined}>
        {open && (
          <div className="space-y-5">
            <SummaryCard run={open} onChange={setOpen} />
            <Card>
              <CardContent className="pt-5">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Source document</div>
                <p className="max-h-72 overflow-y-auto scroll-thin whitespace-pre-wrap text-[15px] leading-relaxed">{open.source_text}</p>
              </CardContent>
            </Card>
            {open.reference_summary && (
              <Card><CardContent className="pt-5">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Reference summary</div>
                <p className="text-[15px] leading-relaxed">{open.reference_summary}</p>
                {open.metrics?.rouge && <p className="mt-3 text-sm text-muted">ROUGE-1 {open.metrics.rouge.rouge1.f1} · ROUGE-2 {open.metrics.rouge.rouge2.f1} · ROUGE-L {open.metrics.rouge.rougeL.f1} (F1)</p>}
              </CardContent></Card>
            )}
            <div className="flex justify-end"><Button variant="danger" onClick={() => setDel(open)}><Trash2 className="h-4 w-4" />Delete</Button></div>
          </div>
        )}
      </Dialog>
      <ConfirmDialog open={!!del} onOpenChange={(o) => !o && setDel(null)} title="Delete this summary?" busy={deleting}
        description="The source, summary and any verification results will be permanently removed from the local database." onConfirm={confirmDelete} />
    </div>
  );
}
