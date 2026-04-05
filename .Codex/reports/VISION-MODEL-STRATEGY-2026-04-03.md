# Vision Model Strategy

Date: 2026-04-03

## Decision

Wiii nên triển khai `vision` theo kiến trúc **capability-routed multimodal runtime**, không dùng một model duy nhất cho mọi việc.

## Why

Trong code hiện tại, runtime đã tách đúng 3 capability:

- `ocr_extract`
- `visual_describe`
- `grounded_visual_answer`

Tách model theo capability là hướng chuyên nghiệp nhất vì:

- OCR cần tối ưu document parsing, layout, bảng, công thức
- image description cần captioning / scene understanding
- grounded visual answer cần visual reasoning + instruction following

## Recommended Production Architecture

### Lane 1: OCR specialist

Mục tiêu:

- scan/PDF
- invoice/form
- handwriting
- tables
- formulas

Model khuyến nghị:

- Primary cloud: `Z.ai GLM-OCR`
- Primary local/open: `GLM-OCR` self-host hoặc GGUF nếu stack local cho phép

### Lane 2: General visual describe

Mục tiêu:

- mô tả ảnh cho Visual Memory
- enrich hình trong Visual RAG
- screenshot/app/image captioning

Model khuyến nghị:

- OpenRouter cloud balanced: `Qwen2.5-VL 7B`
- OpenRouter quality-first: `Qwen2.5-VL 32B`
- Ollama local balanced: `qwen2.5vl`
- Ollama lightweight fallback: `minicpm-v`

### Lane 3: Grounded visual answer

Mục tiêu:

- trả lời câu hỏi dựa trên ảnh
- đọc chart/screenshot trong ngữ cảnh user query
- instruction following trên visual input

Model khuyến nghị:

- OpenRouter quality-first: `Qwen2.5-VL 32B`
- OpenRouter cheaper fallback: `Qwen2.5-VL 7B`
- Ollama local: `qwen2.5vl`

## Open-Source Options Worth Taking Seriously

### Best OCR-specialist

- `GLM-OCR`
  - mạnh cho document parsing
  - nhẹ khoảng `0.9B`
  - có public ecosystem tốt

### Best general open vision

- `Qwen2.5-VL`
  - mạnh cả vision hiểu ảnh lẫn đọc text trong ảnh
  - có nhiều size phù hợp cloud và edge

### Best edge/local lightweight alternative

- `MiniCPM-V`
  - phù hợp local/edge
  - hợp cho captioning và visual QA mức vừa

### Legacy/general fallback only

- `LLaVA`
  - dễ chạy
  - tốt để có local vision nhanh
  - nhưng không nên là lựa chọn chất lượng chính cho tài liệu/OCR nghiêm túc

## What Not To Do

- Không dùng một VLM tổng quát duy nhất để gánh luôn OCR production.
- Không dùng OCR-specialist duy nhất để thay thế captioning / grounded visual reasoning.
- Không chọn model chỉ vì “cùng provider”, bỏ qua capability fit.

## Best Fit For Wiii Right Now

### Professional default

- `ocr_extract` -> `GLM-OCR`
- `visual_describe` -> `Qwen2.5-VL 7B`
- `grounded_visual_answer` -> `Qwen2.5-VL 32B`

### If local-first matters most

- `ocr_extract` -> `GLM-OCR` self-host / GGUF path
- `visual_describe` -> `qwen2.5vl`
- `grounded_visual_answer` -> `qwen2.5vl`
- fallback nhẹ -> `minicpm-v`

### If simplicity matters more than purity

- giữ một VLM chung cho `visual_describe + grounded_visual_answer`
- chỉ tách riêng `ocr_extract`

Đây là điểm cân bằng tốt nhất giữa chất lượng và độ phức tạp vận hành.

## Recommended Next Implementation

1. thêm `ocr-specialist contract` riêng trong `vision_runtime`
2. thêm policy:
   - `vision_provider_by_capability`
   - `vision_model_by_capability`
3. benchmark theo capability:
   - OCR docs/forms/tables/formulas
   - captioning screenshots/photos/diagrams
   - grounded QA trên chart/screenshot
4. chỉ sau benchmark mới promote provider/model thành default

## Sources

- [Z.AI Overview](https://docs.z.ai/guides/overview/overview)
- [Z.AI GLM-OCR](https://docs.z.ai/guides/vlm/glm-ocr)
- [Z.AI Layout Parsing API](https://docs.z.ai/api-reference/tools/layout-parsing)
- [Transformers GLM-OCR](https://huggingface.co/docs/transformers/model_doc/glm_ocr)
- [GLM-OCR GGUF](https://huggingface.co/ggml-org/GLM-OCR-GGUF)
- [Qwen2.5-VL official](https://qwenlm.github.io/blog/qwen2.5-vl/)
- [Qwen2.5-VL 32B official](https://qwenlm.github.io/blog/qwen2.5-vl-32b/)
- [MiniCPM official](https://github.com/OpenBMB/MiniCPM-o)
- [Ollama qwen2.5vl](https://ollama.com/library/qwen2.5vl)
- [Ollama minicpm-v](https://ollama.com/library/minicpm-v)
- [Ollama llava](https://ollama.com/library/llava)
- [OpenRouter Models](https://openrouter.ai/docs/models)
- [OpenRouter Qwen](https://openrouter.ai/qwen)
- [OpenRouter provider routing](https://openrouter.ai/docs/features/provider-routing)
