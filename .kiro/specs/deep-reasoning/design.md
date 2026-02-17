# Design Document: Deep Reasoning & Smart Context Engine (CHỈ THỊ 21)

## Overview

Thiết kế hệ thống Deep Reasoning cho Maritime AI, biến chatbot thành "Chuyên gia tư duy" với khả năng:
- Internal Monologue qua thẻ `<thinking>`
- Self-Correction và Context-aware reasoning
- Proactive behavior (chủ động hỏi tiếp tục)
- Hybrid Memory (Vector DB + Large Context Window)

## Architecture

```mermaid
flowchart TD
    subgraph "Request Flow"
        A[User Message] --> B[ChatService]
        B --> C{Guardian Check}
        C -->|BLOCKED| D[Return Warning]
        C -->|ALLOWED| E[Build Context]
    end
    
    subgraph "Context Building"
        E --> F[Query Vector DB<br/>User Facts]
        E --> G[Get Recent 50 Messages<br/>Large Context Window]
        E --> H[Analyze Incomplete Topics]
        F --> I[Inject Facts to System Prompt]
        G --> I
        H --> I
    end
    
    subgraph "Deep Reasoning"
        I --> J[UnifiedAgent.process()]
        J --> K[Generate <thinking> Section]
        K --> L[Self-Correction]
        K --> M[Context Check]
        K --> N[Strategy Planning]
        L --> O[Generate Final Answer]
        M --> O
        N --> O
    end
    
    subgraph "Response"
        O --> P[Format Response]
        P --> Q["<thinking>...</thinking><br/>Final Answer"]
        Q --> R[Return to Frontend]
    end
```

## Components and Interfaces

### 1. DeepReasoningConfig

```python
@dataclass
class DeepReasoningConfig:
    """Configuration for Deep Reasoning feature."""
    enabled: bool = True
    context_window_size: int = 50  # Number of messages to include
    include_thinking_tags: bool = True
    proactive_continuation: bool = True
```

### 2. ConversationAnalyzer

```python
class ConversationAnalyzer:
    """Analyzes conversation for incomplete topics and context."""
    
    def analyze(self, messages: List[ChatMessage]) -> ConversationContext:
        """
        Analyze conversation history for:
        - Incomplete explanations
        - User interruptions
        - Topics being discussed
        """
        pass
    
    def detect_incomplete_explanation(self, content: str) -> bool:
        """Check if AI response contains incomplete explanation."""
        pass
    
    def extract_topic(self, content: str) -> Optional[str]:
        """Extract main topic from AI response."""
        pass
    
    def is_continuation_request(self, message: str, topic: str) -> bool:
        """Check if user is asking to continue previous topic."""
        pass
```

### 3. DeepReasoningPromptBuilder

```python
class DeepReasoningPromptBuilder:
    """Builds prompts with Deep Reasoning instructions."""
    
    def build_system_prompt(
        self,
        user_facts: Dict[str, Any],
        conversation_context: ConversationContext
    ) -> str:
        """Build system prompt with Deep Reasoning instructions."""
        pass
    
    def build_thinking_instructions(self) -> str:
        """Generate instructions for <thinking> section."""
        pass
    
    def inject_proactive_context(
        self,
        context: ConversationContext
    ) -> str:
        """Add proactive continuation hints to prompt."""
        pass
```

### 4. Updated ChatService

```python
class ChatService:
    async def process_message(self, request, background_save):
        # Step 1: Guardian validation (existing)
        
        # Step 2: Get large context window (50 messages)
        recent_messages = self._chat_history.get_recent_messages(
            session_id, 
            limit=50,  # Increased from 10
            include_blocked=False
        )
        
        # Step 3: Query Vector DB for user facts
        user_facts = await self._semantic_memory.get_user_facts(user_id)
        
        # Step 4: Analyze conversation for incomplete topics
        conversation_context = self._conversation_analyzer.analyze(recent_messages)
        
        # Step 5: Build Deep Reasoning prompt
        prompt = self._prompt_builder.build_system_prompt(
            user_facts=user_facts,
            conversation_context=conversation_context
        )
        
        # Step 6: Process with UnifiedAgent
        response = await self._unified_agent.process(
            message=message,
            conversation_history=self._build_conversation_history(recent_messages),
            system_prompt=prompt,
            deep_reasoning_config=self._deep_reasoning_config
        )
        
        # Step 7: Return response with <thinking> tags
        return response
```

## Data Models

### ConversationContext

```python
@dataclass
class ConversationContext:
    """Context analysis for proactive AI behavior."""
    incomplete_explanations: List[str]  # Topics being explained
    last_explanation_topic: Optional[str]  # Most recent incomplete topic
    user_interrupted: bool  # Did user ask new question during explanation?
    should_offer_continuation: bool  # Should AI offer to continue?
    current_topic: Optional[str]  # What user is asking about now
    user_facts: Dict[str, Any]  # Facts from Vector DB
```

### ThinkingSection

```python
@dataclass
class ThinkingSection:
    """Parsed thinking section from AI response."""
    raw_content: str  # Full <thinking>...</thinking> content
    self_corrections: List[str]  # Self-correction statements
    context_checks: List[str]  # Context verification statements
    strategy_plans: List[str]  # Response planning statements
    proactive_notes: List[str]  # Notes about incomplete topics
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following properties have been identified:

### Property 1: Thinking Tags Presence
*For any* user message processed with deep reasoning enabled, the response SHALL contain properly formed `<thinking>` tags before the final answer.
**Validates: Requirements 1.1, 1.5, 4.1**

### Property 2: Response Format Order
*For any* response with deep reasoning enabled, the `<thinking>` section SHALL appear BEFORE the final answer, and the final answer SHALL appear AFTER the closing `</thinking>` tag.
**Validates: Requirements 4.2, 4.3**

### Property 3: Context Window Size Limit
*For any* chat history retrieval request, the System SHALL return at most 50 messages, regardless of how many messages exist in the database.
**Validates: Requirements 2.1**

### Property 4: Blocked Messages Exclusion
*For any* context building operation, the resulting context SHALL contain only non-blocked messages in chronological order.
**Validates: Requirements 2.2**

### Property 5: Incomplete Topic Detection
*For any* conversation with an incomplete AI explanation followed by a new user question, the ConversationAnalyzer SHALL correctly identify the incomplete topic and set `should_offer_continuation` to true.
**Validates: Requirements 3.1, 3.4, 3.5**

### Property 6: Proactive Continuation Offer
*For any* response where `should_offer_continuation` is true, the AI response SHALL contain a continuation offer phrase.
**Validates: Requirements 3.2**

### Property 7: Deep Reasoning Disabled Mode
*For any* response with deep reasoning disabled, the response SHALL NOT contain `<thinking>` tags.
**Validates: Requirements 4.4**

### Property 8: Thinking Tags Well-Formed
*For any* response with `<thinking>` tags, the tags SHALL be properly closed and well-formed (matching open/close tags).
**Validates: Requirements 4.5**

### Property 9: User Facts Injection
*For any* prompt building operation with user facts from Vector DB, the resulting prompt SHALL contain all provided user facts.
**Validates: Requirements 5.2**

### Property 10: Vector DB Facts Priority
*For any* conflict between Vector DB facts and conversation-extracted facts, the System SHALL use Vector DB facts in the final prompt.
**Validates: Requirements 5.4**

### Property 11: Frontend Parsing Round-Trip
*For any* valid response with `<thinking>` tags, parsing then reconstructing the response SHALL produce an equivalent result.
**Validates: Requirements 6.1**

### Property 12: Frontend Error Resilience
*For any* malformed response (missing closing tags, invalid format), the frontend parser SHALL return the raw response without throwing an exception.
**Validates: Requirements 6.5**

## Error Handling

### Thinking Tag Parsing Errors
- If `<thinking>` tag is not closed, treat entire response as final answer
- If multiple `<thinking>` sections exist, use only the first one
- Log parsing errors for debugging but don't fail the request

### Context Building Errors
- If Vector DB query fails, proceed with empty user facts
- If chat history retrieval fails, proceed with empty conversation history
- Log errors and continue with degraded functionality

### Conversation Analysis Errors
- If topic extraction fails, set `should_offer_continuation` to false
- If incomplete detection fails, assume no incomplete explanations
- Never block response due to analysis errors

## Testing Strategy

### Property-Based Testing (Hypothesis)

The following properties will be tested using Hypothesis library:

1. **Thinking Tags Format Property**
   - Generate random responses with thinking sections
   - Verify format matches `<thinking>...</thinking>...` pattern

2. **Context Window Size Property**
   - Generate random message lists of varying sizes
   - Verify retrieval never exceeds 50 messages

3. **Blocked Messages Exclusion Property**
   - Generate random messages with random blocked flags
   - Verify only non-blocked messages appear in context

4. **Incomplete Topic Detection Property**
   - Generate random AI responses with incomplete indicators
   - Verify analyzer correctly identifies incomplete explanations

5. **Frontend Parsing Round-Trip Property**
   - Generate random valid responses with thinking sections
   - Verify parse(format(response)) == response

### Unit Tests

1. **ConversationAnalyzer Tests**
   - Test `detect_incomplete_explanation()` with various inputs
   - Test `extract_topic()` with maritime-specific content
   - Test `is_continuation_request()` with Vietnamese phrases

2. **DeepReasoningPromptBuilder Tests**
   - Test system prompt generation with user facts
   - Test thinking instructions format
   - Test proactive context injection

3. **Response Parser Tests**
   - Test parsing valid responses
   - Test parsing malformed responses
   - Test Clean Mode vs Debug Mode output

### Integration Tests

1. **End-to-End Deep Reasoning Flow**
   - Send message → Verify response has thinking tags
   - Verify thinking section contains reasoning
   - Verify final answer is coherent

2. **Proactive Continuation Flow**
   - Send incomplete explanation → Send new question
   - Verify AI offers to continue previous topic
