/**
 * SSE (Server-Sent Events) stream parser for Wiii /chat/stream/v3.
 *
 * Protocol (from maritime-ai-service/app/api/v1/chat_stream.py):
 *   event: <type>\n
 *   data: <json>\n
 *   \n
 *
 * Event types: thinking, answer, sources, metadata, done, error
 */
import type {
  SSEThinkingEvent,
  SSEThinkingDeltaEvent,
  SSEAnswerEvent,
  SSESourcesEvent,
  SSEMetadataEvent,
  SSEErrorEvent,
  SSEToolCallEvent,
  SSEToolResultEvent,
  SSEStatusEvent,
  SSEThinkingStartEvent,
  SSEThinkingEndEvent,
  SSEDomainNoticeEvent,
  SSEEmotionEvent,
  SSEActionTextEvent,
} from "./types";

export interface SSEEventHandler {
  onThinking: (data: SSEThinkingEvent) => void;
  onThinkingDelta?: (data: SSEThinkingDeltaEvent) => void;
  onAnswer: (data: SSEAnswerEvent) => void;
  onSources: (data: SSESourcesEvent) => void;
  onMetadata: (data: SSEMetadataEvent) => void;
  onDone: () => void;
  onError: (data: SSEErrorEvent) => void;
  onToolCall: (data: SSEToolCallEvent) => void;
  onToolResult: (data: SSEToolResultEvent) => void;
  onStatus: (data: SSEStatusEvent) => void;
  onThinkingStart?: (data: SSEThinkingStartEvent) => void;
  onThinkingEnd?: (data: SSEThinkingEndEvent) => void;
  onDomainNotice?: (data: SSEDomainNoticeEvent) => void;
  /** Sprint 135: Soul emotion — LLM-driven avatar expression */
  onEmotion?: (data: SSEEmotionEvent) => void;
  /** Sprint 147: Bold action text between thinking blocks */
  onActionText?: (data: SSEActionTextEvent) => void;
}

/**
 * Parse an SSE stream from ReadableStream<Uint8Array>.
 *
 * Handles:
 * - Partial JSON across TCP chunks (buffer accumulation)
 * - Multi-line data fields
 * - Abort signal for cancellation
 */
/** Result from parseSSEStream, carries reconnection metadata. */
export interface SSEStreamResult {
  /** Last event ID received (for reconnection via Last-Event-ID header). */
  lastEventId: string | null;
}

export async function parseSSEStream(
  stream: ReadableStream<Uint8Array>,
  handlers: SSEEventHandler,
  abortSignal?: AbortSignal
): Promise<SSEStreamResult> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastEventId: string | null = null;

  try {
    while (true) {
      if (abortSignal?.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines
      const events = buffer.split("\n\n");
      // Keep the last (possibly incomplete) chunk in the buffer
      buffer = events.pop() || "";

      for (const eventStr of events) {
        if (!eventStr.trim()) continue;

        const lines = eventStr.trim().split("\n");
        let eventType = "";
        let dataLines: string[] = [];

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataLines.push(line.slice(6));
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5));
          } else if (line.startsWith("id: ")) {
            lastEventId = line.slice(4).trim();
          } else if (line.startsWith("id:")) {
            lastEventId = line.slice(3).trim();
          }
        }

        if (!eventType || dataLines.length === 0) continue;

        const dataStr = dataLines.join("\n");

        try {
          const parsed = JSON.parse(dataStr);
          dispatchEvent(eventType, parsed, handlers);
        } catch {
          // If JSON parsing fails, try to handle as plain text
          console.warn(`[SSE] Failed to parse JSON for event "${eventType}":`, dataStr);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  return { lastEventId };
}

function dispatchEvent(
  eventType: string,
  data: unknown,
  handlers: SSEEventHandler
) {
  switch (eventType) {
    case "thinking":
      handlers.onThinking(data as SSEThinkingEvent);
      break;
    case "answer":
      handlers.onAnswer(data as SSEAnswerEvent);
      break;
    case "sources":
      handlers.onSources(data as SSESourcesEvent);
      break;
    case "metadata":
      handlers.onMetadata(data as SSEMetadataEvent);
      break;
    case "done":
      handlers.onDone();
      break;
    case "error":
      handlers.onError(data as SSEErrorEvent);
      break;
    case "tool_call":
      handlers.onToolCall(data as SSEToolCallEvent);
      break;
    case "tool_result":
      handlers.onToolResult(data as SSEToolResultEvent);
      break;
    case "status":
      handlers.onStatus(data as SSEStatusEvent);
      break;
    case "thinking_delta":
      handlers.onThinkingDelta?.(data as SSEThinkingDeltaEvent);
      break;
    case "thinking_start":
      handlers.onThinkingStart?.(data as SSEThinkingStartEvent);
      break;
    case "thinking_end":
      handlers.onThinkingEnd?.(data as SSEThinkingEndEvent);
      break;
    case "domain_notice":
      handlers.onDomainNotice?.(data as SSEDomainNoticeEvent);
      break;
    case "emotion":
      handlers.onEmotion?.(data as SSEEmotionEvent);
      break;
    case "action_text":
      handlers.onActionText?.(data as SSEActionTextEvent);
      break;
    default:
      console.warn(`[SSE] Unknown event type: ${eventType}`);
  }
}
