import type { ReactNode } from "react";

export type Palette = {
  ink: string;
  soft: string;
  line: string;
  accent: string;
};

export type DiagramTone = "neutral" | "accent" | "warning" | "success";

const PALETTES: Palette[] = [
  { ink: "#7a3621", soft: "#fdf0ea", line: "#e8b59c", accent: "#c75b39" },
  { ink: "#155f86", soft: "#ebf7ff", line: "#9ed3ef", accent: "#2c84db" },
  { ink: "#0f766e", soft: "#e9fbf8", line: "#8fe1d4", accent: "#159a8a" },
  { ink: "#7c3a8d", soft: "#f7edff", line: "#d9b2ef", accent: "#9c4fd6" },
];

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function paletteAt(index: number): Palette {
  return PALETTES[index % PALETTES.length];
}

function tonePalette(tone: DiagramTone): Palette {
  switch (tone) {
    case "warning":
      return { ink: "#8a4b11", soft: "#fff5df", line: "#f0cf8d", accent: "#d18a24" };
    case "success":
      return { ink: "#0f766e", soft: "#e9fbf8", line: "#8fe1d4", accent: "#159a8a" };
    case "neutral":
      return { ink: "#4b5563", soft: "#f5f1e8", line: "#d9d1c1", accent: "#6b7280" };
    case "accent":
    default:
      return { ink: "#7a3621", soft: "#fdf0ea", line: "#e8b59c", accent: "#c75b39" };
  }
}

export function DiagramSectionPill({
  children,
  tone = "accent",
  className,
}: {
  children: ReactNode;
  tone?: "accent" | "neutral";
  className?: string;
}) {
  return (
    <div
      className={cx(
        "inline-flex items-center gap-3 rounded-full border px-4 py-2 text-xs font-medium shadow-[var(--shadow-sm)]",
        tone === "accent"
          ? "border-[rgba(174,86,48,0.16)] bg-[rgba(255,255,255,0.84)] text-text-tertiary"
          : "border-[color-mix(in_srgb,var(--border)_72%,white)] bg-white/84 text-text-secondary",
        className,
      )}
    >
      {tone === "accent" && <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-orange)]" />}
      <span>{children}</span>
    </div>
  );
}

export function DiagramFormulaChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-[rgba(184,90,51,0.14)] bg-[rgba(255,255,255,0.78)] px-3 py-1.5 font-mono text-xs text-[var(--accent-orange)] shadow-[var(--shadow-sm)]">
      {children}
    </span>
  );
}

export function DiagramStatusPill({
  label,
  detail,
  tone = "neutral",
  className,
}: {
  label: ReactNode;
  detail?: ReactNode;
  tone?: DiagramTone;
  className?: string;
}) {
  const palette = tonePalette(tone);
  return (
    <div
      className={cx(
        "inline-flex min-h-[34px] items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] shadow-[var(--shadow-sm)]",
        className,
      )}
      style={{
        borderColor: palette.line,
        background: `linear-gradient(180deg, ${palette.soft}, rgba(255,255,255,0.96))`,
        color: palette.ink,
      }}
    >
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{ background: palette.accent }}
        aria-hidden="true"
      />
      <span className="font-semibold uppercase tracking-[0.14em]">{label}</span>
      {detail ? <span className="text-text-secondary">{detail}</span> : null}
    </div>
  );
}

export function DiagramFlowBridge({
  label,
  compact = false,
}: {
  label: ReactNode;
  compact?: boolean;
}) {
  return (
    <>
      <div className="flex items-center justify-center xl:hidden" aria-hidden="true">
        <div className="flex w-full max-w-sm items-center gap-3 rounded-full border border-[var(--border)] bg-white/82 px-4 py-3 shadow-[var(--shadow-sm)]">
          <div className="h-px flex-1 bg-[linear-gradient(90deg,rgba(174,86,48,0.18),rgba(174,86,48,0.72))]" />
          <span className="rounded-full border border-[rgba(174,86,48,0.18)] bg-[rgba(174,86,48,0.08)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--accent-orange)]">
            {label}
          </span>
          <div className="h-px flex-1 bg-[linear-gradient(90deg,rgba(44,132,219,0.72),rgba(44,132,219,0.18))]" />
        </div>
      </div>

      <div className="relative hidden items-center justify-center xl:flex" aria-hidden="true">
        <div className={cx("flex h-full flex-col items-center justify-center", compact ? "gap-3" : "gap-4")}>
          <div className="grid h-14 w-14 place-items-center rounded-full border border-[rgba(174,86,48,0.16)] bg-white/88 text-[var(--accent-orange)] shadow-[var(--shadow-md)]">
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" aria-hidden="true">
              <path d="M5 12h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <path d="m13 7 4 5-4 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="max-w-[7rem] text-center text-[11px] font-medium uppercase tracking-[0.16em] text-text-tertiary">
            {label}
          </div>
        </div>
      </div>
    </>
  );
}

export function DiagramConnectorArrow({
  palette,
  orientation = "horizontal",
  label,
  className,
}: {
  palette: Palette;
  orientation?: "horizontal" | "vertical";
  label?: ReactNode;
  className?: string;
}) {
  const isHorizontal = orientation === "horizontal";

  return (
    <div
      className={cx(
        "pointer-events-none flex items-center justify-center",
        isHorizontal ? "gap-2" : "flex-col gap-2",
        className,
      )}
      aria-hidden="true"
    >
      <div
        className={cx("shrink-0", isHorizontal ? "h-px w-8" : "h-8 w-px")}
        style={{
          background: isHorizontal
            ? `linear-gradient(90deg, color-mix(in srgb, ${palette.accent} 14%, white), ${palette.accent})`
            : `linear-gradient(180deg, color-mix(in srgb, ${palette.accent} 14%, white), ${palette.accent})`,
        }}
      />
      <div
        className="grid h-9 w-9 place-items-center rounded-full border bg-white/90 shadow-[var(--shadow-sm)]"
        style={{ borderColor: palette.line, color: palette.accent }}
      >
        <svg
          viewBox="0 0 24 24"
          className={cx("h-4 w-4", isHorizontal ? "" : "rotate-90")}
          fill="none"
        >
          <path d="M5 12h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="m13 7 4 5-4 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div
        className={cx("shrink-0", isHorizontal ? "h-px w-8" : "h-8 w-px")}
        style={{
          background: isHorizontal
            ? `linear-gradient(90deg, ${palette.accent}, color-mix(in srgb, ${palette.accent} 14%, white))`
            : `linear-gradient(180deg, ${palette.accent}, color-mix(in srgb, ${palette.accent} 14%, white))`,
        }}
      />
      {label ? (
        <span className="max-w-[6.5rem] text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-text-tertiary">
          {label}
        </span>
      ) : null}
    </div>
  );
}

export function DiagramCurveConnector({
  palette,
  direction = "right",
  className,
}: {
  palette: Palette;
  direction?: "left" | "right";
  className?: string;
}) {
  const isRight = direction === "right";
  const path = isRight
    ? "M42 2 C42 16 56 18 60 28 C64 38 72 40 82 40"
    : "M42 2 C42 16 28 18 24 28 C20 38 12 40 2 40";
  const arrowPath = isRight
    ? "m75 34 7 6-7 6"
    : "m9 34-7 6 7 6";

  return (
    <svg
      viewBox="0 0 84 52"
      className={cx("h-[52px] w-full", className)}
      fill="none"
      aria-hidden="true"
    >
      <path
        d={path}
        stroke={palette.accent}
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="4 5"
        opacity="0.75"
      />
      <circle cx="42" cy="2" r="3" fill={palette.accent} opacity="0.88" />
      <path
        d={arrowPath}
        stroke={palette.accent}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function DiagramStepBadge({
  palette,
  label,
}: {
  palette: Palette;
  label: ReactNode;
}) {
  return (
    <div
      className="grid h-10 w-10 shrink-0 place-items-center rounded-[16px] text-sm font-bold text-white shadow-[var(--shadow-sm)] md:h-11 md:w-11"
      style={{ background: palette.accent }}
    >
      {label}
    </div>
  );
}

export function DiagramNodeCard({
  palette,
  eyebrow,
  title,
  badge,
  emphasis,
  muted = false,
  className,
  children,
}: {
  palette: Palette;
  eyebrow?: ReactNode;
  title: ReactNode;
  badge?: ReactNode;
  emphasis?: ReactNode;
  muted?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <article
      className={cx(
        "relative overflow-hidden rounded-[28px] border px-5 py-5 shadow-[var(--shadow-md)] transition-[opacity,transform] duration-300",
        className,
      )}
      style={{
        background: `radial-gradient(circle at top left, color-mix(in srgb, ${palette.accent} 12%, transparent), transparent 38%), ${palette.soft}`,
        borderColor: palette.line,
        opacity: muted ? 0.38 : 1,
        transform: muted ? "scale(0.985)" : "scale(1)",
      }}
    >
      <div
        className="absolute inset-x-5 top-0 h-px bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.88),transparent)]"
        aria-hidden="true"
      />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {eyebrow ? (
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: palette.ink }}>
              {eyebrow}
            </p>
          ) : null}
          <h4 className="mt-2 font-serif text-[clamp(1.34rem,4.2vw,2.22rem)] leading-tight text-text">{title}</h4>
        </div>
        {badge ? (
          <div
            className="rounded-full border bg-white/80 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] shadow-[var(--shadow-sm)]"
            style={{ borderColor: palette.line, color: palette.ink }}
          >
            {badge}
          </div>
        ) : null}
      </div>

      {emphasis ? (
        <div
          className="mt-5 rounded-[22px] border bg-white/74 px-4 py-4 shadow-[var(--shadow-sm)]"
          style={{ borderColor: "color-mix(in srgb, var(--border) 76%, white)" }}
        >
          {emphasis}
        </div>
      ) : null}

      {children ? <div className={emphasis ? "mt-5" : "mt-4"}>{children}</div> : null}
    </article>
  );
}

export function DiagramCalloutPanel({
  palette,
  eyebrow,
  title,
  body,
  accentLabel,
  className,
}: {
  palette: Palette;
  eyebrow?: ReactNode;
  title: ReactNode;
  body?: ReactNode;
  accentLabel?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx("rounded-[26px] border px-5 py-5 shadow-[var(--shadow-md)]", className)}
      style={{
        borderColor: palette.line,
        background: `linear-gradient(135deg, ${palette.soft}, rgba(255,255,255,0.96))`,
      }}
    >
      <div className="grid gap-4 lg:grid-cols-[auto_1fr] lg:items-start">
        <div className="inline-flex items-center gap-3 rounded-full border border-white/70 bg-white/70 px-3 py-2 text-sm font-semibold text-text shadow-[var(--shadow-sm)]">
          <span className="grid h-8 w-8 place-items-center rounded-full text-white" style={{ background: palette.accent }}>
            {accentLabel || "!"}
          </span>
          <span>{eyebrow || "Điểm cần chú ý"}</span>
        </div>
        <div>
          <h4 className="font-serif text-[clamp(1.5rem,2.5vw,2rem)] leading-tight text-text">{title}</h4>
          {body ? <div className="mt-3 max-w-3xl text-sm leading-7 text-text-secondary">{body}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function DiagramAnnotationChip({
  title,
  index,
  tone = "accent",
  selected = false,
  onClick,
  controls,
}: {
  title: ReactNode;
  index?: number;
  tone?: DiagramTone;
  selected?: boolean;
  onClick: () => void;
  controls?: string;
}) {
  const palette = tonePalette(tone);
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-controls={controls}
      className={cx(
        "inline-flex min-h-[40px] items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-[transform,box-shadow,border-color,background] duration-200",
        selected ? "shadow-[var(--shadow-sm)]" : "hover:-translate-y-[1px]",
      )}
      style={{
        borderColor: selected ? palette.line : "color-mix(in srgb, var(--border) 82%, white)",
        background: selected ? `linear-gradient(180deg, ${palette.soft}, rgba(255,255,255,0.94))` : "rgba(255,255,255,0.9)",
        color: selected ? palette.ink : "var(--text-secondary)",
      }}
      onClick={onClick}
    >
      {typeof index === "number" ? (
        <span
          className="grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold text-white"
          style={{ background: palette.accent }}
        >
          {index + 1}
        </span>
      ) : null}
      <span className="tracking-[0.08em]">{title}</span>
    </button>
  );
}

export function DiagramInsightPanel({
  title,
  body,
  tone = "neutral",
  eyebrow,
  className,
}: {
  title: ReactNode;
  body?: ReactNode;
  tone?: DiagramTone;
  eyebrow?: ReactNode;
  className?: string;
}) {
  const palette = tonePalette(tone);
  return (
    <div
      className={cx("relative overflow-hidden rounded-[22px] border px-4 py-4 shadow-[var(--shadow-sm)]", className)}
      style={{
        borderColor: palette.line,
        background: `linear-gradient(180deg, ${palette.soft}, rgba(255,255,255,0.94))`,
      }}
    >
      <div className="absolute inset-y-3 left-0 w-[3px] rounded-full" style={{ background: palette.accent }} aria-hidden="true" />
      {eyebrow ? (
        <p className="pl-3 text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: palette.ink }}>
          {eyebrow}
        </p>
      ) : null}
      <h5 className="pl-3 font-serif text-[1.08rem] leading-tight text-text">{title}</h5>
      {body ? <div className="mt-2 pl-3 text-sm leading-6 text-text-secondary">{body}</div> : null}
    </div>
  );
}

export function DiagramStageFrame({
  eyebrow,
  title,
  caption,
  children,
  className,
}: {
  eyebrow?: ReactNode;
  title?: ReactNode;
  caption?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "overflow-hidden rounded-[28px] border border-[color-mix(in_srgb,var(--border)_78%,white)] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(247,243,235,0.94))] shadow-[var(--shadow-md)]",
        className,
      )}
    >
      {(eyebrow || title) ? (
        <div className="border-b border-[color-mix(in_srgb,var(--border)_66%,white)] px-5 py-4">
          {eyebrow ? (
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--accent-orange)]">{eyebrow}</p>
          ) : null}
          {title ? <h5 className="mt-1 font-serif text-[clamp(1.08rem,2.6vw,1.32rem)] leading-tight text-text">{title}</h5> : null}
        </div>
      ) : null}
      <div className="px-4 py-4 md:px-5 md:py-5">{children}</div>
      {caption ? (
        <div className="border-t border-[color-mix(in_srgb,var(--border)_66%,white)] px-5 py-3 text-sm leading-6 text-text-secondary">
          {caption}
        </div>
      ) : null}
    </div>
  );
}

export function DiagramGroupBand({
  label,
  detail,
  tone = "neutral",
  className,
  children,
}: {
  label: ReactNode;
  detail?: ReactNode;
  tone?: DiagramTone;
  className?: string;
  children: ReactNode;
}) {
  const palette = tonePalette(tone);

  return (
    <section
      className={cx(
        "relative overflow-hidden rounded-[24px] border px-4 py-4 shadow-[var(--shadow-sm)] md:px-5 md:py-5",
        className,
      )}
      style={{
        borderColor: palette.line,
        background: `linear-gradient(180deg, color-mix(in srgb, ${palette.soft} 92%, white), rgba(255,255,255,0.98))`,
      }}
    >
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background: `linear-gradient(90deg, transparent, ${palette.accent}, transparent)`,
          opacity: 0.38,
        }}
        aria-hidden="true"
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div
          className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] shadow-[var(--shadow-sm)]"
          style={{
            borderColor: palette.line,
            background: "rgba(255,255,255,0.88)",
            color: palette.ink,
          }}
        >
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: palette.accent }} aria-hidden="true" />
          <span>{label}</span>
        </div>
        {detail ? (
          <p className="text-sm leading-6 text-text-secondary">
            {detail}
          </p>
        ) : null}
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

export function DiagramLegend({
  items,
  className,
}: {
  items: Array<{ label: ReactNode; color: string; detail?: ReactNode }>;
  className?: string;
}) {
  if (!items.length) return null;
  return (
    <div className={cx("flex flex-wrap gap-2", className)}>
      {items.map((item, index) => (
        <div
          key={`${String(item.label)}-${index}`}
          className="inline-flex items-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--border)_80%,white)] bg-white/88 px-3 py-1.5 text-xs text-text-secondary shadow-[var(--shadow-sm)]"
        >
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} aria-hidden="true" />
          <span className="font-semibold">{item.label}</span>
          {item.detail ? <span className="text-text-tertiary">{item.detail}</span> : null}
        </div>
      ))}
    </div>
  );
}

export function DiagramMetricPill({
  label,
  value,
  tone = "neutral",
}: {
  label: ReactNode;
  value: ReactNode;
  tone?: DiagramTone;
}) {
  const palette = tonePalette(tone);
  return (
    <div
      className="rounded-[18px] border px-3 py-3 shadow-[var(--shadow-sm)]"
      style={{
        borderColor: palette.line,
        background: `linear-gradient(180deg, ${palette.soft}, rgba(255,255,255,0.94))`,
      }}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: palette.ink }}>
        {label}
      </p>
      <p className="mt-1 font-serif text-[1.45rem] leading-none text-text">{value}</p>
    </div>
  );
}

export function DiagramCenterpiece({
  palette,
  eyebrow,
  title,
  body,
}: {
  palette: Palette;
  eyebrow: ReactNode;
  title: ReactNode;
  body?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-[30px] border px-6 py-7 text-center shadow-[var(--shadow-lg)]" style={{
      borderColor: "color-mix(in srgb, var(--border) 72%, white)",
      background: `radial-gradient(circle at top, color-mix(in srgb, ${palette.accent} 16%, transparent), transparent 42%), linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,244,236,0.96))`,
    }}>
      <div className="absolute left-1/2 top-0 h-10 w-px -translate-x-1/2 bg-[linear-gradient(180deg,rgba(174,86,48,0.4),rgba(174,86,48,0))]" aria-hidden="true" />
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: palette.accent }}>{eyebrow}</p>
      <h4 className="mt-2 font-serif text-[clamp(2rem,4vw,3.2rem)] leading-[0.98] tracking-[-0.04em] text-text">{title}</h4>
      {body ? <div className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-text-secondary">{body}</div> : null}
    </div>
  );
}
