"use client";
import * as React from "react";
import { FileUp, Eraser, Sparkles, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/components/app-provider";
import type { Language, Length, OutputLanguage, Run, SampleItem, SamplesResponse, Strategy } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorNote, InfoNote } from "@/components/ui/empty-state";
import { Field, Input, Segmented, Select, Textarea } from "@/components/ui/form";
import { SummarySkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { SummaryCard } from "@/components/features/summary-card";
import { CompareTable } from "@/components/features/compare-table";
import { countWords, LANG_SHORT } from "@/lib/utils";

type StrategyChoice = Strategy | "compare";
const ACCEPT = ".txt,.md,.pdf,.docx";

export default function SummarizePage() {
  const { settings, backendDown } = useApp();
  const { toast } = useToast();
  const fileRef = React.useRef<HTMLInputElement>(null);

  const [title, setTitle] = React.useState("");
  const [sourcePages, setSourcePages] = React.useState<import("@/lib/types").SourcePage[] | undefined>();
  const [text, setText] = React.useState("");
  const [reference, setReference] = React.useState("");
  const [language, setLanguage] = React.useState<Language>("auto");
  const [outLang, setOutLang] = React.useState<OutputLanguage>("same");
  const [length, setLength] = React.useState<Length>("medium");
  const [strategy, setStrategy] = React.useState<StrategyChoice>("factuality");
  const [loading, setLoading] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [results, setResults] = React.useState<Run[]>([]);
  const [wasCompare, setWasCompare] = React.useState(false);
  const [samples, setSamples] = React.useState<SamplesResponse | null>(null);
  const [applied, setApplied] = React.useState(false);

  React.useEffect(() => { api.samples().then(setSamples).catch(() => undefined); }, []);
  React.useEffect(() => {
    if (settings && !applied) {
      const p = settings.preferences;
      setLanguage(p.default_language); setOutLang(p.default_output_language); setLength(p.default_length); setStrategy(p.default_strategy);
      setApplied(true);
    }
  }, [settings, applied]);

  const words = countWords(text);
  const maxChars = settings?.limits.max_input_chars ?? 60000;
  const problem = !text.trim() ? "Paste or upload a document to summarize."
    : words < 3 ? "The text is too short to summarize (at least 3 words)."
    : text.length > maxChars ? `The document has ${text.length.toLocaleString()} characters; the limit is ${maxChars.toLocaleString()}.` : null;

  const submit = async () => {
    if (problem || loading) return;
    setLoading(true); setError(null); setResults([]);
    const body = { text, source_pages: sourcePages, title: title.trim() || undefined, language, output_language: outLang, length,
      strategy: strategy === "compare" ? ("factuality" as Strategy) : strategy, reference_summary: reference.trim() || undefined };
    try {
      if (strategy === "compare") { const r = await api.compare(body); setResults(r.results); setWasCompare(true); }
      else { setResults([await api.summarize(body)]); setWasCompare(false); }
    } catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  };

  const load = (s: { text: string; language: string; title: string; reference?: string }) => {
    setSourcePages(undefined); setText(s.text); setTitle(s.title); setReference(s.reference ?? ""); setLanguage("auto"); setResults([]); setError(null);
  };
  const quick = (lang: "hi" | "en" | "hinglish") => {
    const it = samples?.items.find((i) => i.language === lang && i.pair_id === "air");
    if (it) load({ text: it.source, language: it.language, title: it.title, reference: it.reference_summary });
  };
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    const maxMb = settings?.limits.max_upload_mb ?? 5;
    if (f.size > maxMb * 1024 * 1024) { setError(`"${f.name}" is larger than the ${maxMb} MB limit.`); return; }
    setUploading(true); setError(null);
    try {
      const r = await api.extract(f);
      setSourcePages(r.pages ?? undefined); setText(r.text); setTitle((t) => t || f.name.replace(/\.[^.]+$/, "")); setResults([]);
      toast(`Loaded ${f.name} (${r.words.toLocaleString()} words)`);
    } catch (e) { setError((e as Error).message); } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const updateRun = (r: Run) => setResults((rs) => rs.map((x) => (x.id === r.id ? r : x)));

  const verifyBoth = async () => {
    if (settings?.preferences.verifier === "claim_nli" && !window.confirm(`Extract claims with Groq for ${results.length} summaries? This may use up to ${results.length * 2} API requests (at most one retry per summary if the output or quotes are invalid). Retrieval and NLI run locally.`)) return;
    setLoading(true); setError(null);
    try {
      const next = await Promise.all(results.map(async (r) => {
        const v = await api.verify({ source: r.source_text ?? "", summary: r.summary, run_id: r.id });
        return { ...r, verification: v, verification_metrics: v.metrics, verification_method: v.method } as Run;
      }));
      setResults(next);
    } catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-serif text-3xl tracking-tight sm:text-4xl">Summarize with facts intact.</h2>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">
          Paste Hindi, English or Hinglish text. FactAlign compares a standard summary with a factuality-aware one and checks every claim against your source.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-5 pt-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 text-[13px] font-medium">Try a sample</span>
            <Button size="sm" onClick={() => quick("hi")} disabled={!samples}>Hindi</Button>
            <Button size="sm" onClick={() => quick("en")} disabled={!samples}>English</Button>
            <Button size="sm" onClick={() => quick("hinglish")} disabled={!samples}>Hinglish</Button>
            <Select aria-label="More samples" className="h-8 w-auto max-w-[220px] text-[13px]" value="" disabled={!samples}
              onChange={(e) => {
                const v = e.target.value; if (!v) return;
                const it = samples?.items.find((i) => i.id === v) as SampleItem | undefined;
                if (it) load({ text: it.source, language: it.language, title: it.title, reference: it.reference_summary });
                const ex = samples?.assignment_examples.find((i) => i.id === v);
                if (ex) load({ text: ex.text, language: ex.language, title: ex.title });
              }}>
              <option value="">More samples…</option>
              {samples?.items.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
              {samples?.assignment_examples.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
            </Select>
            <div className="ml-auto flex gap-2">
              <input ref={fileRef} type="file" accept={ACCEPT} className="sr-only" aria-label="Upload a document" onChange={(e) => onFile(e.target.files?.[0])} />
              <Button size="sm" onClick={() => fileRef.current?.click()} loading={uploading}><FileUp className="h-4 w-4" />Upload</Button>
              <Button size="sm" variant="ghost" onClick={() => { setText(""); setSourcePages(undefined); setTitle(""); setReference(""); setResults([]); setError(null); }} disabled={!text && !title}>
                <Eraser className="h-4 w-4" />Clear
              </Button>
            </div>
          </div>
          {samples && <p className="-mt-2 text-xs text-muted">{samples.note}</p>}

          <Field label="Document title (optional)">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} placeholder="e.g. City air-quality report" />
          </Field>
          <div>
            <Textarea value={text} onChange={(e) => { setText(e.target.value); setSourcePages(undefined); }} placeholder="Paste or type your document here — Hindi, English, or Hinglish…"
              aria-label="Document text" className="min-h-[240px] text-[15px]" onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") submit(); }} />
            <div className="mt-1.5 flex flex-wrap justify-between gap-2 text-xs text-muted">
              <span>{words.toLocaleString()} words · {text.length.toLocaleString()} characters</span>
              <span className={text.length > maxChars ? "text-bad" : ""}>Limit {maxChars.toLocaleString()} characters · TXT, MD, PDF, DOCX up to {settings?.limits.max_upload_mb ?? 5} MB</span>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Language">
              <Select value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
                <option value="auto">Auto-detect</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hindi-English code-mixed</option>
              </Select>
            </Field>
            <Field label="Output language" hint="Real AI mode only; demo mode keeps the source language.">
              <Select value={outLang} onChange={(e) => setOutLang(e.target.value as OutputLanguage)}>
                <option value="same">Same as source</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hinglish</option>
              </Select>
            </Field>
            <div className="space-y-1.5">
              <span className="text-[13px] font-medium">Summary length</span>
              <div><Segmented label="Summary length" value={length} onChange={setLength} options={[{ value: "short", label: "Short" }, { value: "medium", label: "Medium" }, { value: "long", label: "Long" }]} /></div>
            </div>
            <div className="space-y-1.5">
              <span className="text-[13px] font-medium">Strategy</span>
              <div><Segmented label="Strategy" value={strategy} onChange={setStrategy} options={[{ value: "standard", label: "Standard" }, { value: "factuality", label: "Factuality-aware" }, { value: "compare", label: "Compare both" }]} /></div>
            </div>
          </div>

          <details className="group rounded-xl border border-border px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium">Reference summary (optional) <span className="font-normal text-muted">— enables ROUGE and fact recall</span></summary>
            <Textarea value={reference} onChange={(e) => setReference(e.target.value)} className="mt-3 min-h-[90px]" aria-label="Reference summary" placeholder="A human-written summary of this document" />
          </details>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" size="lg" onClick={submit} loading={loading} disabled={!!problem || backendDown}>
              <Sparkles className="h-4 w-4" />{strategy === "compare" ? "Compare both strategies" : "Summarize"}
            </Button>
            <span className="text-xs text-muted">Ctrl + Enter</span>
            {problem && text.trim() && <span className="text-sm text-bad" role="alert">{problem}</span>}
          </div>
          {settings?.effective_mode === "demo" && (
            <InfoNote>
              <strong>Demo mode.</strong> No API key is configured, so summaries come from a transparent <em>rule-based extractive</em> engine (it selects sentences from your text; it does not write new ones).
              Add an Groq key in <code>backend/.env</code> to use real AI summarization and verification.
            </InfoNote>
          )}
        </CardContent>
      </Card>

      {error && <ErrorNote message={error} />}

      {loading && results.length === 0 && (
        <div className={strategy === "compare" ? "grid gap-5 md:grid-cols-2" : ""}>
          <Card><SummarySkeleton /></Card>
          {strategy === "compare" && <Card><SummarySkeleton /></Card>}
        </div>
      )}

      {results.length > 0 && (
        <section className="space-y-5" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-serif text-2xl tracking-tight">{wasCompare ? "Side-by-side comparison" : "Summary"}</h3>
            {wasCompare && <Button size="sm" variant="subtle" onClick={verifyBoth} loading={loading}><ShieldCheck className="h-4 w-4" />Verify both</Button>}
          </div>
          <div className={wasCompare ? "grid items-start gap-5 md:grid-cols-2" : ""}>
            {results.map((r) => <SummaryCard key={r.id} run={r} onChange={updateRun} compact={wasCompare} />)}
          </div>
          {wasCompare && <CompareTable runs={results} />}
          <p className="text-xs text-muted">Detected language: {LANG_SHORT[results[0].language_detected]}. Results are stored in the local database.</p>
        </section>
      )}
    </div>
  );
}
