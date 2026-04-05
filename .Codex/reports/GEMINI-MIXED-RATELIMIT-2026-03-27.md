# Gemini API Key Test Report

> Date: 2026-03-26T19:41:25Z
> Mode: full
> Model: `gemini-3.1-flash-lite-preview`
> Embedding Model: `models/gemini-embedding-001`
> API Key: `AIzaSy...6-sQ`

## Summary

- Successes: `15`
- Failures: `0`
- Total elapsed: `102201.86 ms`

## Results

### PASS — models.list

- Elapsed: `381.30 ms`
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

- Elapsed: `82.13 ms`
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

- Elapsed: `70.18 ms`
- Details:
```json
{
  "total_tokens": 28
}
```

### PASS — generate_text_vi:gemini-3.1-flash-lite-preview

- Elapsed: `1305.52 ms`
- Details:
```json
{
  "response_preview": "Chào bạn, tôi đang hoạt động bình thường. Rất vui được hỗ trợ bạn!",
  "response_length": 66,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=18 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### PASS — generate_text_vi:gemini-2.5-flash

- Elapsed: `5244.63 ms`
- Details:
```json
{
  "response_preview": "Chào bạn! Tôi đang hoạt động bình thường.",
  "response_length": 41,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=10 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### PASS — generate_stream

- Elapsed: `2471.05 ms`
- Details:
```json
{
  "chunk_count": 8,
  "response_preview": "Dưới đây là đoạn văn 4 câu giải thích tầm quan trọng của việc kết hợp smoke test và load test cho API key: Kiểm thử Smoke giúp xác nhận API key hoạt động ổn định và có quyền truy cập đúng ngay từ bước đầu tiên. Trong khi đó, Load test lại đảm bảo rằng key v...",
  "response_length": 572
}
```

### PASS — structured_json

- Elapsed: `1498.99 ms`
- Details:
```json
{
  "raw_preview": "{ \"summary\": \"Thị trường dầu mỏ đang chịu áp lực từ lo ngại suy thoái kinh tế toàn cầu và nguồn cung dồi dào từ các quốc gia ngoài OPEC. Tuy nhiên, các căng thẳng địa chính trị tại Trung Đông vẫn duy trì mức giá hỗ tr...",
  "parsed": {
    "summary": "Thị trường dầu mỏ đang chịu áp lực từ lo ngại suy thoái kinh tế toàn cầu và nguồn cung dồi dào từ các quốc gia ngoài OPEC. Tuy nhiên, các căng thẳng địa chính trị tại Trung Đông vẫn duy trì mức giá hỗ trợ nhất định cho mặt hàng này.",
    "risk_level": "medium",
    "confidence": 0.95
  }
}
```

### PASS — thinking_budget_probe

- Elapsed: `3423.09 ms`
- Details:
```json
{
  "response_preview": "Dưới đây là 2 câu về lợi ích của tư duy có chủ đích (deliberate reasoning): 1. Tư duy có chủ đích giúp chúng ta vượt qua những định kiến và cảm xúc nhất thời để đưa ra các quyết định sáng suốt, logic hơn trong những t..."
}
```

### PASS — thinking_level:minimal

- Elapsed: `1668.29 ms`
- Details:
```json
{
  "level": "minimal",
  "response_preview": "Việc phân biệt giữa **thinking** (quá trình suy luận logic để giải quyết vấn đề) và **debug trace** (quá trình ghi lại các bước thực thi kỹ thuật) giúp hệ thống tách biệt giữa tư duy chiến lược và việc kiểm tra lỗi vậ...",
  "candidate_count": 1
}
```

### PASS — thinking_level:medium

- Elapsed: `7100.34 ms`
- Details:
```json
{
  "level": "medium",
  "response_preview": "Việc phân biệt giữa suy luận (thinking) và nhật ký lỗi (debug trace) giúp tách biệt quá trình tư duy logic của AI với các thông tin kỹ thuật hệ thống, từ đó đảm bảo người dùng chỉ nhận được kết quả phản hồi mạch lạc t...",
  "candidate_count": 1
}
```

### PASS — thinking_level:high

- Elapsed: `6813.81 ms`
- Details:
```json
{
  "level": "high",
  "response_preview": "Việc phân biệt giúp tách biệt quá trình suy luận logic dành cho người dùng với các thông tin kỹ thuật nội bộ, đảm bảo câu trả lời luôn rõ ràng và dễ hiểu. Đồng thời, điều này ngăn chặn việc rò rỉ các dữ liệu hệ thống ...",
  "candidate_count": 1
}
```

### PASS — embeddings_document_batch

- Elapsed: `351.59 ms`
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

### PASS — multimodal_image_understanding

- Elapsed: `2611.10 ms`
- Details:
```json
{
  "response_preview": "Màu chủ đạo của ảnh là màu vàng và có ký tự \"WIII\" ở bên trong.",
  "response_length": 63
}
```

### PASS — burst_probe

- Elapsed: `4141.07 ms`
- Details:
```json
{
  "requests": 10,
  "concurrency": 4,
  "successes": 10,
  "failures": 0,
  "sample_failure": null,
  "mean_latency_ms": 1418.05,
  "p95_latency_ms": 2046.95
}
```

### PASS — mixed_text_embedding_rate_limit_probe

- Elapsed: `65025.95 ms`
- Details:
```json
{
  "rounds": 8,
  "concurrency": 6,
  "text_models": [
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-pro-preview"
  ],
  "embedding_model": "models/gemini-embedding-001",
  "thinking_levels": [
    "medium",
    "high"
  ],
  "total_jobs": 40,
  "successes": 40,
  "failures": 0,
  "rate_limit_failures": 0,
  "sample_failure": null,
  "per_lane": {
    "text": {
      "count": 32,
      "mean_latency_ms": 10785.06,
      "p95_latency_ms": 30037.41
    },
    "embedding": {
      "count": 8,
      "mean_latency_ms": 358.1,
      "p95_latency_ms": 412.26
    }
  },
  "per_model": {
    "gemini-3.1-flash-lite-preview": {
      "successes": 16,
      "failures": 0,
      "mean_latency_ms": 6296.9,
      "p95_latency_ms": 7888.06
    },
    "gemini-3.1-pro-preview": {
      "successes": 16,
      "failures": 0,
      "mean_latency_ms": 15273.22,
      "p95_latency_ms": 31436.43
    },
    "models/gemini-embedding-001": {
      "successes": 8,
      "failures": 0,
      "mean_latency_ms": 358.1,
      "p95_latency_ms": 412.26
    }
  }
}
```
