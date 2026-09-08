export const WIII_APP_EVENTS_PROTOCOL = "dev.wiii.app-events.v1" as const;

export type AppEventKind =
  | "content_changed"
  | "state_changed"
  | "attention_required";

export type AppEventResponseMode = "observe_only" | "draft" | "auto_reply";

export interface AppEventSubscription {
  subscriptionId: string;
  appIds: string[];
  resourceRefs: string[];
  responseMode: AppEventResponseMode;
  expiresAt: string;
  heartbeatMs: number;
  maxActions: number;
}

export interface AppEventSignal {
  eventId: string;
  cursor: string;
  appId: string;
  resourceRef: string;
  kind: AppEventKind;
  observedAt: string;
}

export type AppEventSource =
  | "at_spi"
  | "ui_automation"
  | "ax_observer"
  | "dom"
  | "webhook";

export interface AppEventBatch {
  source: AppEventSource;
  sourceId: string;
  cursor: string;
  gapDetected: boolean;
  events: AppEventSignal[];
}

export interface AppEventPollRequest {
  environmentId: string;
  afterCursor: string | null;
  limit: number;
  waitMs?: number;
}

export interface AppEventWake extends AppEventSignal {
  firstObservedAt: string;
  coalescedCount: number;
}

interface PendingWake {
  firstObservedAt: string;
  lastReceivedAtMs: number;
  signal: AppEventSignal;
  coalescedCount: number;
}

const EVENT_KINDS = new Set<AppEventKind>([
  "content_changed",
  "state_changed",
  "attention_required",
]);
const SIGNAL_KEYS = new Set([
  "eventId",
  "cursor",
  "appId",
  "resourceRef",
  "kind",
  "observedAt",
]);
const SUBSCRIPTION_KEYS = new Set([
  "subscriptionId",
  "appIds",
  "resourceRefs",
  "responseMode",
  "expiresAt",
  "heartbeatMs",
  "maxActions",
]);
const RESPONSE_MODES = new Set<AppEventResponseMode>([
  "observe_only",
  "draft",
  "auto_reply",
]);
const IDENTIFIER = /^[a-z0-9][a-z0-9._:-]*$/iu;

function boundedIdentifier(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string" || value.length < 1 || value.length > maxLength) return null;
  return IDENTIFIER.test(value) ? value : null;
}

export function appEventSignalFrom(value: unknown): AppEventSignal | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (Object.keys(record).some((key) => !SIGNAL_KEYS.has(key))) return null;

  const eventId = boundedIdentifier(record.eventId, 160);
  const cursor = boundedIdentifier(record.cursor, 512);
  const appId = boundedIdentifier(record.appId, 64);
  const resourceRef = boundedIdentifier(record.resourceRef, 200);
  const kind = record.kind;
  const observedAt = record.observedAt;
  if (
    !eventId ||
    !cursor ||
    !appId ||
    !resourceRef ||
    typeof kind !== "string" ||
    !EVENT_KINDS.has(kind as AppEventKind) ||
    typeof observedAt !== "string" ||
    observedAt.length > 40 ||
    !Number.isFinite(Date.parse(observedAt))
  ) {
    return null;
  }

  return { eventId, cursor, appId, resourceRef, kind: kind as AppEventKind, observedAt };
}

function identifierList(value: unknown, limit: number, itemLimit: number): string[] | null {
  if (!Array.isArray(value) || value.length < 1 || value.length > limit) return null;
  const parsed = value.map((item) => boundedIdentifier(item, itemLimit));
  if (parsed.some((item) => item === null)) return null;
  return [...new Set(parsed as string[])];
}

export function appEventSubscriptionFrom(
  value: unknown,
  nowMs = Date.now(),
): AppEventSubscription | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (Object.keys(record).some((key) => !SUBSCRIPTION_KEYS.has(key))) return null;

  const subscriptionId = boundedIdentifier(record.subscriptionId, 160);
  const appIds = identifierList(record.appIds, 16, 64);
  const resourceRefs = identifierList(record.resourceRefs, 64, 200);
  const responseMode = record.responseMode;
  const expiresAt = record.expiresAt;
  const expiresAtMs = typeof expiresAt === "string" ? Date.parse(expiresAt) : Number.NaN;
  const heartbeatMs = record.heartbeatMs;
  const maxActions = record.maxActions;
  if (
    !subscriptionId ||
    !appIds ||
    !resourceRefs ||
    typeof responseMode !== "string" ||
    !RESPONSE_MODES.has(responseMode as AppEventResponseMode) ||
    typeof expiresAt !== "string" ||
    expiresAt.length > 40 ||
    !Number.isFinite(nowMs) ||
    !Number.isFinite(expiresAtMs) ||
    expiresAtMs <= nowMs ||
    expiresAtMs - nowMs > 24 * 60 * 60 * 1_000 ||
    !Number.isInteger(heartbeatMs) ||
    (heartbeatMs as number) < 5_000 ||
    (heartbeatMs as number) > 5 * 60 * 1_000 ||
    !Number.isInteger(maxActions) ||
    (maxActions as number) < 0 ||
    (maxActions as number) > 1_000
  ) {
    return null;
  }

  return {
    subscriptionId,
    appIds,
    resourceRefs,
    responseMode: responseMode as AppEventResponseMode,
    expiresAt,
    heartbeatMs: heartbeatMs as number,
    maxActions: maxActions as number,
  };
}

export class AppEventCoalescer {
  private readonly pending = new Map<string, PendingWake>();
  private readonly seenEventIds = new Set<string>();
  private readonly seenOrder: string[] = [];
  private dropped = 0;

  constructor(
    private readonly quietWindowMs = 350,
    private readonly maxPending = 128,
    private readonly maxSeenEventIds = 1024,
  ) {
    if (quietWindowMs < 0 || maxPending < 1 || maxSeenEventIds < 1) {
      throw new Error("invalid_app_event_coalescer_limits");
    }
  }

  get pendingCount(): number {
    return this.pending.size;
  }

  get droppedSignals(): number {
    return this.dropped;
  }

  push(signal: AppEventSignal, receivedAtMs: number): boolean {
    if (!Number.isFinite(receivedAtMs)) return false;
    if (this.seenEventIds.has(signal.eventId)) return true;
    this.remember(signal.eventId);

    const key = `${signal.appId}\u0000${signal.resourceRef}\u0000${signal.kind}`;
    const current = this.pending.get(key);
    if (current) {
      current.signal = signal;
      current.lastReceivedAtMs = receivedAtMs;
      current.coalescedCount += 1;
      return true;
    }
    if (this.pending.size >= this.maxPending) {
      this.dropped += 1;
      return false;
    }

    this.pending.set(key, {
      firstObservedAt: signal.observedAt,
      lastReceivedAtMs: receivedAtMs,
      signal,
      coalescedCount: 1,
    });
    return true;
  }

  drainReady(nowMs: number): AppEventWake[] {
    if (!Number.isFinite(nowMs)) return [];
    const ready = [...this.pending.entries()]
      .filter(([, item]) => nowMs - item.lastReceivedAtMs >= this.quietWindowMs)
      .sort((left, right) => left[1].lastReceivedAtMs - right[1].lastReceivedAtMs);

    for (const [key] of ready) this.pending.delete(key);
    return ready.map(([, item]) => ({
      ...item.signal,
      firstObservedAt: item.firstObservedAt,
      coalescedCount: item.coalescedCount,
    }));
  }

  private remember(eventId: string): void {
    this.seenEventIds.add(eventId);
    this.seenOrder.push(eventId);
    while (this.seenOrder.length > this.maxSeenEventIds) {
      const expired = this.seenOrder.shift();
      if (expired) this.seenEventIds.delete(expired);
    }
  }
}
