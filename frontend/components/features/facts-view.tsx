import type { Analysis, Run } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

function Chips({ title, items, tone }: { title: string; items: string[]; tone?: "accent" | "neutral" | "warn" }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{title} <span className="normal-case">({items.length})</span></div>
      {items.length ? (
        <div className="flex flex-wrap gap-1.5">{items.slice(0, 40).map((x, i) => <Badge key={`${x}-${i}`} tone={tone ?? "neutral"}>{x}</Badge>)}</div>
      ) : <p className="text-sm text-muted">None detected</p>}
    </div>
  );
}

export function FactsView({ run }: { run: Run }) {
  const a: Analysis | undefined = run.analysis;
  if (!a) return null;
  const unsupported = run.metrics?.fact.unsupported_facts ?? [];
  return (
    <div className="space-y-5">
      <div>
        <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">Key facts in the source</div>
        {a.key_facts.length ? (
          <ul className="space-y-2">
            {a.key_facts.map((f, i) => <li key={i} className="rounded-lg bg-sunken px-3 py-2 text-sm leading-relaxed">{f}</li>)}
          </ul>
        ) : <p className="text-sm text-muted">No fact-dense sentences detected.</p>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Chips title="Important entities" items={a.entities} tone="accent" />
        <Chips title="Dates" items={a.dates} />
        <Chips title="Numbers" items={a.numbers} />
        <Chips title="In summary but not in source" items={unsupported} tone="warn" />
      </div>
      <p className="text-xs text-muted">
        Entities are detected heuristically (capitalised Latin names and a small Hindi gazetteer) and will miss some Devanagari names.
      </p>
    </div>
  );
}
