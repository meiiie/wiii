# Requirements Document

## Introduction

This feature migrates the Sparse Search functionality from Neo4j to Neon PostgreSQL using PostgreSQL's native full-text search capabilities (tsvector/tsquery). The goal is to simplify the architecture by consolidating all search functionality into a single database (Neon), while preserving Neo4j for future Learning Graph features.

Currently, the Hybrid Search system uses:
- **Dense Search**: Neon PostgreSQL with pgvector (semantic similarity)
- **Sparse Search**: Neo4j with full-text index (keyword matching)

After migration:
- **Dense Search**: Neon PostgreSQL with pgvector (unchanged)
- **Sparse Search**: Neon PostgreSQL with tsvector/tsquery (new)
- **Neo4j**: Reserved for future Learning Graph integration with LMS

## Glossary

- **Sparse Search**: Keyword-based search using term frequency and BM25-style scoring
- **Dense Search**: Vector similarity search using embeddings
- **tsvector**: PostgreSQL data type for full-text search document representation
- **tsquery**: PostgreSQL data type for full-text search queries
- **GIN Index**: Generalized Inverted Index for fast full-text search
- **Hybrid Search Service**: Service that combines Dense and Sparse search results using RRF reranking
- **RRF**: Reciprocal Rank Fusion algorithm for merging search results

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want sparse search to use PostgreSQL instead of Neo4j, so that I can reduce infrastructure complexity and costs.

#### Acceptance Criteria

1. WHEN the system performs a sparse search THEN the Sparse Search Repository SHALL query the knowledge_embeddings table using PostgreSQL full-text search
2. WHEN a new document is ingested THEN the system SHALL generate and store a tsvector representation in the knowledge_embeddings table
3. WHEN the sparse search is unavailable THEN the Hybrid Search Service SHALL fall back to dense-only search gracefully
4. WHEN Neo4j connection fails THEN the RAG system SHALL continue functioning using PostgreSQL-based search

### Requirement 2

**User Story:** As a developer, I want the knowledge_embeddings table to support full-text search, so that sparse search queries can be executed efficiently.

#### Acceptance Criteria

1. WHEN the migration runs THEN the system SHALL add a search_vector column of type tsvector to the knowledge_embeddings table
2. WHEN the migration runs THEN the system SHALL create a GIN index on the search_vector column for fast lookups
3. WHEN the migration runs THEN the system SHALL populate search_vector for all existing rows using content column
4. WHEN a new row is inserted THEN the system SHALL automatically generate the search_vector using a database trigger

### Requirement 3

**User Story:** As a user, I want keyword search to return relevant results with proper scoring, so that I can find maritime regulations by keywords.

#### Acceptance Criteria

1. WHEN a user searches with keywords THEN the system SHALL return results ranked by ts_rank score
2. WHEN a user searches with Vietnamese keywords THEN the system SHALL handle Vietnamese text appropriately using simple configuration
3. WHEN a user searches with rule numbers like "Rule 15" or "Điều 15" THEN the system SHALL boost results containing exact number matches in content
4. WHEN search results are returned THEN each result SHALL include node_id, content, score, and metadata fields

### Requirement 4

**User Story:** As a developer, I want the Sparse Search Repository to use PostgreSQL, so that the codebase is simplified and maintainable.

#### Acceptance Criteria

1. WHEN the Sparse Search Repository is initialized THEN it SHALL use the shared PostgreSQL connection pool
2. WHEN the search method is called THEN it SHALL execute a tsquery against the search_vector column
3. WHEN the repository is queried THEN it SHALL return SparseSearchResult objects compatible with the existing interface
4. WHEN the is_available method is called THEN it SHALL check PostgreSQL connectivity instead of Neo4j

### Requirement 5

**User Story:** As a system administrator, I want to remove Neo4j dependency from RAG search, so that the system is simpler to maintain and deploy.

#### Acceptance Criteria

1. WHEN the Hybrid Search Service initializes THEN it SHALL use the PostgreSQL-based Sparse Search Repository
2. WHEN health checks run THEN the system SHALL report sparse search health based on PostgreSQL status
3. WHEN the system starts THEN it SHALL NOT require Neo4j connection for RAG functionality
4. WHEN Neo4j is unavailable THEN the RAG search SHALL function normally using PostgreSQL

### Requirement 6

**User Story:** As a developer, I want backward compatibility maintained, so that existing code continues to work without changes.

#### Acceptance Criteria

1. WHEN the Sparse Search Repository is imported THEN it SHALL expose the same interface as the Neo4j-based version
2. WHEN the search method is called THEN it SHALL return SparseSearchResult with identical fields
3. WHEN the Hybrid Search Service uses sparse search THEN it SHALL work without code changes
4. WHEN tests run THEN all existing hybrid search tests SHALL pass
