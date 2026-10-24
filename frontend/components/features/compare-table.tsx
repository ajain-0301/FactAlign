import type { Run } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ms, num, pct, STRATEGY_LABEL } from "@/lib/utils";

export function CompareTable({ runs }: { runs: Run[] }) {
  const rows: { label: string; hint?: string; get: (r: Run) => string }[] = [
    { label: "Summary words", get: (r) => String(r.summary_words) },
    { label: "Compression (summary ÷ source)", get: (r) => pct(r.compression_ratio, 1) },
    { label: "Inference time", get: (r) => ms(r.inference_ms) },
    { label: "Numbers/dates/entities not in source", hint: "Automatic proxy", get: (r) => String(r.metrics?.fact.unsupported_facts.length ?? "—") },
    { label: "Fact precision (proxy)", get: (r) => pct(r.metrics?.fact.fact_precision) },
    { label: "Claim-support rate", hint: "Needs verification", get: (r) => (r.verification ? pct(r.verification.metrics.support_rate) : "not verified") },
    { label: "Contradicted / unverifiable claims", get: (r) => (r.verification ? `${r.verification.metrics.contradicted} / ${r.verification.metrics.unverifiable}` : "not verified") },
    { label: "ROUGE-L F1 (needs reference)", get: (r) => (r.metrics?.rouge ? num(r.metrics.rouge.rougeL.f1, 3) : "no reference") },
  ];
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Strategy comparison</CardTitle>
          <CardDescription>Measured on this document only. One document is an anecdote, not an experiment — use Experiments or Evaluation for aggregate results.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="overflow-x-auto scroll-thin">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <th className="py-2 pr-4 font-medium">Metric</th>
              {runs.map((r) => <th key={r.id} className="py-2 pr-4 font-medium">{STRATEGY_LABEL[r.strategy]}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-border/60 last:border-0">
                <td className="py-2.5 pr-4 text-muted" title={row.hint}>{row.label}</td>
                {runs.map((r) => <td key={r.id} className="py-2.5 pr-4 font-medium">{row.get(r)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
