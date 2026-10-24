"use client";
import * as React from "react";
import { Check, Copy, Download, Save, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/components/app-provider";
import type { Run } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ErrorNote, InfoNote, Stat } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { download, LANG_SHORT, ms, num, pct, STRATEGY_LABEL, cn } from "@/lib/utils";
import { FactsView } from "./facts-view";
import { StatusChip, VerificationView } from "./verification-view";

export function ModeChip({ run }: { run: Run }) {
  return run.mode === "demo"
    ? <Badge tone="warn" title="Rule-based extractive summary. Not produced by an AI model.">Demo · rule-based extractive</Badge>
    : <Badge tone="ok">AI · {run.model}</Badge>;
}

export function SummaryCard({ run, onChange, compact }: { run: Run; onChange: (r: Run) => void; compact?: boolean }) {
  const { toast } = useToast();
  const { settings } = useApp();
  const [tab, setTab] = React.useState<"facts" | "verify">(run.verification ? "verify" : "facts");
  const [verifyMethod, setVerifyMethod] = React.useState<"auto" | "claim_nli">("auto");
  const [verifying, setVerifying] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(run.summary);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch { toast("Copy failed. Select the text and copy it manually.", "bad"); }
  };
  const save = async () => {
    setSaving(true);
    try { onChange({ ...run, ...(await api.saveRun(run.id)), verification: run.verification }); toast("Saved to history"); }
    catch (e) { toast((e as Error).message, "bad"); } finally { setSaving(false); }
  };
  const verify = async () => {
    setVerifying(true); setError(null);
    if ((verifyMethod === "claim_nli" || (verifyMethod === "auto" && settings?.preferences.verifier === "claim_nli")) && !window.confirm("Extract claims with Groq? This uses one API request. Retrieval and NLI run locally.")) { setVerifying(false); return; }
    try {
      const v = await api.verify({ source: run.source_text ?? "", summary: run.summary, run_id: run.id, method: verifyMethod });
      onChange({ ...run, verification: v, verification_metrics: v.metrics, verification_method: v.method });
      setTab("verify");
    } catch (e) { setError((e as Error).message); } finally { setVerifying(false); }
  };

  const vm = run.verification?.metrics;
  const bad = run.verification?.claims.filter((c) => c.status !== "supported") ?? [];
  const lang = LANG_SHORT[run.language_detected] ?? run.language_detected;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="flex-wrap">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="accent">{STRATEGY_LABEL[run.strategy]}</Badge>
          <ModeChip run={run} />
          <Badge>{lang}</Badge>
          {vm && <StatusChip status={vm.contradicted ? "contradicted" : vm.uncertain ? "uncertain" : vm.unsupported ? "unsupported" : vm.unverifiable ? "unverifiable" : "supported"} />}
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-5">
        <p className="prose-summary whitespace-pre-wrap" lang={run.language_detected === "en" ? "en" : "hi"}>{run.summary}</p>

        {run.extra?.warnings?.map((w) => <InfoNote key={w}>{w}</InfoNote>)}
        {run.extra?.engine_note && run.mode === "demo" && <p className="text-xs leading-relaxed text-muted">{run.extra.engine_note}</p>}
        {run.extra?.chunks && run.extra.chunks > 1 && <p className="text-xs text-muted">Long document: summarized in {run.extra.chunks} chunks and merged.</p>}

        <div className={cn("grid gap-3", compact ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4")}>
          <Stat label="Inference" value={ms(run.inference_ms)} />
          <Stat label="Words" value={<>{run.source_words} <span className="text-base text-muted">→ {run.summary_words}</span></>} />
          <Stat label="Compression" value={pct(run.compression_ratio)} sub={run.compression_factor ? `${num(run.compression_factor)}× shorter` : undefined} hint="Summary words ÷ source words" />
          <Stat label="Code-mixing (CMI)" value={num(run.cmi)} hint="Code-Mixing Index: 0 = monolingual, up to 50 = evenly mixed" />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={copy}>{copied ? <Check className="h-4 w-4 text-ok" /> : <Copy className="h-4 w-4" />}{copied ? "Copied" : "Copy"}</Button>
          <Button size="sm" onClick={() => download(`FactAlign-summary-${run.id}.txt`, `${run.summary}\n`)}><Download className="h-4 w-4" />Download TXT</Button>
          {!run.saved && <Button size="sm" onClick={save} loading={saving}><Save className="h-4 w-4" />Save to history</Button>}
          {run.saved && <Badge tone="ok" className="self-center"><Check className="h-3 w-3" />Saved</Badge>}
          <label className="self-center text-xs">Verifier <select aria-label="Summary verifier" value={verifyMethod} onChange={(e) => setVerifyMethod(e.target.value as "auto" | "claim_nli")} className="rounded border border-border bg-surface p-1"><option value="auto">Configured default</option><option value="claim_nli">Claim-level NLI</option></select></label>
          <Button size="sm" variant="subtle" onClick={verify} loading={verifying}><ShieldCheck className="h-4 w-4" />{run.verification ? "Re-run verification" : "Run factuality verification"}</Button>
        </div>
        {error && <ErrorNote message={error} />}

        {!run.verification && run.metrics && run.metrics.fact.unsupported_facts.length > 0 && (
          <InfoNote>
            Numbers/dates/entities in this summary that do not appear in the source: <strong>{run.metrics.fact.unsupported_facts.join(", ")}</strong>.
            Run verification for a claim-by-claim check.
          </InfoNote>
        )}

        <div>
          <div role="tablist" className="mb-4 flex gap-1 border-b border-border">
            {([["facts", "Facts & entities"], ["verify", `Verification${vm ? ` (${vm.n_claims})` : ""}`]] as const).map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                className={cn("-mb-px border-b-2 px-3 py-2 text-sm transition-colors", tab === k ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg")}>
                {label}
              </button>
            ))}
          </div>
          {tab === "facts" ? <FactsView run={run} /> : run.verification ? (
            <div className="space-y-4">
              {bad.length > 0 && <InfoNote tone="warn"><strong>{bad.length} potentially unsupported claim{bad.length > 1 ? "s" : ""}</strong> — review the evidence below.</InfoNote>}
              <VerificationView v={run.verification} />
            </div>
          ) : (
            <p className="text-sm text-muted">Verification has not been run for this summary yet. Use “Run factuality verification”.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
