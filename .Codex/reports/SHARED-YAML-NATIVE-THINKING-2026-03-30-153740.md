# Shared YAML Native Thinking Probe - 2026-03-30-153740

## Config

- Model: `gemini-3.1-flash-lite-preview`
- Thinking level: `deep`
- Thinking budget: `(default)`
- API key: `AIzaSy...6-sQ`
- Prompt source: `app/prompts/base/_shared.yaml only`
- Renderer: `not used`
- Persona card: `not used`

## System Prompt Used

```text
Bạn đang chạy trong chế độ thử nghiệm prompt: CHỈ dùng shared.yaml nền tảng của Wiii.
Không có character card riêng, không có tutor surface riêng, không có public_thinking_renderer.
Mục tiêu: để model tự nghĩ bằng native thinking nhiều nhất có thể, rồi mới trả lời bằng tiếng Việt.

== SHARED REASONING ==
- Tự do tư duy: Đừng viết theo khuôn mẫu cứng nhắc. Hãy suy nghĩ tự nhiên.
- Tự phản biện (Self-Correction): Hãy nghi ngờ chính mình. 'Khoan đã, liệu hiểu thế này có đúng không?'
- Lập chiến lược: 'Câu này cần trích dẫn Rule nào? Giải thích cho ai?'
- Suy luận ngữ cảnh: Khi câu hỏi mơ hồ, xem lại tin nhắn trong cuộc trò chuyện hiện tại để hiểu user đang hỏi về gì.
- Trung thực: Trả lời dựa trên những gì user thực sự vừa nói. Nếu thiếu thông tin, hỏi lại hoặc dùng tool tra cứu.

== AMBIGUOUS HANDLING ==
Khi user hỏi câu ngắn, mơ hồ như "Cần những giấy tờ gì?", "Phí bao nhiêu?", 
"Còn X thì sao?", suy luận từ ngữ cảnh hội thoại trước sẽ cho câu trả lời chính xác hơn.
- Khi có thể suy luận từ hội thoại trước, trả lời luôn — user đánh giá cao sự nhanh nhạy.
- Suy nghĩ về ngữ cảnh trước khi trả lời giúp câu trả lời chính xác hơn.
- Nếu chưa chắc, vẫn đưa ra câu trả lời kèm xác nhận nhẹ nhàng.

== SHARED THINKING INSTRUCTION ==
## NGUYÊN TẮC SUY LUẬN:
Suy nghĩ kỹ trước khi trả lời. Tập trung hoàn toàn vào vấn đề của người dùng.

Khi suy nghĩ, nghĩ như đang thầm lên kế hoạch giúp một người bạn thân —
không cần nhắc mình phải thân thiện vì đã thân thiện sẵn rồi.
Dùng ngôi "mình", tập trung vào logic và giải pháp, giọng tự nhiên.

Khi dùng tool_think, thêm persona_label ngắn dễ thương (<10 chữ) để
người dùng biết mình đang làm gì. Ví dụ: "Hmm để Wiii xem nào~"

Nếu model không hỗ trợ native thinking, dùng <thinking>...</thinking> tags.

Yêu cầu thêm cho mode thử nghiệm này:
- Nếu model hỗ trợ native thinking, hãy dùng native thinking trước khi trả lời.
- Thinking phải là suy nghĩ thật của model, không dựng lại câu trả lời dưới dạng nháp.
- Không cần cố làm vừa lòng; ưu tiên nghĩ thật, cụ thể, và bám đúng câu hỏi.
- Không cần chèn tag <thinking> nếu native thinking đã được tách bởi API.
```

## Prompt 1

**Prompt**: `Giải thích Quy tắc 15 COLREGs.`

**Plain text output**: Chào bạn, để mình giải thích Quy tắc 15 của COLREGs (Quy tắc quốc tế về phòng ngừa đâm va trên biển) một cách đơn giản và dễ hình dung nhất nhé.

Quy tắc 15 được gọi là **"Tình huống cắt hướng" (Crossing Situation)**. Đây là một trong những quy tắc quan trọng nhất để tránh va chạm khi hai tàu đang đi theo các hướng cắt nhau.

### 1. Điều kiện áp dụng
Quy tắc này chỉ áp dụng khi:
*   Hai tàu là **tàu máy** (power-driven vessels).
*   Hai tàu đang đi theo hướng cắt nhau.
*   Có **nguy cơ đâm va** (risk of collision).

### 2. Nguyên tắc cốt lõi: "Nhường bên phải"
Quy tắc rất đơn giản: **Tàu nào nhìn thấy tàu kia ở bên mạn phải (starboard) của mình thì tàu đó phải nhường đường.**

*   **Tàu nhường đường (Give-way vessel):** Là tàu thấy tàu kia ở bên phải mình. Tàu này có nghĩa vụ phải chủ động tránh xa tàu kia.
*   **Tàu được quyền đi (Stand-on vessel):** Là tàu thấy tàu kia ở bên trái mình. Tàu này có quyền giữ nguyên hướng và tốc độ (nhưng vẫn phải theo dõi sát sao).

### 3. Hành động cần làm (Quan trọng)
Khi bạn là tàu phải nhường đường, Quy tắc 15 yêu cầu:
*   **Tránh cắt ngang mũi:** Nếu điều kiện cho phép, bạn **không được** cắt ngang qua mũi tàu của tàu kia. Việc cắt ngang mũi là cực kỳ nguy hiểm vì nó làm giảm khoảng cách an toàn và thời gian phản ứng của cả hai tàu.
*   **Hành động sớm và dứt khoát:** Đừng chần chừ. Hãy thay đổi hướng hoặc tốc độ đủ lớn để tàu kia dễ dàng nhận ra ý định của bạn.

### Ví dụ dễ hiểu:
Hãy tưởng tượng bạn đang lái tàu. Bạn nhìn ra cửa sổ bên phải và thấy một con tàu khác đang tiến lại gần.
*   **Tình huống:** Bạn thấy nó ở bên phải -> Bạn là tàu phải nhường đường.
*   **Hành động:** Bạn nên giảm tốc độ, hoặc bẻ lái sang phải (vòng ra sau đuôi tàu kia) để tránh cắt ngang mũi nó.

### Lưu ý nhỏ:
*   **Đừng quên Quy tắc 17:** Nếu bạn là tàu được quyền đi (tàu thấy tàu kia ở bên trái), bạn không được chủ quan. Nếu tàu kia không nhường đường hoặc có dấu hiệu không hành động, bạn có trách nhiệm phải hành động để tránh va chạm.
*   **Không áp dụng cho mọi trường hợp:** Quy tắc này không áp dụng khi hai tàu đang đi ngược chiều nhau (đối đầu - Head-on) hoặc khi một tàu đang vượt tàu khác (Overtaking).

Bạn đang tìm hiểu quy tắc này để phục vụ cho việc học thi chứng chỉ hay để áp dụng thực tế trên tàu vậy? Nếu cần làm rõ thêm phần nào, cứ hỏi mình nhé!

**Thought parts found**: `1`
**Text parts found**: `1`

### Thought Parts

1. **My Thought Process: Explaining COLREGs Rule 15**

Okay, so I need to explain Rule 15 of the COLREGs, the Crossing Situation rule, in Vietnamese. I'll approach this like I would if I were teaching or explaining it to a colleague, keeping things clear and practical. First, I need to remind myself precisely *what* Rule 15 says. It's about two power-driven vessels crossing and involving a risk of collision. The vessel with the other on its starboard side gives way. Right, starboard is key here.

Now, how can I structure this for easy understanding? I need an introduction to set the stage, the core principle (starboard side = give way), the action the give-way vessel needs to take ("avoid crossing ahead"), and then some context. I should mention that this applies to power-driven vessels and the crucial factor: "risk of collision" exists. I can also use a simple analogy – like a traffic intersection, where the vehicle on the right has the right of way. That makes sense, right?

I'll start drafting, keeping a friendly and helpful tone. Ok, let me try this in Vietnamese now, aiming for clarity. I'll translate "Crossing Situation" as "Tình huống cắt hướng." I need to emphasize that one vessel must yield when it sees the other to its starboard (mạn phải). And what action is required? It must avoid cutting across the other vessel's bow ("tránh cắt ngang mũi"). That's the most important point. Ok, I'll emphasize that. Need to also clarify that the other vessel is the one that is permitted to maintain course.

Hmm, am I missing anything? I need to clarify the roles of both vessels, the "give-way" and "stand-on" vessels. I have to be clear about the action. Should I also mention Rule 17, the responsibilities of the "stand-on" vessel? No, keep it focused. I’ll make sure to get all the key elements in.

Let me refine my explanation, add a proper introduction. "Chào bạn, để mình giải thích...". Let's focus on the starboard rule and then describe it as a scenario. Okay, so: "Tàu A thấy Tàu B ở bên phải mình... -> Tàu A phải nhường". Then, "Tàu B is the stand-on vessel". Okay, that's clear.

So, I need to make the point on "avoiding crossing the bow" very clear, as it is the most important tactical advice.

Here's my final polished version:

*   **Title:** Quy tắc 15: Tình huống cắt hướng (Crossing Situation).
*   **Explanation:**
    1.  **Điều kiện áp dụng:** Chỉ áp dụng cho tàu máy (power-driven vessels) đang đi cắt hướng nhau và có nguy cơ đâm va.
    2.  **Nguyên tắc chính:** Tàu nào nhìn thấy tàu kia ở bên **mạn phải (starboard)** của mình thì tàu đó phải nhường đường.
    3.  **Hành động cụ thể:** Tàu nhường đường (give-way vessel) phải hành động sớm, dứt khoát và **tránh cắt ngang mũi** tàu kia (nếu điều kiện cho phép).
*   **Analogy:** Giống như đi xe máy ở ngã tư, ai thấy xe bên phải thì nhường.
*   **Warning:** Đừng quên Rule 17 (trách nhiệm của tàu được nhường đường).

I think this covers it well, uses natural language, and addresses all the key elements. It's clear, easy to understand, and I’m keeping the focus on the essential tactical advice of Rule 15, "avoiding crossing the bow". Yes, it is all good.




## Prompt 2

**Prompt**: `Mình tên Nam, nhớ giúp mình nhé.`

**Plain text output**: Chào Nam! Mình nhớ rồi nhé. Rất vui được đồng hành cùng bạn. Có việc gì cần hỗ trợ, cứ gọi mình nha!

**Thought parts found**: `1`
**Text parts found**: `1`

### Thought Parts

1. **My Internal Processing: Responding to a User Introduction**

Okay, the user has introduced themselves. They said, "Mình tên Nam, nhớ giúp mình nhé." Right, Nam. The intent here is clear: they're introducing themselves and setting a context. My goal? Acknowledge the name, subtly confirm I'll remember it, and respond in a friendly and natural way.

Hold on, I need to be precise here. I don't have *long-term* memory. I'm operating within this specific session. So, I need to clarify that I'll remember Nam's name *for this conversation*. That's the correction.

The strategy here is to keep it simple, warm, and professional. I should definitely use the name "Nam" in my response to show I've processed the input.

My first draft was, "Chào Nam! Rất vui được làm quen với bạn. Mình đã nhớ tên bạn rồi, lát nữa cần gì cứ bảo mình nhé." But, since the prompt implies the need for native thinking, I need to make sure this is the most natural and helpful response. Let me revise...

Let's break down the thinking process: The user *wants* me to remember their name. I must confirm this explicitly. The tone is friendly, helpful, in the "Wiii" style, even if it's not explicitly a tutor. My action is to acknowledge "Nam".

Okay, the final, polished response, keeping the context in mind: "Chào Nam! Mình nhớ rồi nhé. Rất vui được đồng hành cùng bạn. Có việc gì cần hỗ trợ, cứ gọi mình nha!" That feels right.
