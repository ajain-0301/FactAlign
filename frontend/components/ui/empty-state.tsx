import * as React from "react";
import { cn } from "@/lib/utils";

export function EmptyState({ icon, title, description, children, className }: {
  icon: React.ReactNode; title: string; description: string; children?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface/60 px-6 py-14 text-center", className)}>
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">{icon}</div>
      <h3 className="font-serif text-xl tracking-tight">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">{description}</p>
      {children && <div className="mt-6 flex flex-wrap justify-center gap-2">{children}</div>}
    </div>
  );
}

export function ErrorNote({ message, className }: { message: string; className?: string }) {
  return (
    <div role="alert" className={cn("rounded-xl border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad", className)}>
      {message}
    </div>
  );
}

export function InfoNote({ children, tone = "warn", className }: { children: React.ReactNode; tone?: "warn" | "accent" | "ok"; className?: string }) {
  const t = { warn: "bg-warn-soft text-warn border-warn/25", accent: "bg-accent-soft text-accent border-accent/25", ok: "bg-ok-soft text-ok border-ok/25" }[tone];
  return <div className={cn("rounded-xl border px-4 py-3 text-sm leading-relaxed", t, className)}>{children}</div>;
}

export function Stat({ label, value, sub, hint }: { label: string; value: React.ReactNode; sub?: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl bg-sunken px-4 py-3" title={hint}>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 font-serif text-2xl tracking-tight">{value}</div>
      {sub ? <div className="mt-0.5 text-xs text-muted">{sub}</div> : null}
    </div>
  );
}
