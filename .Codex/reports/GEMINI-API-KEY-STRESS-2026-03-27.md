# Gemini API Key Test Report

> Date: 2026-03-26T19:32:42Z
> Mode: stress
> Model: `gemini-3.1-flash-lite-preview`
> Embedding Model: `models/gemini-embedding-001`
> API Key: `AIzaSy...6-sQ`

## Summary

- Successes: `13`
- Failures: `0`
- Total elapsed: `28877.42 ms`

## Results

### PASS — models.list

- Elapsed: `348.35 ms`
- Details:
```json
{
  "listed_count": 48,
  "first_models": [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-pro",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-001",
    "models/gemini-2.0-flash-lite-001",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.5-flash-preview-tts",
    "models/gemini-2.5-pro-preview-tts",
    "models/gemma-3-1b-it",
    "models/gemma-3-4b-it"
  ],
  "target_model_seen_in_first_page": false
}
```

### PASS — models.get

- Elapsed: `73.48 ms`
- Details:
```json
{
  "name": "models/gemini-3.1-flash-lite-preview",
  "display_name": "Gemini 3.1 Flash Lite Preview",
  "description": "Gemini 3.1 Flash Lite Preview",
  "input_token_limit": 1048576,
  "output_token_limit": 65536
}
```

### PASS — count_tokens

- Elapsed: `71.54 ms`
- Details:
```json
{
  "total_tokens": 28
}
```

### PASS — generate_text_vi:gemini-3.1-flash-lite-preview

- Elapsed: `1287.09 ms`
- Details:
```json
{
  "response_preview": "Chào bạn, tôi đang hoạt động bình thường. Rất vui được hỗ trợ bạn!",
  "response_length": 66,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=18 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### PASS — generate_text_vi:gemini-2.5-flash

- Elapsed: `1434.82 ms`
- Details:
```json
{
  "response_preview": "Chào bạn! Tôi đang hoạt động bình thường.",
  "response_length": 41,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=10 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### PASS — generate_stream

- Elapsed: `1853.13 ms`
- Details:
```json
{
  "chunk_count": 8,
  "response_preview": "Dưới đây là đoạn văn 4 câu giải thích tầm quan trọng của việc kết hợp smoke test và load test cho API key: Kiểm thử Smoke giúp xác nhận API key hoạt động ổn định và có quyền truy cập cơ bản ngay từ giai đoạn đầu tích hợp. Tuy nhiên, chỉ kiểm tra tính năng l...",
  "response_length": 605
}
```

### PASS — structured_json

- Elapsed: `1720.27 ms`
- Details:
```json
{
  "raw_preview": "{ \"summary\": \"Thị trường dầu mỏ đang chịu áp lực từ lo ngại suy thoái kinh tế toàn cầu và nguồn cung dồi dào từ các quốc gia ngoài OPEC. Tuy nhiên, các biện pháp cắt giảm sản lượng của OPEC+ vẫn đóng vai trò là yếu tố...",
  "parsed": {
    "summary": "Thị trường dầu mỏ đang chịu áp lực từ lo ngại suy thoái kinh tế toàn cầu và nguồn cung dồi dào từ các quốc gia ngoài OPEC. Tuy nhiên, các biện pháp cắt giảm sản lượng của OPEC+ vẫn đóng vai trò là yếu tố hỗ trợ giá dầu không giảm sâu.",
    "risk_level": "medium",
    "confidence": 0.95
  }
}
```

### PASS — thinking_budget_probe

- Elapsed: `3512.23 ms`
- Details:
```json
{
  "response_preview": "Dưới đây là 2 câu về lợi ích của tư duy có chủ đích (deliberate reasoning): 1. Tư duy có chủ đích giúp chúng ta vượt qua những định kiến và cảm xúc nhất thời, từ đó đưa ra những quyết định sáng suốt và chính xác hơn. ..."
}
```

### PASS — thinking_level:minimal

- Elapsed: `1040.21 ms`
- Details:
```json
{
  "level": "minimal",
  "response_preview": "Việc phân biệt giữa **thinking** (quá trình suy luận logic để giải quyết vấn đề) và **debug trace** (quá trình kiểm tra lỗi kỹ thuật) giúp AI duy trì sự tập trung vào mục tiêu cốt lõi mà không bị nhiễu bởi các thông t...",
  "candidate_count": 1
}
```

### PASS — thinking_level:medium

- Elapsed: `5480.77 ms`
- Details:
```json
{
  "level": "medium",
  "response_preview": "Việc phân biệt giữa \"thinking\" và \"debug trace\" giúp tách biệt quá trình tư duy logic của AI khỏi các dữ liệu kỹ thuật rườm rà, đảm bảo người dùng nhận được câu trả lời rõ ràng mà không bị nhiễu bởi thông tin vận hành...",
  "candidate_count": 1
}
```

### PASS — thinking_level:high

- Elapsed: `6760.13 ms`
- Details:
```json
{
  "level": "high",
  "response_preview": "\"Thinking\" là quá trình suy luận logic để tạo ra câu trả lời tối ưu cho người dùng, trong khi \"debug trace\" là dữ liệu kỹ thuật nhằm mục đích theo dõi và sửa lỗi hệ thống. Việc phân tách rõ ràng hai luồng này giúp bảo...",
  "candidate_count": 1
}
```

### PASS — embeddings_document_batch

- Elapsed: `342.54 ms`
- Details:
```json
{
  "embedding_count": 2,
  "dimensions": [
    768,
    768
  ]
}
```

### PASS — burst_probe

- Elapsed: `4944.60 ms`
- Details:
```json
{
  "requests": 24,
  "concurrency": 8,
  "successes": 24,
  "failures": 0,
  "sample_failure": null,
  "mean_latency_ms": 1431.0,
  "p95_latency_ms": 1787.14
}
```
