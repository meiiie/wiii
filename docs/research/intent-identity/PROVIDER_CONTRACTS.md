# Provider contract facts used as evidence (accessed 2026-09-19)

Each entry quotes the official documentation verbatim where it matters, then
states the profile assignment used in the study. Quotes were fetched during
this research session; re-verify before submission because vendors change
documentation without notice.

## Stripe — Idempotent requests

Source: <https://docs.stripe.com/api/idempotent_requests>

- "Stripe's idempotency works by saving the resulting status code and body of
  the first request made for any given idempotency key, regardless of whether
  it succeeds or fails."
- "You can remove keys from the system automatically after they're at least
  24 hours old. We generate a new request if a key is reused after the
  original is pruned."
- "The idempotency layer compares incoming parameters to those of the original
  request and errors if they're not the same to prevent accidental misuse."
- "We save results only after the execution of an endpoint begins."

Profile: `P_D(T)` with `T >= 24 h`, immutable key/payload binding, per-request
key scope, single-object requests (atomic class). The post-window downgrade
is to a lookup-capable profile if the created objects remain retrievable via
list endpoints; that retrieval path was not exercised in this session.

## Amazon SQS — Message deduplication ID (FIFO)

Source: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/using-messagededuplicationid-property.html>

- "`MessageDeduplicationId` is a token used only in Amazon SQS FIFO queues to
  prevent duplicate message delivery. It ensures that within a 5-minute
  deduplication window, only one instance of a message with the same
  deduplication ID is processed and delivered."
- "Amazon SQS continues tracking the deduplication ID even after the message
  has been received and deleted."

Profile: `P_D(T)` with `T = 5 min`, per-entry key scope. No lookup by
deduplication ID exists, so the post-window downgrade is to `P_O`.

## Amazon SQS — SendMessageBatch

Source: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SendMessageBatch.html>

- "The result of sending each message is reported individually in the
  response. Because the batch request can result in a combination of
  successful and unsuccessful actions, you should check for batch errors even
  when the call returns an HTTP status code of 200."
- "For a FIFO queue, multiple messages within a single batch are enqueued in
  the order they are sent."

Batch class: independent (per-entry outcomes).

## Amazon SES v2 — SendBulkEmail

Source: <https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_SendBulkEmail.html>

- Response `BulkEmailEntryResults`: "One object per intended recipient. Check
  each response object and retry any messages with a failure status."

Batch class: independent (per-destination outcomes). No idempotency key is
documented for the send operation.

## Slack — chat.postMessage and conversations.history

Sources: <https://api.slack.com/methods/chat.postMessage>,
<https://api.slack.com/methods/conversations.history>

- `chat.postMessage` documents no idempotency argument. Its error table for
  `fatal_error` and `internal_error` states: "It's possible some aspect of
  the operation succeeded before the error was raised."
- `conversations.history` "Fetches a conversation's history of messages and
  events." "As of May 29, 2025, for new applications and installation
  commercially distributed outside of the Marketplace, this method is rate
  limited to 1 request per minute. The maximum and default values for the
  `limit` parameter have both been reduced to 15 objects."

Profile: `P_O` for the write, with a rate-limited evidence contract. This is
the vendor-documented form of the opaque-outcome ambiguity and of a non-trivial
evidence cost.

## Temporal — Activities

Source: <https://docs.temporal.io/activities>

- "We recommend that it be idempotent, so retries can be processed without
  duplicate side effects."
- "If an Activity attempt fails, it is automatically retried using its Retry
  Policy. Each attempt starts from the initial state, unless your code uses a
  Heartbeat detail payload for checkpointing."

Interpretation: the durable-execution engine delegates effect deduplication to
the provider; it is the strong stable-key reference as deployed, and it
inherits the provider's retention window.

## Not verified in this session

- Kafka idempotent-producer ordering (documentation page redirected; not
  quoted).
- GitHub REST issue creation: the fetched reference page documents no
  idempotency key argument, but this negative observation was not exhaustively
  checked and is not used as evidence in the paper.
