# Gemini API Key Test Report

> Date: 2026-03-27T11:50:11Z
> Mode: smoke
> Model: `gemini-3.1-flash-lite-preview`
> Embedding Model: `models/gemini-embedding-001`
> API Key: `AIzaSy...6-sQ`

## Summary

- Successes: `12`
- Failures: `1`
- Total elapsed: `47534.89 ms`

## Results

### FAIL — models.list

- Elapsed: `11356.80 ms`
- Error: `ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)`
- Details:
```json
{
  "traceback": "Traceback (most recent call last):\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\httpx\\_transports\\default.py\", line 101, in map_httpcore_exceptions\n    yield\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\httpx\\_transports\\default.py\", line 250, in handle_request\n    resp = self._pool.handle_request(req)\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\httpcore\\_sync\\connection_pool.py\", line 256, in handle_request\n    raise exc from None\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\httpcore\\_sync\\connection_pool.py\", line 236, in handle_request\n    response = connection.handle_request(\n        pool_request.request\n    )\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\httpcore\\_sync\\connection.py\", line 101, in handle_request\n    raise exc\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\httpcore\\_sync\\connection.py\", line 78, in handle_request\n    stream = self._connect(request)\nhttpcore.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)\n\nThe above exception was the direct cause of the following exception:\n\nTraceback (most recent call last):\n  File \"E:\\Sach\\Sua\\AI_v1\\maritime-ai-service\\scripts\\test_gemini_api_key.py\", line 230, in run_case\n    details = fn()\n  File \"E:\\Sach\\Sua\\AI_v1\\maritime-ai-service\\scripts\\test_gemini_api_key.py\", line 246, in _list_models\n    pager = client.models.list(config=types.ListModelsConfig(page_size=20))\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\models.py\", line 6039, in list\n    self._list(config=config),\n    ~~~~~~~~~~^^^^^^^^^^^^^^^\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\models.py\", line 4939, in _list\n    response = self._api_client.request('get', path, request_dict, http_options)\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\_api_client.py\", line 1386, in request\n    response = self._request(http_request, http_options, stream=False)\n  File \"C:\\Users\\Admin\\AppData\\Roaming\\Python\\Python313\\site-packages\\google\\genai\\_api_client.py\", line 1222, in _request\n    return self._retry(self._request_once, http_request, stream)  # type: ignore[no-any-return]\n           ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\nhttpx.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)\n"
}
```

### PASS — models.get

- Elapsed: `1566.03 ms`
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

- Elapsed: `658.73 ms`
- Details:
```json
{
  "total_tokens": 28
}
```

### PASS — generate_text_vi:gemini-3.1-flash-lite-preview

- Elapsed: `1830.56 ms`
- Details:
```json
{
  "response_preview": "Chào bạn, tôi đang hoạt động bình thường. Rất vui được hỗ trợ bạn!",
  "response_length": 66,
  "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=18 candidates_tokens_details=None prompt_token_count=18 prompt_tokens_details=[ModalityTokenCoun..."
}
```

### PASS — generate_stream

- Elapsed: `3744.99 ms`
- Details:
```json
{
  "chunk_count": 9,
  "response_preview": "Dưới đây là đoạn văn 4 câu giải thích tầm quan trọng của việc kết hợp smoke test và load test cho API key: Kiểm thử Smoke giúp xác nhận API key hoạt động ổn định và có quyền truy cập đúng ngay từ bước đầu tiên. Trong khi đó, Load test lại đóng vai trò then ...",
  "response_length": 693
}
```

### PASS — structured_json

- Elapsed: `2427.19 ms`
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

- Elapsed: `3905.21 ms`
- Details:
```json
{
  "response_preview": "Dưới đây là 2 câu về lợi ích của tư duy có chủ đích (deliberate reasoning): 1. Tư duy có chủ đích giúp chúng ta vượt qua những định kiến và cảm xúc nhất thời để đưa ra các quyết định sáng suốt, logic hơn trong những t..."
}
```

### PASS — thinking_level:minimal

- Elapsed: `2151.77 ms`
- Details:
```json
{
  "level": "minimal",
  "response_preview": "Việc phân biệt giữa **thinking** (quá trình suy luận logic để giải quyết vấn đề) và **debug trace** (quá trình kiểm tra lỗi kỹ thuật) giúp AI duy trì sự mạch lạc trong tư duy mà không bị nhiễu bởi các thông tin kỹ thu...",
  "candidate_count": 1
}
```

### PASS — thinking_level:medium

- Elapsed: `4845.90 ms`
- Details:
```json
{
  "level": "medium",
  "response_preview": "Việc phân biệt giữa \"thinking\" và \"debug trace\" giúp tách biệt quá trình suy luận logic của AI với các thông tin kỹ thuật vận hành, từ đó tối ưu hóa trải nghiệm người dùng bằng cách chỉ hiển thị những nội dung có giá ...",
  "candidate_count": 1
}
```

### PASS — thinking_level:high

- Elapsed: `7058.05 ms`
- Details:
```json
{
  "level": "high",
  "response_preview": "Việc phân biệt giúp tách biệt quá trình suy luận logic khỏi các dữ liệu kỹ thuật thô, từ đó ngăn chặn việc hiển thị thông tin thừa gây nhiễu cho người dùng cuối. Đồng thời, sự phân tách này cho phép nhà phát triển tru...",
  "candidate_count": 1
}
```

### PASS — embeddings_document_batch

- Elapsed: `539.33 ms`
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

- Elapsed: `2746.67 ms`
- Details:
```json
{
  "response_preview": "Màu chủ đạo của ảnh là màu vàng và có ký tự \"WIII\" ở bên trong.",
  "response_length": 63
}
```

### PASS — burst_probe

- Elapsed: `4518.13 ms`
- Details:
```json
{
  "requests": 4,
  "concurrency": 2,
  "successes": 4,
  "failures": 0,
  "sample_failure": null,
  "mean_latency_ms": 2043.26,
  "p95_latency_ms": 3319.86
}
```
