# Gemini API Key Test Report

> Date: 2026-03-26T19:31:03Z
> Mode: full
> Model: `gemini-3.1-flash-lite-preview`
> Embedding Model: `models/gemini-embedding-001`
> API Key: `AIzaSy...6-sQ`

## Summary

- Successes: `14`
- Failures: `1`
- Total elapsed: `30180.63 ms`

## Results

### PASS — models.list

- Elapsed: `361.65 ms`
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

- Elapsed: `94.32 ms`
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

- Elapsed: `62.76 ms`
- Details:
```json
{
  "total_tokens": 28
}
```

### PASS — generate_text_vi:gemini-3.1-flash-lite-preview

- Elapsed: `1317.43 ms`
- Details:
```json
{
  "response_preview": "Chào bạn, tôi đang hoạt động bình thường. Rất vui được hỗ trợ bạn!",
  "response_length": 66,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=18 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### PASS — generate_text_vi:gemini-2.5-flash

- Elapsed: `1450.65 ms`
- Details:
```json
{
  "response_preview": "Chào bạn! Tôi đang hoạt động bình thường.",
  "response_length": 41,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=10 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### FAIL — generate_text_vi:gemini-2.0-flash

- Elapsed: `281.11 ms`
- Error: `ClientError: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.0-flash is no longer available to new users. Please update your code to use a newer model for the latest features and improvements.', 'status': 'NOT_FOUND'}}`
- Details:
```json
{
  "traceback": "Traceback (most recent call last):\n  File \"E:\\Sach\\Sua\\AI_v1\\maritime-ai-service\\scripts\\test_gemini_api_key.py\", line 208, in run_case\n    details = fn()\n  File \"E:\\Sach\\Sua\\AI_v1\\maritime-ai-service\\scripts\\test_gemini_api_key.py\", line 263, in _call\n    response = client.models.generate_content(\n        model=model,\n        contents=DEFAULT_PROMPT,\n        config=types.GenerateContentConfig(temperature=0.2),\n    )\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\models.py\", line 5474, in generate_content\n    response = self._generate_content(\n        model=model, contents=contents, config=parsed_config\n    )\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\models.py\", line 4214, in _generate_content\n    response = self._api_client.request(\n        'post', path, request_dict, http_options\n    )\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\_api_client.py\", line 1386, in request\n    response = self._request(http_request, http_options, stream=False)\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\_api_client.py\", line 1222, in _request\n    return self._retry(self._request_once, http_request, stream)  # type: ignore[no-any-return]\n           ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\ngoogle.genai.errors.ClientError: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.0-flash is no longer available to new users. Please update your code to use a newer model for the latest features and improvements.', 'status': 'NOT_FOUND'}}\n"
}
```

### PASS — generate_stream

- Elapsed: `2230.61 ms`
- Details:
```json
{
  "chunk_count": 8,
  "response_preview": "Dưới đây là đoạn văn 4 câu giải thích tầm quan trọng của việc kết hợp smoke test và load test cho API key: Smoke test giúp xác nhận API key hoạt động đúng chức năng cơ bản và có quyền truy cập hợp lệ ngay từ bước đầu. Tuy nhiên, chỉ kiểm tra tính năng là ch...",
  "response_length": 607
}
```

### PASS — structured_json

- Elapsed: `2051.47 ms`
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

- Elapsed: `3877.17 ms`
- Details:
```json
{
  "response_preview": "Dưới đây là 2 câu về lợi ích của tư duy có chủ đích (deliberate reasoning): 1. Tư duy có chủ đích giúp chúng ta vượt qua những định kiến và cảm xúc nhất thời để đưa ra các quyết định sáng suốt, logic và chính xác hơn...."
}
```

### PASS — thinking_level:minimal

- Elapsed: `2047.05 ms`
- Details:
```json
{
  "level": "minimal",
  "response_preview": "Việc phân biệt giữa **thinking** (quá trình suy luận logic để giải quyết vấn đề) và **debug trace** (quá trình ghi lại các bước thực thi kỹ thuật) giúp hệ thống tách biệt giữa tư duy chiến lược và việc kiểm tra lỗi vậ...",
  "candidate_count": 1
}
```

### PASS — thinking_level:medium

- Elapsed: `3087.86 ms`
- Details:
```json
{
  "level": "medium",
  "response_preview": "Việc phân biệt giúp người dùng tập trung vào quá trình tư duy logic để giải quyết vấn đề mà không bị xao nhãng bởi các thông tin kỹ thuật phức tạp. Đồng thời, nó cho phép nhà phát triển truy vết lỗi hệ thống một cách ...",
  "candidate_count": 1
}
```

### PASS — thinking_level:high

- Elapsed: `6093.70 ms`
- Details:
```json
{
  "level": "high",
  "response_preview": "\"Thinking\" là quá trình suy luận logic để giải quyết vấn đề, trong khi \"debug trace\" là dữ liệu kỹ thuật dùng để chẩn đoán lỗi hệ thống. Việc tách biệt hai thành phần này giúp ngăn chặn rò rỉ thông tin nhạy cảm và đảm...",
  "candidate_count": 1
}
```

### PASS — embeddings_document_batch

- Elapsed: `363.43 ms`
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

- Elapsed: `2101.94 ms`
- Details:
```json
{
  "response_preview": "Màu chủ đạo của ảnh là màu vàng và có ký tự \"WIII\" ở bên trong.",
  "response_length": 63
}
```

### PASS — burst_probe

- Elapsed: `4225.89 ms`
- Details:
```json
{
  "requests": 10,
  "concurrency": 4,
  "successes": 10,
  "failures": 0,
  "sample_failure": null,
  "mean_latency_ms": 1417.22,
  "p95_latency_ms": 1655.89
}
```
