"use client";
import * as React from "react";
import { CheckCircle2, KeyRound, PlugZap, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/components/app-provider";
import type { Preferences } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorNote, InfoNote } from "@/components/ui/empty-state";
import { Field, Select, Switch } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { formatDate } from "@/lib/utils";

export default function SettingsPage() {
  const { settings, setSettings, loading, refresh } = useApp();
  const { toast } = useToast();
  const [testing, setTesting] = React.useState(false);
  const [testError, setTestError] = React.useState<string | null>(null);
  const [testOk, setTestOk] = React.useState<string | null>(null);

  if (loading || !settings) return <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-64" /></div>;
  const p = settings.preferences;

  const update = async (patch: Partial<Preferences>) => {
    try { setSettings(await api.updateSettings(patch)); toast("Settings saved"); }
    catch (e) { toast((e as Error).message, "bad"); }
  };
  const test = async () => {
    setTesting(true); setTestError(null); setTestOk(null);
    try {
      const r = await api.testConnection(settings.model);
      setTestOk(`Connected: ${r.model} responded in ${Math.round(r.latency_ms)} ms.`);
    } catch (e) { setTestError((e as Error).message); } finally { setTesting(false); await refresh(); }
  };
  const c = settings.connection;

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h2 className="font-serif text-3xl tracking-tight">Settings</h2>
        <p className="mt-1 text-sm text-muted">Provider status and your defaults. API keys are read from the server environment and are never sent to the browser.</p>
      </div>

      <Card>
        <CardHeader>
          <div><CardTitle>AI provider</CardTitle><CardDescription>Groq for summarization and LLM-based verification.</CardDescription></div>
          {settings.effective_mode === "real" ? <Badge tone="ok">Real AI mode</Badge> : settings.effective_mode === "demo" ? <Badge tone="warn">Demo mode</Badge> : <Badge tone="bad">Unavailable</Badge>}
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-xl bg-sunken px-4 py-3">
              <dt className="flex items-center gap-1.5 text-xs text-muted"><KeyRound className="h-3.5 w-3.5" />API key on server</dt>
              <dd className="mt-1 font-medium">{settings.api_key_configured ? "Configured (hidden)" : "Not configured"}</dd>
            </div>
            <div className="rounded-xl bg-sunken px-4 py-3">
              <dt className="flex items-center gap-1.5 text-xs text-muted"><PlugZap className="h-3.5 w-3.5" />Connection</dt>
              <dd className="mt-1 flex items-center gap-1.5 font-medium">
                {c.verified ? <><CheckCircle2 className="h-4 w-4 text-ok" />Verified ({c.model})</> : <><XCircle className="h-4 w-4 text-muted" />Not verified</>}
              </dd>
              {c.verified_at && <dd className="text-xs text-muted">{formatDate(c.verified_at)}</dd>}
            </div>
          </dl>
          {settings.mode_problem && <ErrorNote message={settings.mode_problem} />}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Provider mode" hint="Auto uses real AI whenever a key is configured.">
              <Select value={settings.provider_mode} onChange={(e) => update({ provider_mode: e.target.value as Preferences["provider_mode"] })}>
                <option value="auto">Auto</option><option value="demo">Demo (rule-based, offline)</option><option value="real">Real AI (requires key)</option>
              </Select>
            </Field>
            <Field label="Model" hint="Changing the model clears the verified status.">
              <Select value={settings.model} onChange={(e) => update({ model: e.target.value })}>
                {Array.from(new Set([settings.model, ...settings.model_options])).map((m) => <option key={m} value={m}>{m}</option>)}
              </Select>
            </Field>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" onClick={test} loading={testing}><PlugZap className="h-4 w-4" />Test connection</Button>
            <span className="text-xs text-muted">Sends one tiny request to the provider. “Verified” is only shown after it succeeds.</span>
          </div>
          {testOk && <InfoNote tone="ok" >{testOk}</InfoNote>}
          {testError && <ErrorNote message={testError} />}
          {c.error && !testError && <p className="text-xs text-muted">Last test failed: {c.error}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><div><CardTitle>Defaults</CardTitle><CardDescription>Applied when you open New Summary.</CardDescription></div></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Default strategy">
            <Select value={p.default_strategy} onChange={(e) => update({ default_strategy: e.target.value as Preferences["default_strategy"] })}>
              <option value="standard">Standard</option><option value="factuality">Factuality-aware</option>
            </Select>
          </Field>
          <Field label="Default summary length">
            <Select value={p.default_length} onChange={(e) => update({ default_length: e.target.value as Preferences["default_length"] })}>
              <option value="short">Short</option><option value="medium">Medium</option><option value="long">Long</option>
            </Select>
          </Field>
          <Field label="Input language">
            <Select value={p.default_language} onChange={(e) => update({ default_language: e.target.value as Preferences["default_language"] })}>
              <option value="auto">Auto-detect</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hindi-English code-mixed</option>
            </Select>
          </Field>
          <Field label="Output language">
            <Select value={p.default_output_language} onChange={(e) => update({ default_output_language: e.target.value as Preferences["default_output_language"] })}>
              <option value="same">Same as source</option><option value="hi">Hindi</option><option value="en">English</option><option value="hinglish">Hinglish</option>
            </Select>
          </Field>
          <Field label="Verification method" hint="Auto: hybrid in real mode, rule-based in demo mode.">
            <Select value={p.verifier} onChange={(e) => update({ verifier: e.target.value as Preferences["verifier"] })}>
              <option value="auto">Auto</option><option value="rule">Rule-based</option><option value="llm">LLM judge</option><option value="claim_nli">Claim-level NLI (Groq extraction + local models)</option><option value="hybrid">Hybrid</option>
            </Select>
          </Field>
          <div className="flex items-center justify-between gap-4 rounded-xl border border-border px-4 py-3">
            <div><div className="text-sm font-medium">Auto-save to history</div><div className="text-xs text-muted">Otherwise use “Save to history” per result.</div></div>
            <Switch checked={p.auto_save} onChange={(v) => update({ auto_save: v })} label="Auto-save to history" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><div><CardTitle>Enable real AI mode</CardTitle></div></CardHeader>
        <CardContent>
          <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed">{settings.setup_instructions.map((s) => <li key={s}>{s}</li>)}</ol>
          <p className="mt-4 text-xs text-muted">
            Limits: {settings.limits.max_input_chars.toLocaleString()} characters per document · uploads up to {settings.limits.max_upload_mb} MB · documents over {settings.limits.chunk_chars.toLocaleString()} characters
            are chunked · model timeout {settings.limits.llm_timeout_seconds}s · database: {settings.database}.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
