/** Pure transcript, control, and durable-journal projections. */
import type { NekoMessage, NekoSession } from "./session-store-types";
import type { ContentBlock, ToolExecutionBlockData } from "@/api/types";
import type { DriverActivity, DriverConfigOption } from "../drivers/types";
import type { NekoSessionEvent, NekoSessionEventData } from "../session-events";
import { appendSessionEvent } from "../session-events";
export function lastBlock(message: NekoMessage): ContentBlock | undefined {
  return message.blocks?.[message.blocks.length - 1];
}
/** The streaming assistant message of a session (last message when open). */
export function openAssistant(session: NekoSession): NekoMessage | undefined {
  const last = session.messages[session.messages.length - 1];
  return last?.role === "assistant" ? last : undefined;
}
export function toToolBlock(activity: DriverActivity): ToolExecutionBlockData {
  return {
    type: "tool_execution",
    id: activity.id,
    tool: {
      id: activity.id,
      name: activity.title,
      result: activity.detail,
    },
    status: activity.status === "pending" || activity.status === "in_progress" ? "pending" : "completed",
    outcome: activity.status === "pending" || activity.status === "in_progress" ? undefined : activity.status,
  };
}
/** Rebuild effective session-control values from the durable transition log. */
export function projectControls(controls: DriverConfigOption[], events: NekoSessionEvent[]): DriverConfigOption[] {
  const projected = controls.map((option) => ({
    ...option,
    choices: option.choices?.map((choice) => ({ ...choice })),
  }));
  // Index controls are the latest provider-reported baseline. Historical
  // commits from an earlier process must never override a fresh provider's
  // defaults, so replay only the current provider epoch.
  let epochStart = 0;
  for (const [eventIndex, event] of events.entries()) {
    if (event.data.type === "runtime-attached")
      epochStart = eventIndex + 1;
  }
  for (const event of events.slice(epochStart)) {
    const transition = event.data;
    if (transition.type !== "control-change")
      continue;
    const value = transition.phase === "committed"
      ? transition.nextValue
      : transition.phase === "rolled-back"
        ? transition.previousValue
        : null;
    if (value === null)
      continue;
    const option = projected.find((candidate) => candidate.id === transition.optionId);
    if (option)
      option.currentValue = value;
  }
  return projected;
}
export function appendOwnedSessionEvent(session: NekoSession, visibility: NekoSessionEvent["visibility"], data: NekoSessionEventData, at?: number): NekoSessionEvent {
  const event = appendSessionEvent(session.events as NekoSessionEvent[], visibility, data, at, session.eventHighWaterMark);
  session.eventHighWaterMark = event.seq;
  return event;
}
export function removeEventById(events: NekoSessionEvent[], eventId: string | null): void {
  if (eventId === null)
    return;
  const eventIndex = events.findIndex((event) => event.eventId === eventId);
  if (eventIndex < 0)
    return;
  events.splice(eventIndex, 1);
}
export function projectAuthoritativeMessages(messages: NekoMessage[], events: NekoSessionEvent[]): NekoMessage[] {
  const stagedPrompts = new Map(events.flatMap((event) => event.eventId &&
    event.data.type === "model-input" &&
    event.data.delivery === "staged"
    ? [[event.eventId, event] as const]
    : []));
  const invokedEventIds = new Set<string>();
  for (const event of events) {
    if (event.data.type !== "dispatch-invoked" || event.data.action !== "prompt")
      continue;
    const target = stagedPrompts.get(event.data.targetEventId);
    if (target &&
      event.seq > target.seq &&
      target.data.type === "model-input" &&
      event.data.providerInstanceId === target.data.providerInstanceId) {
      invokedEventIds.add(event.data.targetEventId);
    }
  }
  const stagedMessageIds = new Set(events.flatMap((event) => event.data.type === "model-input" &&
    event.data.delivery === "staged" &&
    (!event.eventId || !invokedEventIds.has(event.eventId))
    ? [event.data.messageId]
    : []));
  if (stagedMessageIds.size === 0)
    return messages;
  return messages.filter((message) => !stagedMessageIds.has(message.id));
}
