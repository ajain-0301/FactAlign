"use client";
import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3, FlaskConical, History, LayoutDashboard, Menu, PanelLeftClose, PanelLeftOpen, Settings, ShieldCheck, SquarePen, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LogoMark, Wordmark } from "./logo";
import { ThemeToggle } from "./theme-toggle";
import { useApp } from "./app-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const NAV = [
  { href: "/", label: "New Summary", icon: SquarePen, title: "New Summary" },
  { href: "/overview", label: "Overview", icon: LayoutDashboard, title: "Overview" },
  { href: "/fact-checker", label: "Fact Checker", icon: ShieldCheck, title: "Fact Checker" },
  { href: "/experiments", label: "Experiments", icon: FlaskConical, title: "Experiments" },
  { href: "/evaluation", label: "Evaluation", icon: BarChart3, title: "Evaluation" },
  { href: "/history", label: "History", icon: History, title: "History" },
  { href: "/settings", label: "Settings", icon: Settings, title: "Settings" },
];

function ModeBadge() {
  const { settings, health, backendDown, loading } = useApp();
  if (loading) return <Badge>Connecting…</Badge>;
  if (backendDown) return <Badge tone="bad">Backend offline</Badge>;
  const mode = settings?.effective_mode ?? health?.mode;
  if (mode === "real") return <Badge tone="ok" title="Real AI mode: requests are sent to the configured model">Real AI · {settings?.model}</Badge>;
  if (mode === "unavailable") return <Badge tone="bad">Provider unavailable</Badge>;
  return <Badge tone="warn" title="Demo mode: rule-based extractive engine, no LLM">Demo mode</Badge>;
}

function NavList({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <nav aria-label="Primary" className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link key={href} href={href} onClick={onNavigate} aria-current={active ? "page" : undefined} title={collapsed ? label : undefined}
            className={cn("group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14.5px] transition-colors",
              active ? "bg-accent-soft font-medium text-accent" : "text-muted hover:bg-sunken hover:text-fg",
              collapsed && "justify-center px-0")}>
            <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
            {!collapsed && <span>{label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const path = usePathname();
  const { backendDown } = useApp();
  React.useEffect(() => { try { setCollapsed(localStorage.getItem("FactAlign-sidebar") === "1"); } catch { /* ignore */ } }, []);
  React.useEffect(() => setOpen(false), [path]);
  const toggle = () => { setCollapsed((c) => { try { localStorage.setItem("FactAlign-sidebar", c ? "0" : "1"); } catch { /* ignore */ } return !c; }); };
  const title = NAV.find((n) => (n.href === "/" ? path === "/" : path.startsWith(n.href)))?.title ?? "FactAlign";

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-fg">Skip to content</a>
      {/* desktop sidebar */}
      <aside className={cn("fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-border bg-surface/70 px-3 py-4 backdrop-blur transition-[width] duration-200 lg:flex",
        collapsed ? "w-[76px]" : "w-[264px]")}>
        <div className={cn("mb-6 flex items-center gap-2.5 px-2", collapsed && "justify-center px-0")}>
          <LogoMark />{!collapsed && <Wordmark />}
        </div>
        <NavList collapsed={collapsed} />
        <div className="mt-auto space-y-3">
          {!collapsed && (
            <p className="px-2 text-xs leading-relaxed text-muted">
              Factuality-aware summarization for Hindi, English and Hinglish. Automatic checks are estimates, not guarantees.
            </p>
          )}
          <Button variant="ghost" size={collapsed ? "icon" : "sm"} onClick={toggle} className={cn(!collapsed && "w-full justify-start")} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <><PanelLeftClose className="h-[18px] w-[18px]" /> Collapse</>}
          </Button>
        </div>
      </aside>

      {/* mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-fg/30" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-[280px] animate-fadeIn flex-col bg-surface px-3 py-4 shadow-pop">
            <div className="mb-6 flex items-center justify-between px-2">
              <div className="flex items-center gap-2.5"><LogoMark /><Wordmark /></div>
              <Button variant="ghost" size="icon" aria-label="Close menu" onClick={() => setOpen(false)}><X className="h-5 w-5" /></Button>
            </div>
            <NavList collapsed={false} onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <div className={cn("transition-[padding] duration-200", collapsed ? "lg:pl-[76px]" : "lg:pl-[264px]")}>
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-bg/85 px-4 backdrop-blur sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></Button>
          <div className="flex items-center gap-2 lg:hidden"><LogoMark className="h-6 w-6" /></div>
          <h1 className="font-serif text-lg tracking-tight">{title}</h1>
          <div className="ml-auto flex items-center gap-2"><ModeBadge /><ThemeToggle /></div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1200px] px-4 py-6 sm:px-6 sm:py-8">
          {backendDown && (
            <div role="alert" className="mb-6 rounded-xl border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad">
              <strong>Cannot reach the FactAlign backend.</strong> Start it with <code className="rounded bg-surface px-1.5 py-0.5">start.bat</code> (or
              run <code className="rounded bg-surface px-1.5 py-0.5">uvicorn app.main:app --port 8000</code> inside <code className="rounded bg-surface px-1.5 py-0.5">backend</code>),
              then reload this page.
            </div>
          )}
          <div className="animate-fadeIn">{children}</div>
        </main>
      </div>
    </div>
  );
}
