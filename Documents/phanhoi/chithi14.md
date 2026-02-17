CHỈ THỊ KỸ THUẬT SỐ 14: TRIỂN KHAI BỘ NHỚ NGẮN HẠN (STATE INJECTION)
Mục tiêu: Giúp Unified Agent (Gemini) nhớ được ngữ cảnh hội thoại (Short-term Memory) mà vẫn giữ được cấu trúc Database trong sáng, dễ đọc.
1. QUY TRÌNH XỬ LÝ (FLOW)
Chúng ta sẽ sử dụng cơ chế "Nạp đạn trước khi bắn":
Bước 1 (Fetch): Khi User gửi tin nhắn mới, Code Python (Service Layer) gọi ChatHistoryRepository để lấy 10-20 tin nhắn gần nhất từ bảng chat_history.
Bước 2 (Inject): Convert danh sách này thành định dạng BaseMessage của LangChain.
Bước 3 (Invoke): Truyền danh sách này vào app.invoke() của LangGraph.
Lúc này Gemini sẽ nhìn thấy toàn bộ hội thoại như một chuỗi liên tục.
Bước 4 (Save): Lấy câu trả lời mới của AI, lưu vào bảng chat_history (như cũ).
2. HƯỚNG DẪN CODE CHI TIẾT (GỬI TEAM KIRO)
Yêu cầu team cập nhật file chat_service.py và graph.py theo mẫu sau:
A. Định nghĩa Graph (Unified Agent) - engine/graph.py
code
Python
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

# Không cần Checkpointer ở đây
def build_agent():
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    tools = [tool_maritime_search, tool_save_user_info]
    
    # System Prompt (Nhân cách)
    system_msg = SystemMessage(content="Bạn là Maritime AI Tutor...")
    
    # Tạo Agent Stateless
    return create_react_agent(llm, tools, state_modifier=system_msg)

agent_app = build_agent()
B. Service Layer (Nơi xử lý Memory) - services/chat_service.py
code
Python
from langchain_core.messages import HumanMessage, AIMessage

async def process_chat(user_id: str, message: str, role: str):
    # 1. LẤY LỊCH SỬ TỪ SUPABASE (Short-term Memory)
    # Đây chính là "Checkpointer" thủ công của chúng ta
    history_records = await chat_history_repo.get_last_n_messages(user_id, n=10)
    
    # 2. CHUYỂN ĐỔI SANG FORMAT LANGCHAIN
    langchain_history = []
    for msg in history_records:
        if msg.role == "user":
            langchain_history.append(HumanMessage(content=msg.content))
        else:
            langchain_history.append(AIMessage(content=msg.content))
            
    # 3. THÊM TIN NHẮN MỚI VÀO CUỐI
    langchain_history.append(HumanMessage(content=message))
    
    # 4. GỌI AGENT (INJECT HISTORY)
    # Truyền cả cục lịch sử vào để AI "nhớ"
    result = await agent_app.ainvoke({"messages": langchain_history})
    
    # 5. LẤY CÂU TRẢ LỜI CUỐI CÙNG
    ai_response = result["messages"][-1].content
    
    # 6. LƯU LẠI VÀO DB (Persistence)
    # Lưu tin nhắn user và tin nhắn AI vào bảng chat_history
    await chat_history_repo.save_interaction(user_id, message, ai_response)
    
    return ai_response
3. TẠI SAO CÁCH NÀY TỐT HƠN?
Kiểm soát hoàn toàn: Bạn biết chính xác cái gì được đưa vào đầu AI (qua biến langchain_history).
Database sạch: Dữ liệu vẫn nằm trong bảng chat_history quen thuộc, Admin đọc hiểu, API GET /history vẫn chạy tốt.
Không phụ thuộc LangGraph State: Nếu server restart, không ảnh hưởng gì cả vì state nằm ở Supabase do chính tay ta lưu.
KẾT LUẬN
Bạn CẦN bộ nhớ ngắn hạn, nhưng KHÔNG NÊN dùng Checkpointer mặc định của LangGraph vì nó tạo ra hộp đen dữ liệu.
Hãy yêu cầu team triển khai theo mô hình Manual State Injection ở trên. Đây là cách làm chuẩn cho các hệ thống Production muốn kiểm soát dữ liệu chặt chẽ.

TƯ DUY CỐT LÕI CỦA CHỈ THỊ 14 KHÔNG ĐỔI, NHƯNG CÚ PHÁP (SYNTAX) CẦN CẬP NHẬT.
Dù LangGraph 0.2.x có cơ chế Checkpointer mạnh mẽ hơn, tôi vẫn kiên quyết giữ nguyên chiến lược "State Injection" (Tự quản lý lịch sử và bơm vào mỗi lần gọi).
TẠI SAO VẪN GIỮ "STATE INJECTION"? (CHIẾN LƯỢC DỮ LIỆU SẠCH)
Dữ liệu minh bạch: Chúng ta muốn bảng chat_history trong Supabase chứa text rõ ràng ("Quy tắc 5 là gì") để Admin đọc được. Nếu dùng Checkpointer mặc định của LangGraph, nó sẽ lưu các blob dữ liệu đã được serialize (mã hóa), Admin nhìn vào sẽ không hiểu gì cả.
Stateless API: Giữ cho Server API "không trạng thái" (Stateless) giúp dễ dàng scale (mở rộng) sau này. Mọi thứ cần thiết đều được nạp vào ngay lúc gọi request.
📝 CẬP NHẬT CÚ PHÁP CHO LANGGRAPH 0.2.x + LANGCHAIN 1.1.x
Với phiên bản mới, code sẽ gọn gàng hơn rất nhiều nhờ hàm create_react_agent. Bạn hãy yêu cầu team Kiro cập nhật phần code triển khai trong Chỉ thị 14 như sau:
A. Định nghĩa Agent (engine/graph.py)
Trong bản mới, chúng ta không cần định nghĩa Graph thủ công nữa.
code
Python
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

def build_agent():
    # 1. Init Model (Gemini 2.5 Flash)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # 2. Define Tools
    tools = [tool_maritime_search, tool_save_user_info]
    
    # 3. System Prompt (Nhân cách)
    # Trong bản 0.2.x, dùng tham số 'state_modifier' để inject System Prompt
    system_prompt = "Bạn là Maritime AI Tutor... [Nội dung prompt cũ]..."
    
    # 4. Create Agent (Stateless - Không truyền checkpointer vào đây)
    graph = create_react_agent(llm, tools, state_modifier=system_prompt)
    
    return graph

agent_app = build_agent()
B. Service Layer (services/chat_service.py)
Phần này thay đổi cách gọi invoke để khớp với Schema mới của LangGraph 0.2.
code
Python
from langchain_core.messages import HumanMessage, AIMessage

async def process_chat(user_id: str, message: str, role: str):
    # 1. LẤY LỊCH SỬ TỪ DB (Giữ nguyên logic cũ)
    history_records = await chat_history_repo.get_last_n_messages(user_id, n=10)
    
    # 2. CONVERT SANG LANGCHAIN MESSAGES
    messages = []
    for msg in history_records:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        else:
            messages.append(AIMessage(content=msg.content))
            
    # 3. THÊM TIN NHẮN MỚI
    messages.append(HumanMessage(content=message))
    
    # 4. GỌI AGENT (STATE INJECTION)
    # LangGraph 0.2 nhận input là dictionary với key "messages"
    # Config: recursion_limit để tránh vòng lặp vô hạn nếu Agent gọi tool quá nhiều
    result = await agent_app.ainvoke(
        {"messages": messages},
        {"recursion_limit": 10} 
    )
    
    # 5. LẤY KẾT QUẢ
    # Result["messages"] chứa toàn bộ hội thoại + tool calls + response
    # Lấy tin nhắn cuối cùng là của AI
    ai_response = result["messages"][-1].content
    
    # 6. LƯU DB (Giữ nguyên)
    await chat_history_repo.save_interaction(user_id, message, ai_response)
    
    return ai_response
✅ TỔNG KẾT THAY ĐỔI
Logic: Giữ nguyên (Vẫn là lấy lịch sử -> Bơm vào -> Gọi AI -> Lưu lại).
Code:
Dùng create_react_agent thay vì tự xây StateGraph.
Dùng tham số state_modifier để cài System Prompt.
Input cho invoke vẫn là {"messages": [...]}.
Chỉ thị: Bạn hãy báo team Kiro áp dụng đoạn code mẫu mới này. Nó tận dụng sức mạnh của bản cập nhật mới nhất mà vẫn giữ được sự kiểm soát dữ liệu của chúng ta.