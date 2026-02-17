# Tests

Test suites for Wiii.

---

## 📁 Structure

```
tests/
├── unit/           # Unit tests (38 files)
├── integration/    # Integration tests (8 files)
├── property/       # Property-based tests (11 files)
├── e2e/            # End-to-end tests (12 files)
└── conftest.py     # Pytest fixtures
```

---

## 🚀 Running Tests

```bash
# All tests
pytest tests/ -v

# Specific category
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/property/ -v
pytest tests/e2e/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

---

## 📊 Test Categories

### Unit Tests (`unit/`)
- Individual component tests
- Mock external dependencies
- Fast execution

### Integration Tests (`integration/`)
- Component interaction tests
- Real database (test instance)
- API endpoint tests

### Property Tests (`property/`)
- Hypothesis-based property testing
- Chunking properties
- Grading properties

### E2E Tests (`e2e/`)
- Full flow tests
- Production-like environment
- SSE streaming tests

---

## 🔧 Fixtures

Common fixtures defined in `conftest.py`:
- `test_client` - FastAPI test client
- `test_db` - Test database session
- `mock_llm` - Mocked LLM responses
