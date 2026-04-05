# Gemini API Key Test Report

> Date: 2026-03-26T19:29:12Z
> Mode: smoke
> Model: `gemini-3.1-flash-lite-preview`
> Embedding Model: `models/gemini-embedding-001`
> API Key: `AIzaSy...6-sQ`

## Summary

- Successes: `12`
- Failures: `0`
- Total elapsed: `22244.77 ms`

## Results

### PASS — models.list

- Elapsed: `509.22 ms`
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

- Elapsed: `87.74 ms`
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

- Elapsed: `58.37 ms`
- Details:
```json
{
  "total_tokens": 28
}
```

### PASS — generate_text_vi:gemini-3.1-flash-lite-preview

- Elapsed: `1268.60 ms`
- Details:
```json
{
  "response_preview": "Chào bạn, tôi đang hoạt động bình thường. Rất vui được hỗ trợ bạn!",
  "response_length": 66,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=18 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### PASS — generate_stream

- Elapsed: `1795.36 ms`
- Details:
```json
{
  "chunk_count": 8,
  "response_preview": "Dưới đây là đoạn văn 4 câu giải thích tầm quan trọng của việc kết hợp smoke test và load test cho API key: Kiểm thử API key cần thực hiện smoke test để đảm bảo các chức năng xác thực cơ bản hoạt động ổn định trước khi triển khai sâu hơn. Bên cạnh đó, load t...",
  "response_length": 610
}
```

### PASS — structured_json

- Elapsed: `1408.37 ms`
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

- Elapsed: `2814.35 ms`
- Details:
```json
{
  "response_preview": "Dưới đây là 2 câu về lợi ích của tư duy có chủ đích (deliberate reasoning): 1. Tư duy có chủ đích giúp chúng ta vượt qua những định kiến và cảm xúc nhất thời, từ đó đưa ra những quyết định sáng suốt và logic hơn. 2. B..."
}
```

### PASS — thinking_level:minimal

- Elapsed: `1738.61 ms`
- Details:
```json
{
  "level": "minimal",
  "response_preview": "Việc phân biệt giữa **thinking** (quá trình suy luận logic để giải quyết vấn đề) và **debug trace** (quá trình ghi lại các bước thực thi kỹ thuật) giúp hệ thống tách biệt giữa tư duy chiến lược và việc kiểm tra lỗi vậ...",
  "candidate_count": 1
}
```

### PASS — thinking_level:medium

- Elapsed: `3687.34 ms`
- Details:
```json
{
  "level": "medium",
  "response_preview": "Việc phân biệt giữa \"thinking\" và \"debug trace\" giúp AI tập trung vào quá trình suy luận logic để giải quyết vấn đề thay vì làm nhiễu người dùng bằng các thông tin kỹ thuật không cần thiết. Đồng thời, việc tách biệt n...",
  "candidate_count": 1
}
```

### PASS — thinking_level:high

- Elapsed: `5539.47 ms`
- Details:
```json
{
  "level": "high",
  "response_preview": "Phân biệt giữa \"thinking\" và \"debug trace\" giúp người dùng tập trung vào logic giải quyết vấn đề thay vì bị nhiễu bởi các thông tin kỹ thuật phức tạp. Ngoài ra, việc tách biệt này còn đảm bảo an toàn bằng cách ngăn ch...",
  "candidate_count": 1
}
```

### PASS — embeddings_document_batch

- Elapsed: `370.71 ms`
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

- Elapsed: `2950.96 ms`
- Details:
```json
{
  "requests": 4,
  "concurrency": 2,
  "successes": 4,
  "failures": 0,
  "sample_failure": null,
  "mean_latency_ms": 1456.25,
  "p95_latency_ms": 1601.3
}
```
