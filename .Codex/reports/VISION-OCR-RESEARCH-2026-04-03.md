# Vision vs OCR Research

Date: 2026-04-03

## Question

`vision model` trong Wiii có phải chỉ là `OCR` không, và Z.ai có model OCR nhẹ/open dùng tốt không?

## Short Answer

Không. Trong Wiii, `vision` hiện là một runtime rộng hơn OCR.

Ba capability hiện có:

- `ocr_extract`
- `visual_describe`
- `grounded_visual_answer`

OCR chỉ là **một nhánh con** trong đó.

## Current Wiii Reality

Code hiện tại đã tách capability khá đúng:

- [vision_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/vision_runtime.py)
- [visual_rag.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/visual_rag.py)
- [visual_memory.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/visual_memory.py)

Ý nghĩa thực tế:

- `ocr_extract`: bóc chữ, layout, công thức, bảng
- `visual_describe`: mô tả nội dung ảnh cho retrieval/memory
- `grounded_visual_answer`: trả lời câu hỏi bám sát ảnh và ngữ cảnh

## What Z.ai Actually Offers

Theo docs chính thức của Z.ai:

- GLM-4.6V / GLM-5V-Turbo là **vision-language model** tổng quát
- GLM-OCR là **document parsing / OCR** chuyên biệt

GLM-OCR hiện được Z.ai mô tả là:

- lightweight, chỉ khoảng `0.9B`
- tối ưu cho document parsing
- mạnh ở text, handwriting, formulas, tables, information extraction
- phù hợp cho RAG trên tài liệu

## Practical Conclusion

Z.ai GLM-OCR là ứng viên rất tốt cho lane `ocr_extract`.

Nhưng GLM-OCR **không nên** là model duy nhất cho toàn bộ `vision runtime`, vì:

- nó được định vị cho document parsing/OCR
- còn `visual_describe` và `grounded_visual_answer` cần năng lực VLM tổng quát hơn

## Recommended Architecture

Nên route theo capability:

- `ocr_extract` -> OCR-specialist
- `visual_describe` -> general VLM
- `grounded_visual_answer` -> stronger general VLM / reasoning VLM

Một mapping hợp lý cho Wiii:

- `ocr_extract` -> `GLM-OCR`
- `visual_describe` -> `GLM-4.6V` / `GLM-5V-Turbo` / Gemini / OpenAI vision
- `grounded_visual_answer` -> `GLM-4.6V` / `GLM-5V-Turbo` / Gemini / OpenAI vision

## Open-Source / Local Note

Mình xác nhận có ecosystem public rõ cho GLM-OCR:

- docs tích hợp trong Transformers
- model public trên Hugging Face
- có cả bản GGUF cộng đồng chuyển đổi

Điều đó rất tốt cho local/self-hosted OCR direction.

Tuy nhiên, với phần `general vision`, mình chưa thấy một contract production-ready tương đương trong Wiii cho Zhipu, nên hiện vẫn đúng khi runtime fail-close Zhipu ở lane vision tổng quát.

## Best Next Step

Không nên hỏi `vision = OCR hay không`, mà nên sửa runtime theo đúng câu hỏi hơn:

- model nào cho `ocr_extract`
- model nào cho `visual_describe`
- model nào cho `grounded_visual_answer`

Đề xuất kỹ thuật tiếp theo:

1. thêm `ocr-specialist provider contract` cho Z.ai GLM-OCR
2. giữ `general vision` và `OCR` là hai đường chọn model riêng
3. benchmark live:
   - invoice / scan / screenshot / handwriting / table
   - và tách riêng `OCR quality` khỏi `general visual reasoning quality`

## Sources

- [Z.AI Overview](https://docs.z.ai/guides/overview/overview)
- [Z.AI GLM-OCR Guide](https://docs.z.ai/guides/vlm/glm-ocr)
- [Z.AI GLM-4.6V Guide](https://docs.z.ai/guides/vlm/glm-4.6v)
- [Z.AI Layout Parsing API](https://docs.z.ai/api-reference/tools/layout-parsing)
- [Z.AI Pricing](https://docs.z.ai/guides/overview/pricing)
- [Google Gemini Image Understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
- [Google Document AI OCR](https://cloud.google.com/document-ai/docs/process-documents-ocr)
- [Hugging Face Transformers GLM-OCR](https://huggingface.co/docs/transformers/model_doc/glm_ocr)
- [GGUF GLM-OCR](https://huggingface.co/ggml-org/GLM-OCR-GGUF)
