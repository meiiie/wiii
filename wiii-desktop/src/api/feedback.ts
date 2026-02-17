/**
 * Feedback API module — Sprint 107.
 * Sends message rating (thumbs up/down) to backend.
 */
import { getClient } from "./client";

export type FeedbackRating = "up" | "down";

interface FeedbackRequest {
  message_id: string;
  session_id: string;
  rating: FeedbackRating;
  comment?: string;
}

interface FeedbackResponse {
  status: string;
  message_id: string;
  rating: FeedbackRating;
}

/** Submit feedback for an AI message. Fire-and-forget safe. */
export async function submitFeedback(
  messageId: string,
  sessionId: string,
  rating: FeedbackRating,
  comment?: string
): Promise<FeedbackResponse> {
  const client = getClient();
  const body: FeedbackRequest = {
    message_id: messageId,
    session_id: sessionId,
    rating,
    comment,
  };
  return client.post<FeedbackResponse>("/api/v1/feedback", body);
}
