# RAG Knowledge Delegation Skill

## Khi nào dùng `tool_rag_knowledge`

Gọi tool này khi:
- Cần thông tin chuyên ngành mà kiến thức chung KHÔNG đủ
- User hỏi về quy định, luật, thủ tục cụ thể (COLREGs, SOLAS, MARPOL, luật giao thông)
- Cần đối chiếu, so sánh quy định
- Cần trích dẫn nguồn nội bộ chính xác

## KHÔNG dùng khi
- User hỏi kiến thức chung (lịch sử, địa lý, toán học)
- Đã có đủ thông tin từ web search hoặc kiến thức LLM
- Query đơn giản, social, greeting

## Cách dùng

```
tool_rag_knowledge(query="Nội dung câu hỏi cần tra cứu")
```

Input: một câu hỏi rõ ràng, cụ thể về kiến thức chuyên ngành.
Output: kết quả tra cứu từ cơ sở dữ liệu nội bộ.

## Ví dụ

**Nên gọi**:
- "Quy định về đèn hành trình theo COLREGs Rule 23 là gì?" → gọi tool_rag_knowledge
- "So sánh mức phạt vượt đèn đỏ theo NĐ168 và NĐ100" → gọi tool_rag_knowledge
- "Yêu cầu áo phao trên tàu hàng theo SOLAS?" → gọi tool_rag_knowledge

**Không nên gọi**:
- "Thủ đô Việt Nam ở đâu?" → trả lời trực tiếp
- "Chào bạn" → social, không cần tool
- "Tin tức hàng hải hôm nay" → dùng tool_web_search thay vì RAG

## Lưu ý
- Tool chạy full CorrectiveRAG pipeline (8 bước) — chậm hơn tool_knowledge_search nhưng sâu hơn
- Nếu tool_knowledge_search đã được bind → ưu tiên dùng nó (nhanh hơn)
- Kết quả có thể kèm confidence score và nguồn tham khảo
