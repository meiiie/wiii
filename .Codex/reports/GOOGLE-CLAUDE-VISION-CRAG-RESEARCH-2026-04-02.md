# Google + Claude Code Research For Vision / CRAG / Memory

Date: 2026-04-02

## Executive truth

Yes, Wiii should continue learning from both Claude Code and Google, but for different layers:

- Claude Code is most valuable for runtime discipline:
  - thought lifecycle invariants
  - fallback / retry / partial-state cleanup
  - preserving assistant trajectories across tool loops
- Google is most valuable for retrieval / multimodal / embedding strategy:
  - embeddings and multimodal embedding spaces
  - RAG robustness
  - long-term vector search efficiency

The Google `TurboQuant` article is relevant, but **not as the immediate next architecture move**.
It is a medium-term optimization topic for vector search and KV-cache compression, not the most urgent fix for Wiii's current `Vision + CRAG + Memory` architecture.

## What Wiii currently has in code

### 1. Query-time Visual RAG exists and is real

File: [visual_rag.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/visual_rag.py)

Current behavior:

- chooses retrieved docs with `image_url`
- fetches page images
- calls Gemini Vision directly
- appends visual description back into retrieved content

Important truth:

- this is already a real multimodal RAG path
- but it is still **Gemini-specific**, not provider-agnostic

### 2. Ingestion-time vision path also exists and is separate

Files:

- [vision_processor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/vision_processor.py)
- [vision_extractor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/vision_extractor.py)

Current behavior:

- page ingestion decides between direct text extraction and vision extraction
- if vision is used, the page can get visual descriptions for tables/diagrams/formulas
- chunk embeddings are now provider-agnostic
- but image understanding itself is still Gemini-bound

Important truth:

- Wiii currently has **two different vision-related surfaces**:
  - ingestion-time document understanding
  - query-time visual enrichment
- they do not yet share one provider-neutral `Vision Runtime` authority

### 3. Visual memory is half-modernized

File: [visual_memory.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/visual_memory.py)

Current behavior:

- image description is generated via Gemini directly
- storage/retrieval embeddings now go through shared embedding runtime

Important truth:

- visual memory already benefits from the new multi-socket embedding layer
- but the image caption/description step is still **hard-wired to Google**

### 4. CRAG + HyDE embeddings are already on the shared authority

Files:

- [corrective_rag_process_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/corrective_rag_process_runtime.py)
- [corrective_rag_runtime_support.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/corrective_rag_runtime_support.py)
- [hyde_generator.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/hyde_generator.py)

Current behavior:

- query embeddings resolve via shared embedding authority
- document-style embeddings for HyDE also resolve via shared embedding authority
- CRAG cache and retrieval degrade more honestly when embeddings are unavailable

Important truth:

- text-side embedding infrastructure is now much healthier than image/vision-side runtime

## What Claude Code is useful for here

Local references:

- [query.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/query.ts)
- [QueryEngine.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/QueryEngine.ts)
- [errors.ts](E:/Sach/Sua/test/claude_lo/claude-code/src/services/api/errors.ts)

Key lessons that transfer well to Wiii:

1. Preserve trajectory invariants
- thinking/tool blocks are treated as a lifecycle, not ad-hoc text
- retries and fallback reset partial state carefully

2. Clean error taxonomy
- auth/rate-limit/media/prompt-too-long/timeout are classified explicitly
- this reduces fake recoveries and misleading UI

3. Fallback with state hygiene
- when model fallback happens, partial tool/thinking state is tombstoned or rebuilt
- this is exactly the kind of discipline Wiii needs in `direct stream` and later `vision/runtime` failover

What Claude Code is **not** the best template for:

- multimodal RAG architecture
- document vision ingestion
- image-grounded retrieval

Its image support is mostly attachment-oriented, not a full `Visual RAG + CRAG + visual memory` stack.

## What Google is useful for here

### A. Immediately relevant

1. Gemini embeddings docs
Source: [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings)

Why it matters:

- confirms multimodal embedding space is now a first-class concept
- reinforces that text/image/document retrieval should be reasoned about as space contracts, not just vector lengths

2. Vertex AI RAG Engine overview
Source: [Vertex AI RAG Engine overview](https://cloud.google.com/vertex-ai/generative-ai/docs/rag-overview)

Why it matters:

- useful as a systems reference for managed RAG patterns
- especially helpful for separation between retrieval infrastructure and generation infrastructure

3. Astute RAG
Source: [Astute RAG](https://research.google/pubs/astute-rag-overcoming-imperfect-retrieval-augmentation-and-knowledge-conflicts-for-large-language-models/)

Why it matters:

- directly relevant to Wiii because CRAG is already trying to handle imperfect retrieval
- strong signal that post-retrieval conflict handling matters as much as retrieval quality

### B. Relevant, but not first priority

4. TurboQuant
Source: [TurboQuant blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)

What it is about:

- extreme vector compression for vector search
- KV-cache compression
- reducing memory overhead while preserving retrieval quality

Why it matters to Wiii later:

- semantic memory and knowledge vector stores may benefit from storage/index compression
- future shadow-index or multi-index systems could use compressed serving tiers
- if Wiii grows large org knowledge corpora, this becomes strategically important

Why it is **not** the immediate next move:

- it does not solve current correctness issues in vision/runtime/provider abstraction
- it does not directly solve Wiii's current `Gemini-only vision` bottleneck
- it does not replace the need for a unified `Vision Runtime authority`

## Recommendation

### Short answer

Yes, we should study Google.

But for current Wiii work, the priority order should be:

1. Google on multimodal embeddings + robust RAG
2. Claude Code on lifecycle/fallback/state hygiene
3. TurboQuant later for scale/efficiency optimization

### The architecture move that now makes most sense

After `Thinking Lifecycle` and `Embedding Runtime`, Wiii should build:

## Vision Runtime authority

A single backend authority for image understanding that serves:

- query-time `Visual RAG`
- ingestion-time `Vision Processor`
- `Visual Memory` image description

It should define:

- provider/model contract
- capability types:
  - `ocr_extract`
  - `visual_describe`
  - `grounded_visual_answer`
- failover behavior
- latency/quality tiers
- provenance in metadata
- safe degradation when no vision-capable provider is available

### Why this is the right next system

Because today Wiii has:

- modernized text embeddings
- shadow migration for embedding spaces
- healthier CRAG text retrieval

But still has fragmented image intelligence:

- `visual_rag.py` uses Gemini directly
- `vision_extractor.py` uses Gemini directly
- `visual_memory.py` uses Gemini directly

That means the next real bottleneck is no longer embeddings alone.
It is **vision authority fragmentation**.

## Concrete next steps

1. Create `vision_runtime.py`
- single provider-neutral gateway for image understanding

2. Migrate these callsites onto it
- [visual_rag.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/agentic_rag/visual_rag.py)
- [vision_extractor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/vision_extractor.py)
- [visual_memory.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/visual_memory.py)

3. Define fail-closed vs fail-open paths
- OCR extraction for ingestion may need a stronger fail path
- visual enrichment at query time can degrade more softly
- visual memory captioning can fallback to metadata-only storage if needed

4. Only after that, revisit compression/efficiency
- compressed vector tiers
- quantized ANN
- TurboQuant-style ideas

## Final judgment

The user intuition was correct in two ways:

- there really is a meaningful `Vision / CRAG / Memory` cluster in the codebase
- Google is worth studying here

But the most accurate strategic takeaway is:

- **Claude Code teaches Wiii how to keep runtime state honest**
- **Google teaches Wiii how to think about multimodal retrieval and future vector efficiency**
- **TurboQuant is valuable, but it belongs after Wiii has a unified vision runtime**
