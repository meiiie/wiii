# Stream Answer Authority Sync Parity

Date: 2026-03-31

## Goal

Đưa `tutor` stream về cùng answer authority với `sync`:

- Stream vẫn giữ `thinking` và `tool trace`
- Tutor không còn tự đẩy final `answer_delta` sớm
- `synthesizer.final_response` trở thành câu trả lời cuối trên stream

## Code Changes

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
  - bỏ việc tutor tự push `answer_delta`/bulk answer ở `_react_loop()`
  - bỏ propagation `_answer_streamed_via_bus` từ `process()`
  - giữ tuple legacy để tương thích, nhưng flag answer-streamed của tutor luôn là compatibility-only

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_stream_dispatch_runtime.py`
  - nhánh `tutor_agent` không còn emit `tutor_output` như final answer
  - giữ `thinking`/`tool_call`/`tool_result`
  - hold tutor response cho tới `synthesizer`

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_stream_merge_runtime.py`
  - thêm suppression rule ở merge layer:
    - nếu có `answer_delta` từ `tutor_agent`, drop luôn trước khi ra SSE
  - drain logic cũng áp cùng suppression này để không còn race path cũ lách qua lúc `graph_done`

## Tests

Focused suites:

- `maritime-ai-service/tests/unit/test_sprint74_streaming_quality.py`
- `maritime-ai-service/tests/unit/test_thinking_lifecycle.py`
- `maritime-ai-service/tests/unit/test_tutor_agent_node.py`
- `maritime-ai-service/tests/unit/test_sprint150_answer_drain.py`

Result:

- `105 passed` (batch chính)
- `5 passed` (drain/suppression regression)

## Live Probe

Artifacts:

- JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\stream-answer-authority-probe-2026-03-31-034109.json`
- HTML: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest.html`
- Raw stream: `E:\Sach\Sua\AI_v1\.Codex\reports\stream-authority-stream-rule15-2026-03-31-034109.txt`

Important runtime note:

- lỗi probe trước không phản ánh patch vì cổng `8000` đang bị một process Python cũ giữ
- sau khi dừng process cũ và restart lại đúng `.venv\\Scripts\\python.exe -m uvicorn ...`, live stream mới phản ánh code hiện tại

## Current Truth

Đã fix đúng:

- `stream_rule15.answer_before_synth = false`
- `stream_visual_followup.answer_before_synth = false`
- tức là stream không còn emit câu trả lời của tutor trước status `synthesizer`
- tool trace và thinking trace vẫn giữ nguyên, chỉ chặn đúng final answer sớm từ tutor

Chưa xong:

- `stream_rule15.thinking` vẫn còn lẫn block tiếng Anh native thought
- `stream_visual_followup.thinking` cũng còn tiếng Anh khá dài
- `sync` vẫn nghe “Wiii” hơn `stream` ở surface cuối
- raw `tool_result`/research trace hiện đã được giữ, nên UI có thể tiếp tục soi chính xác hơn thay vì bị answer chèn lên trước

## Next Best Step

Tập trung lại vào `thinking authority/quality` của stream:

1. căn visible thinking về ngôn ngữ user khi native thought trượt sang tiếng Anh
2. giữ raw research trace nhưng phân biệt rõ thinking với tool/report text
3. sau đó mới tune Soul/Wiii voice cho visible stream thinking
