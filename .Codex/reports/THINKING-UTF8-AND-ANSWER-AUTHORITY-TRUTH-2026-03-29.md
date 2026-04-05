# Thinking UTF-8 And Answer Authority Truth

Date: 2026-03-29
Scope: analytical prompts on local Wiii stack after refactor + runtime parity fixes

## Executive Summary

The earlier conclusion that analytical prompts like `Phân tích giá dầu` or `Phân tích về toán học con lắc đơn` still produced generic gray-rail thinking was only partially true.

After retesting with Unicode-safe requests, the direct analytical thinking path is working.

The real current blockers are:

1. false positives caused by PowerShell mangling Vietnamese Unicode into `?`
2. routing nondeterminism between repeated requests
3. stream answer authority drift: some direct-lane streaming runs surface analytical thinking but finish without a final visible answer

## What Was Verified

### 1. Helper-level analytical thinking works

Using Unicode-safe `\u`-escaped prompts:

- `Phân tích giá dầu`
  - `thinking_mode = analytical_market`
  - `topic_hint = giá dầu`
- `Phân tích về toán học con lắc đơn`
  - `thinking_mode = analytical_math`
  - `topic_hint = con lắc đơn`

Deterministic narrator output is analytical and domain-shaped, not relational generic.

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-inproc-escaped-2026-03-29.json`

### 2. In-process sync graph path works with Unicode-safe prompts

`process_with_multi_agent()` with escaped prompts produced analytical final `thinking_content`.

Oil example:

```text
Câu này chạm vào giá dầu, mà phần khó không nằm ở một con số đơn lẻ mà ở việc tách đúng những lực đang kéo giá theo các hướng khác nhau.

Mình muốn nhìn riêng OPEC+ và sản lượng, tồn kho và nhịp cung cầu, và địa chính trị trước khi chốt nhận định.

Mình đã có một khung đủ chắc để đọc giá dầu không chỉ như biến động giá, mà như kết quả của nhiều lực kéo cùng lúc.

Giờ mình sẽ nối OPEC+ và sản lượng, tồn kho và nhịp cung cầu, và địa chính trị thành một mạch dễ theo.
```

Math example:

```text
Con lắc đơn nhìn vậy thôi chứ chỗ dễ trượt không nằm ở công thức cuối, mà ở việc chọn đúng mô hình ngay từ đầu.

Mình sẽ giữ riêng mô hình lý tưởng, giả định góc nhỏ, và phương trình dao động trước để mạch phân tích không bị nhảy cóc.

Mình đã có đủ khung để nói về con lắc đơn như một hệ động lực, không chỉ như một công thức cần chép lại.

Giờ mình sẽ nối mô hình, giả định, và kết quả thành một mạch sáng hơn.
```

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-inproc-escaped-2026-03-29.json`

### 3. HTTP sync path also works with Unicode-safe prompts

`/api/v1/chat` with escaped prompts returned `200` and analytical `thinking_content`.

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-sync-httpx-escaped-2026-03-29.json`

### 4. Browser UI on localhost:1420 shows analytical thinking on the real surface

Using local dev mode + API key login on `http://localhost:1420`, the UI gray rail for `Phân tích giá dầu` shows analytical text, not the older relational generic fallback.

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\ui-localhost-1420-after-api-login-2026-03-29.png`
- `E:\Sach\Sua\AI_v1\.Codex\reports\ui-localhost-1420-chat-oil-2026-03-29.png`
- `E:\Sach\Sua\AI_v1\.Codex\reports\ui-localhost-1420-chat-oil-2026-03-29.txt`

## False Positive That Misled Earlier Diagnosis

When Python was piped through PowerShell using raw Vietnamese literals, the prompt text was transformed into strings like:

```text
Ph?n t?ch gi? d?u
```

That destroyed analytical keyword recognition and made the system look generic.

This explains why some earlier CLI-based checks incorrectly concluded:

- `thinking_mode = ""`
- relational generic opening
- visual/generic synthesize beat

Those conclusions were valid for corrupted text, not for true UTF-8 requests.

## New Real Problem

### Stream answer authority is still unstable

For the same oil-analysis family of prompts, there are now at least two real behaviors:

1. sync HTTP can return:
   - analytical thinking
   - full final answer
2. stream HTTP / UI can sometimes show:
   - analytical thinking
   - but no final visible answer

Observed stream symptom:

- metadata showed `response_length = 0`
- UI showed only the analytical thinking rail and no answer bubble

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-stream-httpx-oil-escaped-2026-03-29.txt`
- `E:\Sach\Sua\AI_v1\.Codex\reports\ui-localhost-1420-chat-oil-2026-03-29.png`

This is a real answer-surface bug, not a Unicode false positive.

## Additional Finding: Routing Is Not Stable Enough

Repeated runs of essentially the same analytical oil prompt can land in different lanes:

- direct
- rag_agent

Examples seen during this session:

- HTTP sync escaped run: `final_agent = direct`
- in-process streaming escaped run: `final_agent = rag_agent`

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-stream-direct-extract-probe-2026-03-29.json`

This means current behavior is still influenced by routing nondeterminism, which directly affects:

- the style of thinking surfaced
- whether answer is streamed early or synthesized later
- whether final metadata is authoritative

## Current Backend Truth

The current truthful state is:

- analytical thinking generation is working
- public thinking authority is cleaner than before
- CLI-based non-escaped Vietnamese tests were misleading
- answer authority on stream is still not reliable
- routing for analytical prompts is still too unstable

## Recommended Next Fix Order

1. Stabilize routing for analytical prompts
   - same prompt family should not bounce between `direct` and `rag_agent`
2. Fix stream answer authority
   - if direct node finishes with empty `final_response`, stream path needs deterministic recovery
3. Only then continue polishing analytical thinking richness
   - because current analytical wording is already substantially better than the earlier generic relational fallback

