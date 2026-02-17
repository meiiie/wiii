# LangChain RAG Pipeline Skill

## Description
LangChain 0.3.x RAG (Retrieval-Augmented Generation) patterns for building AI-powered Q&A systems with ChromaDB and Google Gemini.

## Architecture
```
Query → Retriever → Reranker → Context Builder → LLM → Response
              ↓
         Vector DB (ChromaDB)
         + BM25 (Keyword Search)
```

## Core Components

### 1. Embeddings
```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=settings.GOOGLE_API_KEY,
)
```

### 2. Vector Store (ChromaDB)
```python
from langchain_chroma import Chroma

vectorstore = Chroma(
    persist_directory="./data/chroma_db",
    embedding_function=embeddings,
    collection_name="vbpl_documents",
)

# Add documents
vectorstore.add_texts(
    texts=["Document content..."],
    metadatas=[{"source": "vbpl.vn", "doc_id": "123"}],
)

# Search
results = vectorstore.similarity_search_with_score(
    query="search query",
    k=10,
    filter={"source": "vbpl.vn"},
)
```

### 3. LLM (Gemini)
```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-3.0-flash",
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=0.2,
    convert_system_message_to_human=True,
)

# Async invocation
response = await llm.ainvoke(prompt)
```

### 4. Hybrid Retriever (Semantic + BM25)
```python
from rank_bm25 import BM25Okapi

class HybridRetriever:
    def __init__(self, vectorstore, documents):
        self.vectorstore = vectorstore
        # Build BM25 index
        tokenized = [doc.split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized)

    async def retrieve(self, query: str, k: int = 10):
        # Semantic search
        semantic = self.vectorstore.similarity_search_with_score(query, k=k)

        # BM25 search
        tokenized_query = query.split()
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # Reciprocal Rank Fusion
        return self._rrf_fusion(semantic, bm25_scores)

    def _rrf_fusion(self, semantic, bm25, k=60):
        """Combine rankings using RRF"""
        scores = {}
        for rank, (doc, _) in enumerate(semantic):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank)
        # ... similar for BM25
        return sorted(scores.items(), key=lambda x: -x[1])
```

### 5. Prompt Templates
```python
from langchain.prompts import PromptTemplate

QA_PROMPT = PromptTemplate.from_template("""
Dựa trên các văn bản pháp luật sau đây, hãy trả lời câu hỏi.

=== VĂN BẢN THAM KHẢO ===
{context}
=== HẾT VĂN BẢN ===

CÂU HỎI: {question}

YÊU CẦU:
- Trích dẫn cụ thể Điều, Khoản, Điểm
- Ghi rõ số hiệu văn bản
- Nếu không tìm thấy, nói rõ

TRẢ LỜI:
""")
```

### 6. RAG Engine
```python
class RAGEngine:
    async def chat(self, query: str) -> dict:
        # 1. Retrieve
        docs = await self.retriever.retrieve(query)

        # 2. Build context
        context = self._build_context(docs)

        # 3. Generate
        prompt = QA_PROMPT.format(context=context, question=query)
        response = await self.llm.ainvoke(prompt)

        # 4. Extract sources
        sources = self._extract_sources(docs)

        return {
            "answer": response.content,
            "sources": sources,
        }
```

## Vietnamese Legal Document Handling

### Structure-Aware Chunking
```python
import re

ARTICLE_PATTERN = re.compile(r'(Điều\s+\d+[a-z]?\.?\s*[^\n]*)', re.UNICODE)

def chunk_legal_document(text: str, metadata: dict):
    articles = ARTICLE_PATTERN.split(text)
    chunks = []
    for i in range(1, len(articles), 2):
        title = articles[i]
        content = articles[i + 1] if i + 1 < len(articles) else ""
        chunks.append({
            "content": f"{title}\n{content}",
            "metadata": {**metadata, "article": title.strip()},
        })
    return chunks
```

### Metadata Schema
```python
document_metadata = {
    "document_number": "12/2024/NĐ-CP",  # Số hiệu
    "title": "Nghị định về...",           # Tiêu đề
    "issuing_body": "Chính phủ",          # Cơ quan ban hành
    "effective_date": "2024-03-01",       # Ngày hiệu lực
    "status": "còn hiệu lực",             # Trạng thái
    "source_url": "https://vbpl.vn/...",  # Nguồn
    "article": "Điều 5",                   # Điều khoản (for chunks)
}
```

## Best Practices

1. **Chunk Size**: 800-1200 tokens for legal documents
2. **Overlap**: 200 tokens to preserve context
3. **Always cite sources** in responses
4. **Warn about outdated info** when document status is unclear
5. **Use streaming** for better UX with long responses
6. **Log retrieval metrics** for debugging and improvement
