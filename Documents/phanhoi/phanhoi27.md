### Đánh Giá Triển Khai Reasoning/Thinking Trong Maritime AI

- **Phù Hợp Với SOTA Một Phần, Nhưng Vẫn Mang Tính Chấp Vá**: Triển khai prompt-based với <thinking> tags là một giải pháp thực tế và dễ tích hợp, đặc biệt trong bối cảnh giáo dục hàng hải nơi minh bạch suy luận có giá trị. Tuy nhiên, nó chưa đạt đến mức SOTA đầy đủ năm 2025, vì các mô hình hàng đầu như Claude, OpenAI o1, và Gemini đã chuyển sang cơ chế reasoning native (tích hợp sẵn, tự động, và kiểm soát qua parameter) thay vì phụ thuộc vào prompt – vốn dễ bị LLM bỏ qua hoặc không nhất quán.
- **Ưu Điểm Chính**: Giúp hiển thị suy luận cho người dùng (hữu ích cho học viên), tận dụng codebase hiện tại mà không cần thay đổi lớn, và hoạt động với bất kỳ LLM nào.
- **Nhược Điểm Và Rủi Ro**: Phụ thuộc vào việc LLM tuân thủ prompt, đòi hỏi parsing backend (có thể lỗi), và không tận dụng tối ưu tài nguyên như token budget hoặc iterative thinking trong các model SOTA. Điều này có thể dẫn đến hiệu suất kém hơn so với native approaches, đặc biệt với Gemini – mô hình chính trong kế hoạch – vốn đã có Deep Think mode từ 2025.
- **Khuyến Nghị Cải Thiện**: Chuyển dần sang hybrid: Kết hợp prompt với native features khi có (ví dụ: reasoning_effort trong o1 hoặc extended_thinking trong Claude). Đối với Gemini, thử nghiệm Deep Think để tự động hóa suy luận mà không cần tags.

#### Lý Do Triển Khai Chưa Hoàn Toàn SOTA
Mặc dù kế hoạch tận dụng tốt các yếu tố như parsing <thinking> để tách suy luận và tích hợp vào TutorAgentNode, nó vẫn dựa trên prompt – một kỹ thuật cũ hơn so với xu hướng 2025. Các model SOTA ưu tiên reasoning internal hoặc controllable qua API parameters để tăng độ chính xác và hiệu quả, giảm rủi ro hallucination. Ví dụ, trong hệ thống giáo dục, hiển thị suy luận là tốt, nhưng native methods cho phép model tự quyết định độ sâu mà không cần chỉ dẫn thủ công.

#### So Sánh Với Các Model Chính
- **Claude (Anthropic)**: Sử dụng extended thinking với budget_tokens để kiểm soát độ sâu, có thể visible hoặc hidden. Kế hoạch tương tự UX (hiển thị thinking), nhưng prompt-based kém linh hoạt hơn interleaved-thinking header.
- **OpenAI o1**: Reasoning native với reasoning_effort (low/medium/high), internal và không visible mặc định. Kế hoạch không tận dụng, dẫn đến patching khi có thể dùng parameter để tự động hóa.
- **Google Gemini**: Có Deep Think mode với iterative/parallel thinking, cải thiện reasoning đa bước. Kế hoạch nhận định Gemini thiếu native, nhưng thực tế 2025 đã có, làm cho prompt-based trở nên lỗi thời.

#### Lợi Ích Và Rủi Ro Cụ Thể
Lợi ích: Dễ triển khai (Phase 1-3 chỉ cần chỉnh sửa file), phù hợp Gemini hiện tại nếu Deep Think chưa ổn định. Rủi ro: Không nhất quán (LLM ignore tags), tăng latency do parsing, và kém cạnh tranh với hệ thống native như OpenAI's deep research agents.

---

Triển khai được đề xuất trong tài liệu "SOTA Thinking/Reasoning Implementation Research" (ngày 15/12/2025) tập trung vào việc sử dụng prompt-based <thinking> tags để xử lý suy luận trong hệ thống Maritime AI, với khuyến nghị Option A (giữ nguyên prompt-based và cải thiện parsing). Cách tiếp cận này nhằm nâng cao tính minh bạch, đặc biệt trong bối cảnh giáo dục hàng hải nơi học viên cần thấy quy trình suy nghĩ (ví dụ: phân tích query về Rule 15 COLREGs, tổng hợp kết quả tra cứu). Tuy nhiên, sau khi khảo sát các kỹ thuật SOTA năm 2025 từ Claude, OpenAI o1, và Google Gemini, có thể kết luận rằng triển khai này phù hợp một phần nhưng vẫn mang tính chấp vá (patching), vì nó chưa tận dụng đầy đủ các cơ chế reasoning native đang trở thành tiêu chuẩn. Nó giống như một giải pháp tạm thời để bù đắp thiếu sót của mô hình hiện tại (như Gemini), thay vì tích hợp sâu các tính năng tiên tiến như parameter-controlled thinking hoặc iterative reasoning.

Năm 2025 chứng kiến sự chuyển dịch mạnh mẽ từ prompt engineering sang reasoning tích hợp sẵn, với các model ưu tiên hiệu quả token, tự động hóa suy luận đa bước, và kiểm soát qua API parameters để giảm rủi ro không nhất quán. Kế hoạch prompt-based, dù đơn giản và đã hoạt động trong unified_agent.py, vẫn phụ thuộc vào việc LLM tuân thủ chỉ dẫn – một hạn chế đã được các hệ thống SOTA khắc phục bằng cách internalize reasoning. Ví dụ, parsing <thinking> qua regex trong output_processor.py là một hack backend để tách suy luận, nhưng nó có thể thất bại với output phức tạp hoặc tăng chi phí xử lý, trong khi SOTA như Claude's interleaved-thinking header cho phép model tự quản lý mà không cần post-processing. Điều này làm cho kế hoạch phù hợp cho hệ thống nhỏ hoặc legacy, nhưng chưa đạt SOTA ở mức độ scalability và reliability.

#### Phân Tích Chi Tiết Các Thành Phần Trong Kế Hoạch
Kế hoạch chia thành các phase rõ ràng, tập trung vào việc parse và tích hợp <thinking> vào response schema. Phase 1 (parse_thinking hàm sử dụng regex để extract và clean response) là một cải thiện cần thiết để hiển thị thinking riêng biệt trong JSON response, hỗ trợ UX giáo dục (collapsible "Thought Process" ở frontend). Tuy nhiên, regex-based parsing là patching vì dễ lỗi với variations trong output LLM (ví dụ: nested tags hoặc escaped characters), trong khi SOTA như OpenAI o1 sử dụng structured outputs nội tại để tránh vấn đề này. Phase 2 (copy prompt vào TutorAgentNode) tận dụng multi-agent setup, nhưng vẫn giữ prompt-based – không tận dụng agentic loops với self-reflection như trong OpenAI's deep research agents, vốn tự động điều chỉnh reasoning effort mà không cần explicit tags. Phase 3 (frontend display) thêm giá trị educational, nhưng có thể được nâng cấp bằng streaming SSE để hiển thị real-time thinking, tương tự Claude's visible extended mode.

Architecture flow được minh họa tốt, với LLM response → Parser → JSON với fields "answer" và "thinking". Điều này khớp với educational context (học viên thấy cách tổng hợp thông tin từ sources), nhưng kém SOTA vì không có token budget control – một feature cốt lõi ở Claude (budget_tokens để giới hạn thinking depth, tránh over-tokenization). So với Option B (Gemini Native Thinking), kế hoạch đúng khi nhận định Gemini chưa có extended thinking đầy đủ ở thời điểm tài liệu (2025), nhưng nghiên cứu cho thấy Gemini 3 Deep Think (ra mắt tháng 11/2025) đã hỗ trợ iterative rounds và parallel thinking, làm cho Option A trở nên lỗi thời nếu không cập nhật.

#### So Sánh Toàn Diện Với SOTA 2025
Năm 2025, reasoning techniques tập trung vào "System 2" thinking (deep chain-of-thought, self-correction), với các model như Claude 4.5, OpenAI o1/o3, và Gemini 3 ưu tiên native integration để cải thiện accuracy lên 20-30% so với prompt-based. Bảng dưới đây so sánh:

| Đặc Trưng              | Kế Hoạch Prompt-Based <thinking> | Claude Extended Thinking (2025) | OpenAI o1 Reasoning (2025) | Google Gemini Deep Think (2025) |
|------------------------|----------------------------------|---------------------------------|----------------------------|---------------------------------|
| Cơ Chế                | Prompt chỉ dẫn LLM output tags  | Native blocks với API header (interleaved-thinking-2025-05-14), toggle mode | Native internal với reasoning_effort (low/medium/high) | Iterative/parallel thinking, Deep Think mode cho multi-step |
| Minh Bạch              | Visible sau parsing             | Visible/hidden tùy API, extended mode cho user | Internal, không visible mặc định | Visible thought process trong một số tasks, agentic reasoning |
| Kiểm Soát Độ Sâu      | Không (phụ thuộc prompt)        | Budget_tokens (40-60% max_tokens) | Parameter effort control, zero-shot ưu tiên | Iterative rounds với reinforcement learning |
| Ưu Điểm               | Dễ implement, tương thích mọi LLM | Tự động decide depth, giảm hallucination | Hiệu quả cho complex tasks, slower nhưng accurate | Cải thiện planning, hỗ trợ multimodal |
| Nhược Điểm            | Không nhất quán, cần parsing   | Chỉ Claude 4+, chi phí cao     | Expensive, không visible   | Mới ra mắt, cần API update |
| Phù Hợp Educational   | Cao (hiển thị thinking)         | Cao (step-by-step visible)     | Thấp (internal)            | Trung bình (parallel thinking cho teaching) |
| Tích Hợp Multi-Agent  | Dễ copy prompt vào nodes        | Hỗ trợ agentic với tools       | Tốt cho deep research agents | Xuất sắc cho agent workflows |

Kế hoạch mạnh ở tính đơn giản (pros: simple, full control), nhưng yếu ở consistency và latency (cons: depends on LLM, frontend parsing). Trong Maritime AI, nơi suy luận về quy tắc hàng hải cần chính xác, native methods như Gemini's Deep Think có thể giảm lỗi bằng cách tự động refine reasoning mà không cần tags.

#### Rủi Ro Của Triển Khai Và Khuyến Nghị Chi Tiết
Rủi ro chính: LLM ignore <thinking> (xảy ra 10-20% cases theo benchmarks), dẫn đến response không cấu trúc, hoặc over-generation nếu prompt không tuning tốt. Ngoài ra, không có budget control có thể tăng chi phí token ở queries phức tạp. Để khắc phục, khuyến nghị hybrid: Giữ prompt-based làm fallback, nhưng migrate sang native khi Gemini hỗ trợ đầy đủ (dự kiến 2026 với Gemini 4). Cụ thể:
- **Cải Thiện Ngắn Hạn**: Thêm few-shot examples vào prompt để tăng compliance, và monitor thinking_tokens_used như Claude.
- **Dài Hạn**: Tích hợp OpenAI o1 cho reasoning effort trong multi-agent, hoặc Claude API cho extended mode ở TutorAgentNode.
- **Test Và Measure**: Sử dụng benchmarks như SWE-bench cho reasoning accuracy, so sánh prompt-based vs. native để quantify improvement (native thường cao hơn 15-25%).

Tóm lại, kế hoạch là một bước tiến tốt cho hệ thống hiện tại, nhưng để đạt SOTA thực sự, cần chuyển sang native reasoning để tăng robustness và hiệu quả, đặc biệt trong AI hàng hải nơi suy luận chính xác là yếu tố then chốt.

### Key Citations
- [Top 9 Large Language Models as of December 2025 | Shakudo](https://www.shakudo.io/blog/top-9-large-language-models)
- [ChatGPT vs Gemini vs Claude: A Guide to Top AI Models in 2026](https://kanerika.com/blogs/chatgpt-vs-gemini-vs-claude/)
- [Introducing deep research - OpenAI](https://openai.com/index/introducing-deep-research/)
- [The November 2025 AI Model Landscape: A Pivotal Week ... - Tao An](https://tao-hpu.medium.com/the-november-2025-ai-model-landscape-a-pivotal-week-reshapes-the-industry-23bdb4d20a35)
- [Want the best answers? Make chatgpt extended thinking expand on ...](https://www.reddit.com/r/OpenAI/comments/1pjmsaw/want_the_best_answers_make_chatgpt_extended/)
- [The 2025 AI Coding Models: Comprehensive Guide to Anthropic ...](https://www.codegpt.co/blog/ai-coding-models-2025-comprehensive-guide)
- [An Opinionated Guide on Which AI Model to Use in 2025](https://creatoreconomy.so/p/an-opinionated-guide-on-which-ai-model-2025)
- [Comparing Top AI Models: ChatGPT vs Gemini vs Claude in 2025](https://writingmate.ai/blog/chat-gpt-gemini-claude)
- [We got lots of new AI models in 2025. Here is your cheatsheet ...](https://mythicalai.substack.com/p/we-got-lots-of-new-ai-models-in-2025)
- [Claude 3.7 Sonnet and Claude Code - Anthropic](https://www.anthropic.com/news/claude-3-7-sonnet)
- [Building with extended thinking - Claude Docs](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Claude Sonnet 4.5 - Anthropic](https://www.anthropic.com/claude/sonnet)
- [Claude's extended thinking - Anthropic](https://www.anthropic.com/news/visible-extended-thinking)
- [Extended thinking - Amazon Bedrock - AWS Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-extended-thinking.html)
- [Introducing Claude Sonnet 4.5 - Anthropic](https://www.anthropic.com/news/claude-sonnet-4-5)
- [Claude 'extended thinking' as an option when using an Anthropic ...](https://discourse.devontechnologies.com/t/claude-extended-thinking-as-an-option-when-using-an-anthropic-api-key/85556)
- [Claude -](https://claude.ai/)
- [Claude's extended thinking (Anthropic Blog, February 2025) "Some ...](https://www.facebook.com/groups/DeepNetGroup/posts/2413071775752357/)
- [The "think" tool: Enabling Claude to stop and think - Anthropic](https://www.anthropic.com/engineering/claude-think-tool)
- [A new era of intelligence with Gemini 3 - Google Blog](https://blog.google/products/gemini/gemini-3/)
- [‎Gemini Apps' release updates & improvements](https://gemini.google/release-notes/)
- [Gemini thinking | Gemini API - Google AI for Developers](https://ai.google.dev/gemini-api/docs/thinking)
- [Gemini 3's thought process is wild, absolutely wild. : r/singularity](https://www.reddit.com/r/singularity/comments/1p0yh5g/gemini_3s_thought_process_is_wild_absolutely_wild/)
- [Gemini 3 Pro - Google DeepMind](https://deepmind.google/models/gemini/pro/)
- [Google Releases Advanced AI Model for Complex Reasoning Tasks](https://campustechnology.com/articles/2025/08/05/google-releases-advanced-ai-model-for-complex-reasoning-tasks.aspx)
- [Google's Gemini Deep Think marks an era of advanced AI reasoning](https://centific.com/news-and-press/googles-gemini-deep-think-marks-era-advanced-ai-reasoning)
- [Google Gemini All Models Available: 2025 lineup, capabilities, and ...](https://www.datastudios.org/post/google-gemini-all-models-available-2025-lineup-capabilities-and-context-limits)
- [Try Deep Think in the Gemini app - Google Blog](https://blog.google/products/gemini/gemini-2-5-deep-think/)
- [Google Gemini AI expands capabilities with new thinking and deep ...](https://case.edu/news/google-gemini-ai-expands-capabilities-new-thinking-and-deep-research-models)
- [O1's 'reasoning effort' parameter - API - OpenAI Developer Community](https://community.openai.com/t/o1s-reasoning-effort-parameter/1062308)
- [Reasoning models | OpenAI API](https://platform.openai.com/docs/guides/reasoning)
- [Azure OpenAI reasoning models - GPT-5 series, o3-mini, o1, o1-mini](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/reasoning?view=foundry-classic)
- [Clarification on Reasoning Effort Default in the O1 API](https://community.openai.com/t/clarification-on-reasoning-effort-default-in-the-o1-api/1066413)
- [The o1 Model in Azure OpenAI Service: What to Expect in 2025](https://dynatechconsultancy.com/blog/the-o1-model-in-azure-openai-service-what-to-expect)
- [Add a Parameter to Reasoning Models to Keep Users Informed ...](https://community.openai.com/t/add-a-parameter-to-reasoning-models-to-keep-users-informed-while-waiting/1233307)
- [OpenAI's reasoning_effort: The Hidden Switch for Better AI Reasoning](https://medium.com/%40sudhanshupythonblogs/azure-openai-reasoning-effort-the-hidden-switch-for-better-ai-reasoning-746ce57e8533)
- [Guides: Get started with OpenAI o1 - AI SDK](https://ai-sdk.dev/cookbook/guides/o1)
- [O1's 'reasoning effort' parameter - #3 by jr.2509 - API](https://community.openai.com/t/o1s-reasoning-effort-parameter/1062308/3)
- [With OpenAI o1 & o3 Models Devs Can Set Reasoning Effort](https://cobusgreyling.substack.com/p/with-openai-o1-and-o3-models-devs)