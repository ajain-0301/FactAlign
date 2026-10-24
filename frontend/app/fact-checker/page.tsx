"use client";
import * as React from "react";
import { ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/components/app-provider";
import type { ClaimStatus, SamplesResponse, Verification, VerifyMethod, SourcePage } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNote } from "@/components/ui/empty-state";
import { Field, Segmented, Select, Textarea } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import { VerificationView } from "@/components/features/verification-view";
import { countWords } from "@/lib/utils";

const EXAMPLES = {
  en: { id: "air-en", summary: "The corporation will install 60 monitoring stations. The plan will cost 250 crore rupees. The plan includes a ban on private cars. The plan was approved by the state government. The plan will be completed by December 2026." },
  hinglish: { id: "air-hinglish", summary: "Plan पर 250 crore rupees खर्च होंगे। Plan December 2025 तक complete होगा। Plan में private cars पर ban शामिल है। Plan को state government ने approve कर दिया है।" },
  hi: { id: "air-hi", summary: "योजना पर 250 करोड़ रुपये खर्च होंगे। योजना दिसंबर 2025 तक पूरी होगी। योजना में निजी कारों पर प्रतिबंध शामिल है। योजना को राज्य सरकार ने मंज़ूरी दे दी है।" },
} as const;

export default function FactCheckerPage() {
  const { settings, backendDown } = useApp();
  const [source, setSource] = React.useState("");
  const [sourcePages, setSourcePages] = React.useState<SourcePage[] | undefined>();
  const [uploading, setUploading] = React.useState(false);
  const [summary, setSummary] = React.useState("");
  const [method, setMethod] = React.useState<VerifyMethod>("auto");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<Verification | null>(null);
  const [filter, setFilter] = React.useState<ClaimStatus | "all">("all");
  const [samples, setSamples] = React.useState<SamplesResponse | null>(null);
  React.useEffect(() => { api.samples().then(setSamples).catch(() => undefined); }, []);

  const loadExample = (k: keyof typeof EXAMPLES) => {
    const it = samples?.items.find((i) => i.id === EXAMPLES[k].id);
    if (!it) return;
    setSourcePages(undefined); setSource(it.source); setSummary(EXAMPLES[k].summary); setResult(null); setError(null);
  };
  const run = async () => {
    if ((method === "claim_nli" || (method === "auto" && settings?.preferences.verifier === "claim_nli")) && !window.confirm("Extract claims with Groq? This uses one API request. Retrieval and NLI run locally.")) return;
    setLoading(true); setError(null); setResult(null);
    try { setResult(await api.verify({ source, summary, method, source_pages: sourcePages })); setFilter("all"); }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  };
  const ready = source.trim().length > 0 && summary.trim().length > 0;
  const real = settings?.effective_mode === "real";

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-serif text-3xl tracking-tight">Check a summary against its source.</h2>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">
          Paste any source document and any summary — yours, or one from another tool. Each claim is matched to evidence and labelled
          Supported, Contradicted, Unsupported or Uncertain with the claim-level NLI method.
        </p>
      </div>
      <Card>
        <CardContent className="space-y-5 pt-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-medium">Load an example with planted errors</span>
            <Button size="sm" onClick={() => loadExample("en")} disabled={!samples}>English</Button>
            <Button size="sm" onClick={() => loadExample("hi")} disabled={!samples}>Hindi</Button>
            <Button size="sm" onClick={() => loadExample("hinglish")} disabled={!samples}>Hinglish</Button>
          </div>
          <label className="block text-sm">Upload source (PDF page references are preserved)
            <input className="mt-2 block text-sm" type="file" accept=".pdf,.txt,.md,.docx" disabled={uploading} onChange={async (e) => {
              const file = e.target.files?.[0]; if (!file) return;
              setUploading(true); setError(null); setResult(null);
              try { const doc = await api.extract(file); setSource(doc.text); setSourcePages(doc.pages ?? undefined); }
              catch (err) { setError((err as Error).message); } finally { setUploading(false); e.target.value = ""; }
            }} />
          </label>
          <div className="grid gap-5 lg:grid-cols-2">
            <Field label="Source document" hint={`${countWords(source)} words`}>
              <Textarea value={source} onChange={(e) => { setSource(e.target.value); setSourcePages(undefined); }} className="min-h-[220px]" placeholder="The original document…" />
            </Field>
            <Field label="Summary to verify" hint={`${countWords(summary)} words`}>
              <Textarea value={summary} onChange={(e) => setSummary(e.target.value)} className="min-h-[220px]" placeholder="The summary whose claims should be checked…" />
            </Field>
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <Field label="Verification method" className="w-full sm:w-72" hint={real ? "Auto uses LLM + rule checks (hybrid)." : "Auto uses the offline rule-based heuristic."}>
              <Select value={method} onChange={(e) => setMethod(e.target.value as VerifyMethod)}>
                <option value="auto">Auto</option><option value="rule">Rule-based (offline)</option>
                <option value="llm" disabled={!settings?.api_key_configured}>LLM judge (needs API key)</option>
                <option value="claim_nli" disabled={!settings?.api_key_configured}>Claim-level NLI (Groq + local models)</option>
                <option value="hybrid" disabled={!settings?.api_key_configured}>Hybrid (needs API key)</option>
              </Select>
            </Field>
            <Button variant="primary" size="lg" onClick={run} loading={loading} disabled={!ready || backendDown || uploading}><ShieldCheck className="h-4 w-4" />Verify claims</Button>
          </div>
        </CardContent>
      </Card>

      {error && <ErrorNote message={error} />}
      {loading && <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-24" /></div>}
      {result && (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Claim-by-claim results</CardTitle>
              <CardDescription>{result.metrics.n_claims} claims checked in {result.verify_ms ?? "—"} ms</CardDescription>
            </div>
            <Segmented label="Filter" value={filter} onChange={setFilter} options={[
              { value: "all", label: "All" }, { value: "supported", label: "Supported" }, { value: "contradicted", label: "Contradicted" }, { value: "unsupported", label: "Unsupported" }, { value: "uncertain", label: "Uncertain" }, { value: "unverifiable", label: "Legacy unverifiable" }]} />
          </CardHeader>
          <CardContent><VerificationView v={result} filter={filter} /></CardContent>
        </Card>
      )}
      {!result && !loading && !error && (
        <EmptyState icon={<ShieldCheck className="h-6 w-6" />} title="No verification yet"
          description="Add a source and a summary, or load an example. You'll see each claim with its evidence passage and an explanation." />
      )}
    </div>
  );
}
