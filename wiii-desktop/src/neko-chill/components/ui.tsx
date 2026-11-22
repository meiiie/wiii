import type { ComponentProps, ReactNode } from "react";

type ButtonProps = ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
};

/** Native controls keep their semantics, refs, and caller-owned pending state. */
export function NekoButton({ variant = "secondary", size = "md", type = "button", className = "", ...props }: ButtonProps) {
  return <button {...props} type={type} data-variant={variant} data-size={size} className={`nk-button ${className}`} />;
}

export function NekoIconButton({ label, children, className = "", ...props }: Omit<ButtonProps, "aria-label" | "children"> & { label: string; children: ReactNode }) {
  return <NekoButton variant="ghost" {...props} aria-label={label} className={`nk-icon-button ${className}`}>{children}</NekoButton>;
}

export function NekoInput({ className = "", ...props }: ComponentProps<"input">) {
  return <input {...props} className={`nk-control-input ${className}`} />;
}

export function NekoCard({ tone = "surface", className = "", ...props }: ComponentProps<"div"> & { tone?: "surface" | "inset" }) {
  return <div {...props} data-tone={tone} className={`nk-card ${className}`} />;
}

export function NekoBadge({ className = "", ...props }: ComponentProps<"span">) {
  return <span {...props} className={`nk-badge ${className}`} />;
}

export function NekoListButton({ active = false, type = "button", className = "", ...props }: ComponentProps<"button"> & { active?: boolean }) {
  return <button {...props} type={type} data-active={active || undefined} className={`nk-list-button ${className}`} />;
}

/** Presentation only: native dialog focus, dismissal, and save guards stay local. */
export function NekoDialogPanel({ size = "standard", className = "", ...props }: ComponentProps<"section"> & { size?: "standard" | "compact" }) {
  return <section {...props} data-size={size} className={`nk-dialog-panel ${className}`} />;
}
