import type { NekoMessage } from "./stores/session-store-types";

/** Never infer Retry from equal text: ordinary repeated questions stay visible. */
export function retriedMessageIds(messages: readonly NekoMessage[]): Set<string> {
  const earlier = new Map<string, NekoMessage>();
  const retries = new Set<string>();
  for (const message of messages) {
    if (message.role !== "user") continue;
    const original = typeof message.retryOfMessageId === "string"
      ? earlier.get(message.retryOfMessageId) : undefined;
    if (original && message.id !== original.id && message.text?.trim()
      && message.text === original.text) retries.add(message.id);
    earlier.set(message.id, message);
  }
  return retries;
}
