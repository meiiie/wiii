import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import type { CapabilityStatusTone } from "@/lib/capability-status";
import { statusDotClasses, statusToneClasses } from "./connect-display";

export function SummaryMetric({
  icon: icon,
  label,
  value,
  tone = "off",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: CapabilityStatusTone;
}) {
  const Icon = icon;
  return (
    <div className="min-w-0 rounded-lg border border-[var(--border)] bg-surface px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-text-tertiary">
        <Icon size={14} aria-hidden="true" />
        <span className="truncate">{label}</span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${statusDotClasses[tone]}`} aria-hidden="true" />
        <span className="truncate text-lg font-semibold text-text">{value}</span>
      </div>
    </div>
  );
}

export function StatusPill({ tone, children }: { tone: CapabilityStatusTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium ${statusToneClasses[tone]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${statusDotClasses[tone]}`} aria-hidden="true" />
      {children}
    </span>
  );
}
