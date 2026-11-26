"use client";
import * as React from "react";
import { AlertTriangle, CheckCircle2, HelpCircle, Quote, XCircle } from "lucide-react";
import type { Claim, ClaimStatus, Verification } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { InfoNote } from "@/components/ui/empty-state";
import { cn, pct } from "@/lib/utils";

export const STATUS_META: Record<ClaimStatus, { label: string; tone: "ok" | "bad" | "warn"; icon: typeof CheckCircle2 }> = {
  supported: { label: "Supported", tone: "ok", icon: CheckCircle2 },
  contradicted: { label: "Contradicted", tone: "bad", icon: XCircle },
  unsupported: { label: "Unsupported", tone: "warn", icon: HelpCircle },
  uncertain: { label: "Uncertain", tone: "warn", icon: AlertTriangle },
  unverifiable: { label: "Unverifiable", tone: "warn", icon: HelpCircle },
};

export function StatusChip({ status }: { status: ClaimStatus }) {
  const m = STATUS_META[status];
  const Icon = m.icon;
  return <Badge tone={m.tone}><Icon className="h-3.5 w-3.5" aria-hidden />{m.label}</Badge>;
}

function ClaimRow({ c, index }: { c: Claim; index: number }) {
  const [open, setOpen] = React.useState(false);
  const hasPassages = (c.evidence_passages?.length ?? 0) > 0;
  return (
    <li className={cn("rounded-xl border bg-surface p-4",
      c.status === "supported" ? "border-border" : c.status === "contradicted" ? "border-bad/35" : "border-warn/35")}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-[15px] leading-relaxed"><span className="mr-2 text-xs text-muted">#{index + 1}</span>{c.claim}</p>
        <StatusChip status={c.status} />
      </div>
      {c.support_score !== undefined && <p className="mt-2 text-sm">Uncalibrated support score: <strong>{c.support_score.toFixed(1)}/100</strong> (maximum passage entailment × 100; not a probability)</p>}
      {c.contradiction_warning && <p className="mt-2 text-sm text-bad" role="status">Contradiction warning — review the evidence even when the support score is high.</p>}
      {c.conflicting_evidence && <p className="mt-2 text-sm text-warn">Conflicting source passages: both support and contradiction detected.</p>}
      {hasPassages && <div className="mt-3 space-y-3">
        {(c.evidence_passages??[]).map((p) => <div key={p.passage_id} className="rounded-lg bg-sunken p-3 text-sm">
          <p className="text-xs text-muted">Passage {p.passage_id + 1} · {p.page === null ? "Page unavailable (pasted text)" : `Page ${p.page}`} · characters {p.start}–{p.end}</p>
          <blockquote className="mt-1 whitespace-pre-wrap">{p.text}</blockquote>
          <dl className="mt-2 flex flex-wrap gap-3 text-xs">
            <div><dt className="inline">Entailment </dt><dd className="inline">{p.nli?.entailment!= null ? pct(p.nli?.entailment) : "-"}</dd></div>
            <div><dt className="inline">Contradiction </dt><dd className="inline">{p.nli?.contradiction != null ? pct(p.nli?.contradiction) : "-"}</dd></div>
            <div><dt className="inline">Neutral </dt><dd className="inline">{p.nli?.neutral != null ? pct(p.nli?.neutral) : "-"}</dd></div>
          </dl>
          <p className="mt-1 text-xs text-muted">Retrieval similarity: {(p.retrieval_similarity ?? 0).toFixed(3)} (relevance only)</p>
          <ul className="mt-2 space-y-1">{p.checks.filter((k) => !["match", "not_applicable"].includes(k.outcome ?? "")).map((k) => <li key={k.name} className="text-xs text-warn">{k.name} · {k.outcome}: {k.detail}</li>)}</ul>
        </div>)}
      </div>}
      {!hasPassages && (c.evidence ? (
        <blockquote className="mt-3 flex gap-2 rounded-lg bg-sunken px-3 py-2.5 text-sm leading-relaxed">
          <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
          <span><span className="mb-0.5 block text-[11px] font-medium uppercase tracking-wide text-muted">Source evidence</span>{c.evidence}</span>
        </blockquote>
      ) : (
        <p className="mt-3 rounded-lg bg-sunken px-3 py-2 text-sm text-muted">No supporting passage was found in the source.</p>
      ))}
      <p className="mt-2.5 text-sm text-muted">{c.explanation}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
        {c.confidence !== null && c.confidence !== undefined ? <Badge>confidence {pct(c.confidence)}</Badge> : null}
        {c.evidence_score !== undefined && (
          <span title="Share of the claim's content terms found in the best source passage. A lexical match score, not a probability.">
            lexical match {pct(c.evidence_score)}
          </span>
        )}
        {c.disagreement && <Badge tone="warn"><AlertTriangle className="h-3 w-3" />rule check overrode LLM</Badge>}
        {c.checks && c.checks.length > 0 && (
          <button type="button" onClick={() => setOpen((o) => !o)} className="underline-offset-2 hover:underline" aria-expanded={open}>
            {open ? "Hide checks" : "Show checks"}
          </button>
        )}
      </div>
      {open && c.checks && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {c.checks.map((k) => (
            <li key={k.name}><Badge tone={k.outcome === "not_applicable" ? "neutral" : k.passed ? "ok" : "warn"} title={k.detail}>{k.name}: {k.detail}</Badge></li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function VerificationView({ v, filter }: { v: Verification; filter?: ClaimStatus | "all" }) {
  const m = v.metrics;
  const claims = v.claims.filter((c) => !filter || filter === "all" || c.status === filter);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={v.is_ai_verification ? "accent" : "warn"}>{v.method_label}</Badge>
        <Badge tone="ok">{m.supported} supported</Badge>
        <Badge tone="bad">{m.contradicted} contradicted</Badge>
        {v.method === "claim_nli" ? <><Badge tone="warn">{m.unsupported ?? 0} unsupported</Badge><Badge tone="warn">{m.uncertain ?? 0} uncertain</Badge></> : <Badge tone="warn">{m.unverifiable} unverifiable</Badge>}
        {m.mean_claim_score !== undefined && <span className="text-sm">Mean claim score: {m.mean_claim_score?.toFixed(1) ?? "—"}/100 (uncalibrated)</span>}
        <span className="ml-auto text-sm text-muted" title={m.formula}>
          Claim-support rate <strong className="text-fg">{pct(m.support_rate)}</strong> <span className="text-xs">({m.supported}/{m.n_claims})</span>
        </span>
      </div>
      {!v.is_ai_verification && (
        <InfoNote>
          This result comes from a <strong>rule-based heuristic</strong> (lexical overlap plus checks for numbers, dates, entities and negation).
          It is not AI verification. Configure an API key in Settings for LLM-based verification.
        </InfoNote>
      )}
      {m.n_claims === 0 ? (
        <p className="text-sm text-muted">No verifiable claims were found in the summary.</p>
      ) : (
        <ol className="space-y-3">{claims.map((c, i) => <ClaimRow key={`${i}-${c.claim}`} c={c} index={v.claims.indexOf(c)} />)}</ol>
      )}
      <p className="text-xs leading-relaxed text-muted">{v.limitations}</p>
    </div>
  );
}
