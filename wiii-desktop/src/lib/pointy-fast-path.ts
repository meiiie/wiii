import type { HostContext } from "@/stores/host-context-store";

export const POINTY_FAST_PATH_SOURCE = "pointy_fast_path";

const LOCATE_TERMS = [
  "o dau",
  "where",
  "chi",
  "chi cho",
  "tim",
  "tro",
  "highlight",
  "nut",
  "button",
];

const CLICK_TERMS = [
  "mo",
  "bam",
  "click",
  "nhan vao",
  "vao",
  "di toi",
  "chuyen toi",
  "open",
];

const UNSAFE_CLICK_TERMS = [
  "submit",
  "nop bai",
  "quiz",
  "checkout",
  "payment",
  "thanh toan",
  "enroll",
  "dang ky",
  "logout",
  "dang xuat",
  "delete",
  "xoa",
  "mark complete",
  "hoan thanh",
];

const TARGET_ALIASES: Array<{ ids: string[]; terms: string[] }> = [
  {
    ids: ["browse-courses", "browse-courses-link", "browse-courses-button"],
    terms: ["kham pha khoa hoc", "kham pha", "browse courses", "browse"],
  },
  {
    ids: ["continue-learn", "continue-lesson", "continue-course"],
    terms: ["tiep tuc hoc", "tiep tuc", "continue learning", "continue"],
  },
  {
    ids: ["my-courses", "my-courses-link"],
    terms: ["khoa hoc cua toi", "khoa hoc dang hoc", "my courses"],
  },
  {
    ids: ["profile-link", "profile-card"],
    terms: ["ho so", "profile"],
  },
];

export interface PointyFastPathTarget {
  id: string;
  selector: string;
  label?: string;
  click_safe?: boolean;
  click_kind?: string;
}

export interface PointyFastPathAction {
  action: "ui.highlight" | "ui.click";
  requestId: string;
  params: {
    selector: string;
    message?: string;
    duration_ms?: number;
    source: typeof POINTY_FAST_PATH_SOURCE;
  };
  target: PointyFastPathTarget;
  reason: "locate" | "click" | "unsafe_click_demoted";
}

export function normalizePointyText(value: string): string {
  return value
    .replace(/đ/g, "d")
    .replace(/Đ/g, "d")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "d")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function hasAnyTerm(prompt: string, terms: string[]): boolean {
  return terms.some((term) => prompt.includes(term));
}

function coerceTarget(value: unknown): PointyFastPathTarget | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const id = typeof raw.id === "string" ? raw.id.trim() : "";
  const selector = typeof raw.selector === "string" ? raw.selector.trim() : "";
  if (!id || !selector) return null;
  return {
    id,
    selector,
    label: typeof raw.label === "string" ? raw.label.trim() : undefined,
    click_safe: raw.click_safe === true,
    click_kind: typeof raw.click_kind === "string" ? raw.click_kind.trim() : undefined,
  };
}

export function getPointyTargetsFromContext(ctx: HostContext | null): PointyFastPathTarget[] {
  const targets = ctx?.page?.metadata?.available_targets;
  if (!Array.isArray(targets)) return [];
  return targets.map(coerceTarget).filter((target): target is PointyFastPathTarget => Boolean(target));
}

function aliasScore(prompt: string, target: PointyFastPathTarget): number {
  const idText = normalizePointyText(target.id);
  for (const alias of TARGET_ALIASES) {
    const aliasMatchesPrompt = alias.terms.some((term) => prompt.includes(term));
    if (!aliasMatchesPrompt) continue;
    if (alias.ids.some((id) => idText.includes(normalizePointyText(id)))) {
      return 40;
    }
  }
  return 0;
}

function targetScore(prompt: string, target: PointyFastPathTarget): number {
  const idText = normalizePointyText(target.id);
  const selectorText = normalizePointyText(target.selector);
  const labelText = normalizePointyText(target.label || "");
  const labelWords = labelText.split(" ").filter((word) => word.length >= 3);
  let score = aliasScore(prompt, target);

  if (labelText && prompt.includes(labelText)) score += 35;
  if (idText && prompt.includes(idText)) score += 24;
  if (selectorText && prompt.includes(selectorText)) score += 12;
  if (labelWords.length > 0) {
    const matchedWords = labelWords.filter((word) => prompt.includes(word)).length;
    score += matchedWords * 6;
    if (matchedWords === labelWords.length) score += 12;
  }

  if (target.click_safe) score += 2;
  return score;
}

function selectTarget(prompt: string, targets: PointyFastPathTarget[]): PointyFastPathTarget | null {
  let best: { target: PointyFastPathTarget; score: number } | null = null;
  for (const target of targets) {
    const score = targetScore(prompt, target);
    if (score <= 0) continue;
    if (!best || score > best.score) {
      best = { target, score };
    }
  }
  return best && best.score >= 12 ? best.target : null;
}

function isUnsafeClickTarget(prompt: string, target: PointyFastPathTarget): boolean {
  const combined = normalizePointyText(
    `${prompt} ${target.id} ${target.label || ""} ${target.click_kind || ""}`,
  );
  return hasAnyTerm(combined, UNSAFE_CLICK_TERMS);
}

function makeRequestId(): string {
  const random = globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2, 12);
  return `pointy-fast-${random}`;
}

export function buildPointyFastPathAction(
  prompt: string,
  ctx: HostContext | null,
): PointyFastPathAction | null {
  const normalizedPrompt = normalizePointyText(prompt);
  if (!normalizedPrompt) return null;
  const wantsLocate = hasAnyTerm(normalizedPrompt, LOCATE_TERMS);
  const wantsClick = hasAnyTerm(normalizedPrompt, CLICK_TERMS);
  if (!wantsLocate && !wantsClick) return null;

  const target = selectTarget(normalizedPrompt, getPointyTargetsFromContext(ctx));
  if (!target) return null;

  const label = target.label || target.id;
  if (wantsClick && target.click_safe && !isUnsafeClickTarget(normalizedPrompt, target)) {
    return {
      action: "ui.click",
      requestId: makeRequestId(),
      params: {
        selector: target.id,
        message: `Wiii dang mo ${label} cho ban.`,
        source: POINTY_FAST_PATH_SOURCE,
      },
      target,
      reason: "click",
    };
  }

  return {
    action: "ui.highlight",
    requestId: makeRequestId(),
    params: {
      selector: target.id,
      message: `Day la ${label}. Wiii tro vao de ban thay ngay.`,
      duration_ms: wantsClick ? 5600 : 5200,
      source: POINTY_FAST_PATH_SOURCE,
    },
    target,
    reason: wantsClick ? "unsafe_click_demoted" : "locate",
  };
}
