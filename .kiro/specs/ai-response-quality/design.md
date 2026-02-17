# Design Document: AI Response Quality Improvement

## Overview

Cải thiện chất lượng phản hồi của Maritime AI Tutor thông qua:
1. Tối ưu hóa Persona và Response Style
2. Tích hợp Tutor Agent vào Unified Agent
3. Cải thiện Memory Utilization
4. Thêm Tools mới và cải thiện Tool Descriptions
5. Response Variation và Suggested Questions

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED AGENT v2.0                                   │
│                    (Enhanced Response Quality)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    ENHANCED PROMPT SYSTEM                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │ tutor.yaml  │  │assistant.yaml│  │VariationPool│                  │    │
│  │  │ (Student)   │  │(Teacher/Admin)│  │ (Anti-Rep)  │                  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    TOOLS (Enhanced - 7 tools)                        │    │
│  │  EXISTING:                                                           │    │
│  │  ├── tool_maritime_search (RAG) - Enhanced descriptions             │    │
│  │  ├── tool_save_user_info (Memory) - Better patterns                 │    │
│  │  └── tool_get_user_info (Memory)                                    │    │
│  │                                                                      │    │
│  │  NEW:                                                                │    │
│  │  ├── tool_start_quiz (Tutor Agent integration)                      │    │
│  │  ├── tool_suggest_topics (Learning path)                            │    │
│  │  ├── tool_compare_rules (Side-by-side comparison)                   │    │
│  │  └── tool_explain_term (Terminology breakdown)                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    RESPONSE PROCESSOR                                │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │ Length      │  │ Variation   │  │ Suggested   │                  │    │
│  │  │ Controller  │  │ Checker     │  │ Questions   │                  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
          ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
          │ Semantic    │  │ Tutor       │  │ Hybrid      │
          │ Memory v0.3 │  │ Agent       │  │ Search      │
          └─────────────┘  └─────────────┘  └─────────────┘
```

## Components and Interfaces

### 1. Enhanced Prompt System

```python
class EnhancedPromptLoader:
    """
    Extended PromptLoader with variation support and empathy detection.
    """
    
    def build_system_prompt(
        self,
        role: str,
        user_name: Optional[str] = None,
        user_facts: Optional[List[str]] = None,
        conversation_summary: Optional[str] = None,
        recent_phrases: Optional[List[str]] = None  # NEW: For variation
    ) -> str:
        """Build dynamic system prompt with anti-repetition."""
        pass
    
    def detect_empathy_needed(self, message: str) -> bool:
        """Detect if user message requires empathy-first response."""
        pass
    
    def get_variation_phrases(self, category: str) -> List[str]:
        """Get alternative phrases for a category (greetings, transitions, etc.)"""
        pass
```

### 2. New Tools Interface

```python
# Tool: Start Quiz
@tool(description="""
Bắt đầu một phiên kiểm tra kiến thức (quiz) về chủ đề hàng hải.

PHẢI GỌI KHI:
- User yêu cầu quiz, kiểm tra, test: "kiểm tra kiến thức", "quiz về COLREGs", "test tôi về SOLAS"
- User muốn đánh giá trình độ: "đánh giá kiến thức của tôi"

KHÔNG GỌI KHI:
- User chỉ hỏi kiến thức thông thường
- User đang trong phiên quiz (dùng tool_answer_quiz thay thế)

Input: topic (str) - Chủ đề quiz (colregs, solas, marpol, navigation, safety)
Output: Câu hỏi đầu tiên của quiz
""")
async def tool_start_quiz(topic: str) -> str:
    """Start a quiz session using Tutor Agent."""
    pass

# Tool: Suggest Topics
@tool(description="""
Gợi ý chủ đề học tiếp theo dựa trên lịch sử học tập của user.

PHẢI GỌI KHI:
- User hỏi nên học gì tiếp: "tôi nên học gì", "gợi ý chủ đề"
- User hoàn thành một chủ đề và muốn tiếp tục

Input: current_topic (str, optional) - Chủ đề vừa học xong
Output: Danh sách 3-5 chủ đề gợi ý với lý do
""")
async def tool_suggest_topics(current_topic: str = "") -> str:
    """Suggest next learning topics based on user history."""
    pass

# Tool: Compare Rules
@tool(description="""
So sánh hai hoặc nhiều quy tắc/điều luật hàng hải.

PHẢI GỌI KHI:
- User yêu cầu so sánh: "so sánh Rule 15 và Rule 17", "khác nhau giữa SOLAS và MARPOL"
- User hỏi về sự khác biệt giữa các quy định

Input: rules (str) - Các quy tắc cần so sánh, phân cách bằng dấu phẩy
Output: Bảng so sánh chi tiết
""")
async def tool_compare_rules(rules: str) -> str:
    """Compare multiple maritime rules side-by-side."""
    pass

# Tool: Explain Term
@tool(description="""
Giải thích chi tiết một thuật ngữ hàng hải với ví dụ thực tế.

PHẢI GỌI KHI:
- User hỏi định nghĩa: "starboard là gì", "RAM vessel nghĩa là gì"
- User cần giải thích thuật ngữ chuyên ngành

Input: term (str) - Thuật ngữ cần giải thích
Output: Định nghĩa + Dịch thuật + Ví dụ thực tế
""")
async def tool_explain_term(term: str) -> str:
    """Explain a maritime term with examples."""
    pass
```

### 3. Response Processor

```python
class ResponseProcessor:
    """
    Post-process AI responses for quality control.
    """
    
    def __init__(self):
        self._variation_tracker: Dict[str, List[str]] = {}  # session_id -> recent phrases
        self._length_controller = ResponseLengthController()
        self._suggestion_generator = SuggestedQuestionsGenerator()
    
    def process(
        self,
        response: str,
        session_id: str,
        query_complexity: str,  # "simple" | "complex"
        sources: Optional[List[Source]] = None
    ) -> ProcessedResponse:
        """
        Process response for quality.
        
        1. Check and adjust length
        2. Verify no repetitive patterns
        3. Generate suggested questions
        """
        pass
    
    def check_variation(self, response: str, session_id: str) -> bool:
        """Check if response uses varied phrasing."""
        pass
    
    def estimate_complexity(self, query: str) -> str:
        """Estimate query complexity for length control."""
        pass
```

### 4. Enhanced Tool Descriptions

```python
# BEFORE (current - too short)
@tool(description="Tra cứu các quy tắc, luật lệ hàng hải...")

# AFTER (enhanced - detailed guidelines)
@tool(description="""
Tra cứu kiến thức hàng hải từ Knowledge Base (COLREGs, SOLAS, MARPOL).

PHẢI GỌI KHI:
- User hỏi về quy tắc, điều luật, số hiệu (Rule 15, SOLAS II-2/10, MARPOL Annex I)
- User hỏi về tình huống hàng hải (cắt hướng, vượt, đối đầu, tầm nhìn hạn chế)
- User hỏi về thiết bị, an toàn, cứu sinh, cứu hỏa trên tàu
- User hỏi về chứng chỉ, đăng kiểm, thủ tục hàng hải

KHÔNG GỌI KHI:
- User chào hỏi, giới thiệu bản thân
- User than vãn, chia sẻ cảm xúc (mệt, đói, chán)
- User hỏi về thông tin cá nhân đã lưu
- User yêu cầu quiz (dùng tool_start_quiz)

Input: query (str) - Câu hỏi hoặc từ khóa tìm kiếm
Output: Nội dung kiến thức + Nguồn tham khảo (citations)

ƯU TIÊN: Cao - Gọi tool này khi có bất kỳ từ khóa hàng hải nào
""")
async def tool_maritime_search(query: str) -> str:
    pass
```

## Data Models

### ProcessedResponse

```python
@dataclass
class ProcessedResponse:
    """Response after quality processing."""
    content: str
    word_count: int
    complexity_matched: bool  # Response length matches query complexity
    variation_score: float  # 0-1, higher = more varied
    suggested_questions: List[str]
    sources: Optional[List[Source]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### QuizSession

```python
@dataclass
class QuizSession:
    """Active quiz session state."""
    session_id: str
    user_id: str
    topic: str
    phase: TeachingPhase  # INTRODUCTION | EXPLANATION | ASSESSMENT | COMPLETED
    questions_asked: int
    correct_answers: int
    current_question: Optional[str]
    started_at: datetime
    
    @property
    def score(self) -> float:
        if self.questions_asked == 0:
            return 0.0
        return (self.correct_answers / self.questions_asked) * 100
    
    def has_mastery(self) -> bool:
        return self.score >= 80.0 and self.questions_asked >= 3
```

### VariationTracker

```python
@dataclass
class VariationTracker:
    """Track recent phrases to avoid repetition."""
    session_id: str
    recent_openings: List[str] = field(default_factory=list)  # Last 5 opening phrases
    recent_transitions: List[str] = field(default_factory=list)  # Last 5 transition phrases
    name_usage_count: int = 0
    total_responses: int = 0
    
    def should_use_name(self) -> bool:
        """Check if name should be used (20-30% frequency)."""
        if self.total_responses == 0:
            return True  # First response can use name
        ratio = self.name_usage_count / self.total_responses
        return ratio < 0.3  # Allow if under 30%
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Empathy Detection Accuracy
*For any* user message expressing frustration or tiredness (containing patterns like "mệt", "chán", "đói", "buồn ngủ"), the empathy detection function SHALL return true.
**Validates: Requirements 1.2**

### Property 2: Name Usage Frequency
*For any* sequence of N responses (N ≥ 5) to a user with stored name, the name SHALL appear in 20-30% of responses (between N*0.2 and N*0.3 occurrences).
**Validates: Requirements 1.3, 7.2**

### Property 3: No Greeting Repetition in Follow-ups
*For any* follow-up response (not the first message in session), the response SHALL NOT start with greeting patterns ("Chào", "Xin chào", "Hello").
**Validates: Requirements 1.4**

### Property 4: Response Length Appropriateness
*For any* simple query (less than 10 words, single concept), the response word count SHALL be between 50-150 words. *For any* complex query (multiple concepts or explicit detail request), the response word count SHALL be between 200-400 words.
**Validates: Requirements 2.1, 2.2**

### Property 5: Citation Inclusion
*For any* response generated from RAG tool, the response SHALL include at least one source citation.
**Validates: Requirements 2.3**

### Property 6: Term Translation Consistency
*For any* response containing English maritime terms (starboard, port, give-way, stand-on), the response SHALL also include the Vietnamese translation.
**Validates: Requirements 2.4**

### Property 7: Quiz Tool Invocation
*For any* user message containing quiz-related keywords ("quiz", "kiểm tra", "test kiến thức"), the tool_start_quiz SHALL be invoked.
**Validates: Requirements 3.1**

### Property 8: Tutor Phase Transitions
*For any* active quiz session, the phase transitions SHALL follow the order: INTRODUCTION → EXPLANATION → ASSESSMENT → COMPLETED, with no skipped phases.
**Validates: Requirements 3.2**

### Property 9: Quiz Evaluation Correctness
*For any* quiz answer evaluation, correct answers SHALL increment correct_answers counter, and incorrect answers SHALL trigger hint provision.
**Validates: Requirements 3.3**

### Property 10: Mastery Achievement
*For any* quiz session where score ≥ 80% AND questions_asked ≥ 3, the mastery_achieved flag SHALL be set to true.
**Validates: Requirements 3.4**

### Property 11: User Facts Retrieval
*For any* returning user (has previous sessions), the context retrieval SHALL include stored user facts from Semantic Memory.
**Validates: Requirements 4.1**

### Property 12: Fact Extraction from Personal Info
*For any* message containing personal information patterns (name introduction, profession mention), the fact extraction SHALL identify and store at least one fact.
**Validates: Requirements 4.2**

### Property 13: Summarization Trigger
*For any* session exceeding the token threshold, the summarization process SHALL be triggered.
**Validates: Requirements 4.3**

### Property 14: Tool Registration
*For any* Unified Agent instance, all 7 tools (tool_maritime_search, tool_save_user_info, tool_get_user_info, tool_start_quiz, tool_suggest_topics, tool_compare_rules, tool_explain_term) SHALL be registered and callable.
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

### Property 15: Tool Usage Logging
*For any* tool invocation, the system SHALL log the tool name, arguments, and result.
**Validates: Requirements 5.5**

### Property 16: Greeting No-Search Rule
*For any* greeting message (containing "chào", "hello", "hi"), the tool_maritime_search SHALL NOT be invoked.
**Validates: Requirements 6.4**

### Property 17: Opening Phrase Variation
*For any* sequence of 5 consecutive responses, at least 3 different opening phrases SHALL be used.
**Validates: Requirements 7.1**

### Property 18: Suggested Questions Generation
*For any* RAG-based response, the suggested_questions field SHALL contain 2-3 questions related to the current topic.
**Validates: Requirements 8.1, 8.5**

## Error Handling

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| Tutor Agent unavailable | Fallback to RAG-based explanation without quiz |
| Semantic Memory unavailable | Use sliding window history only |
| Tool execution fails | Return graceful error message, log for debugging |
| LLM timeout | Retry once, then return cached/fallback response |
| Invalid quiz topic | Suggest valid topics from predefined list |
| Empty search results | Provide helpful "no results" message with suggestions |

## Testing Strategy

### Property-Based Testing (Hypothesis)

Sử dụng **Hypothesis** library cho Python để implement property-based tests.

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=100))
def test_empathy_detection(message):
    """Property 1: Empathy detection accuracy."""
    # Generate messages with frustration patterns
    pass

@given(st.integers(min_value=5, max_value=20))
def test_name_usage_frequency(num_responses):
    """Property 2: Name usage frequency."""
    # Generate N responses and verify name frequency
    pass
```

### Unit Tests

- Test individual tool functions
- Test ResponseProcessor methods
- Test VariationTracker logic
- Test QuizSession state transitions

### Integration Tests

- End-to-end chat flow with quiz
- Memory retrieval and storage
- Tool invocation chain

### Test Configuration

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

# Hypothesis settings
[tool.hypothesis]
max_examples = 100
deadline = 5000  # 5 seconds per test
```
