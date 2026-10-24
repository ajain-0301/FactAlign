import { cn } from "@/lib/utils";

/** Original FactAlign mark: a terracotta tile with a check-stroke forming an "F". Not affiliated with any other brand. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-8 w-8", className)} role="img" aria-label="FactAlign">
      <rect width="32" height="32" rx="9" className="fill-accent" />
      <path d="M11 9.5h10.5M11 9.5V23M11 15.5h7" className="stroke-accent-fg" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M17.2 21.2l2.2 2.2 4.1-4.9" className="stroke-accent-fg" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("font-serif text-[1.25rem] tracking-tight", className)}>
      Fact<span className="text-accent">Indic</span>
    </span>
  );
}
