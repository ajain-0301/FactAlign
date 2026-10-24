import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} aria-hidden />;
}

export function SummarySkeleton() {
  return (
    <div className="space-y-4 p-5" role="status" aria-label="Generating summary">
      <Skeleton className="h-5 w-1/3" />
      <div className="space-y-2.5">
        <Skeleton /><Skeleton /><Skeleton className="w-5/6" /><Skeleton className="w-2/3" />
      </div>
      <div className="grid grid-cols-3 gap-3 pt-2">
        <Skeleton className="h-14" /><Skeleton className="h-14" /><Skeleton className="h-14" />
      </div>
    </div>
  );
}
