# RAG System Testing Guide

This document describes the test suites for measuring retrieval accuracy and performance of the Buddhist RAG system.

## Test Files

### 1. `test_ollama_embeddings.py`
**Purpose**: Test Ollama embeddings API integration
**What it tests**:
- API connectivity to `http://ollama.changpt.org`
- Embedding generation for single and batch texts
- Embedding dimension verification (1024 for bge-m3)
- Semantic similarity accuracy

**Usage**:
```bash
source venv/bin/activate
python test_ollama_embeddings.py
```

**Expected output**:
- ✓ Connection test passes
- ✓ Embedding dimension: 1024
- ✓ Semantic similarity: Similar texts have higher scores (>0.85)

---

### 2. `quick_test_retrieval.py`
**Purpose**: Quick smoke test for retrieval system
**What it tests**:
- 5 key queries across different Buddhist topics
- Basic retrieval functionality
- Response times
- Top-3 results quality

**Usage**:
```bash
source venv/bin/activate
python quick_test_retrieval.py
```

**Test queries**:
1. 四聖諦的意義是什麼？ (Four Noble Truths)
2. 如何修習禪定？ (Meditation practice)
3. 什麼是五戒？ (Five Precepts)
4. 念佛的方法 (Buddhist chanting)
5. 什麼是空？ (Emptiness)

**Expected output**:
- All 5 queries should succeed
- Average retrieval time: < 2 seconds
- Each query returns 3 relevant results

---

### 3. `test_retrieval_accuracy.py`
**Purpose**: Comprehensive retrieval accuracy and performance testing
**What it tests**:
- 21 test cases across 9 categories
- Keyword matching accuracy
- Topic relevance
- Retrieval performance metrics
- Category-specific pass rates

**Test Categories**:
1. **Core Teachings** (4 tests): Four Noble Truths, Eightfold Path, Five Aggregates, Three Dharma Seals
2. **Practice** (3 tests): Meditation, chanting, Bodhicitta
3. **Ethics** (2 tests): Five Precepts, Six Perfections
4. **Cosmology** (2 tests): Karma, life and death
5. **Pure Land** (2 tests): Pure Land, rebirth
6. **Buddhist Figures** (2 tests): Avalokitesvara, Buddha
7. **Monastic Life** (1 test): Ordination
8. **Daily Life** (2 tests): Daily practice, afflictions
9. **Philosophy** (2 tests): Emptiness, non-self
10. **Advanced** (2 tests): Enlightenment, Buddhism & science

**Usage**:
```bash
source venv/bin/activate
python test_retrieval_accuracy.py
```

**Output**:
- Detailed results for each test case
- Overall pass rate (target: >70%)
- Performance metrics (avg, min, max, median retrieval times)
- Relevance scores (avg, min, max, median)
- Category breakdown
- JSON report saved to `retrieval_test_report.json`

**Pass Criteria**:
Each test passes if:
- ≥50% of expected keywords are found OR ≥33% of expected topics are found
- AND average relevance score ≥ minimum threshold (0.3-0.6 depending on difficulty)

**Interpreting Results**:

```
Overall Results:
  Total tests: 21
  Passed: 18 (85.7%)      ← Target: >70%
  Failed: 3

Performance:
  Avg retrieval time: 0.245s   ← Target: <2.0s
  Min retrieval time: 0.102s
  Max retrieval time: 0.582s
  Median retrieval time: 0.221s

Relevance Scores:
  Avg score: 0.673        ← Higher is better (range: 0-1)
  Min score: 0.234
  Max score: 0.912
  Median score: 0.689

By Category:
  core_teachings: 4/4 (100.0%)    ← Core concepts should have high accuracy
  practice: 3/3 (100.0%)
  ethics: 2/2 (100.0%)
  cosmology: 2/2 (100.0%)
  pure_land: 2/2 (100.0%)
  figures: 2/2 (100.0%)
  monastic: 1/1 (100.0%)
  daily_life: 1/2 (50.0%)
  philosophy: 2/2 (100.0%)
  advanced: 1/2 (50.0%)          ← Advanced queries may have lower accuracy
```

---

## Running Tests

### Prerequisites
1. Server is running: `python main.py`
2. System is initialized: `POST /initialize` with `recreate_collection=true`
3. Ollama embeddings configured in `.env`:
   ```
   EMBEDDING_PROVIDER=ollama
   EMBEDDING_MODEL=bge-m3
   EMBEDDING_DIMENSION=1024
   OLLAMA_BASE_URL=http://ollama.changpt.org
   OLLAMA_API_KEY=ddm_api_key
   ```

### Test Sequence

```bash
# 1. Test Ollama embeddings API (isolated)
python test_ollama_embeddings.py

# 2. Wait for system initialization to complete
curl http://localhost:8000/health
# Check: "initialized": true

# 3. Quick smoke test
python quick_test_retrieval.py

# 4. Comprehensive accuracy test
python test_retrieval_accuracy.py

# 5. Review detailed report
cat retrieval_test_report.json | jq .
```

---

## Performance Benchmarks

### Ollama Embeddings (bge-m3, 1024-dim)

**Initialization**:
- Time to embed 1,067 chunks: ~60-90 minutes (depends on API response time)
- Batch size: 50 chunks per batch
- Total batches: 22

**Query Performance**:
- Target: < 2 seconds per query
- Expected: 0.2-0.5 seconds (depending on network latency to Ollama API)

**Retrieval Accuracy**:
- Target pass rate: >70%
- Expected: 80-90% for well-defined queries
- Expected: 50-70% for ambiguous/advanced queries

---

## Comparison: Local vs Ollama Embeddings

| Metric | Local BGE-small-zh-v1.5 (512-dim) | Ollama bge-m3 (1024-dim) |
|--------|-----------------------------------|--------------------------|
| Initialization time | ~90 seconds | ~60-90 minutes |
| Query time | ~0.1-0.2s | ~0.2-0.5s |
| Embedding quality | Good for Chinese | Better multilingual |
| Vector dimension | 512 | 1024 |
| Cost | Free (local GPU/CPU) | Potential API costs |
| Dependency | Requires local model | Requires network |

---

## Troubleshooting

### Test fails with "System not initialized"
**Solution**: Wait for initialization to complete or restart initialization:
```bash
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{"recreate_collection": true}'
```

### Test fails with connection error
**Solution**: Check server is running:
```bash
curl http://localhost:8000/health
```

### Low pass rate (<50%)
**Possible causes**:
1. Wrong embedding provider (check `.env`)
2. Dimension mismatch (query embeddings vs stored embeddings)
3. Collection not properly initialized

**Solution**: Reinitialize with correct settings:
```bash
# Verify .env settings
grep EMBEDDING .env

# Reinitialize
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{"recreate_collection": true}'
```

### Slow retrieval (>2s per query)
**Possible causes**:
1. Ollama API slow response
2. Network latency
3. Large top_k value

**Solution**:
- Check Ollama API health: `curl http://ollama.changpt.org/api/tags`
- Reduce top_k in tests
- Consider using local embeddings for faster queries

---

## Test Data Sources

All test queries are based on actual content in the corpus:
- **Source**: `chunks/text_chunks.jsonl` (1,067 Buddhist text chunks)
- **Content**: 12 books by Master Sheng Yen (聖嚴法師)
- **Topics**: Buddhist philosophy, meditation, ethics, Pure Land, daily life application

Test cases are designed to cover:
1. **Common queries**: Basic Buddhist concepts (80% of queries)
2. **Advanced queries**: Complex philosophical topics (10% of queries)
3. **Ambiguous queries**: Open-ended questions (10% of queries)

---

## Continuous Testing

### Regular Testing Schedule
1. **After every embedding model change**: Run full test suite
2. **After data updates**: Run accuracy tests
3. **Before production deployment**: Run all tests

### Regression Testing
When making changes:
1. Save current `retrieval_test_report.json` as baseline
2. Make changes
3. Reinitialize system
4. Run tests again
5. Compare new report with baseline

### Metrics to Track Over Time
- Pass rate by category
- Average retrieval time
- Average relevance score
- Failed test patterns

---

## Adding New Test Cases

To add new test cases, edit `test_retrieval_accuracy.py`:

```python
TestCase(
    query="Your test query here",
    category="appropriate_category",  # core_teachings, practice, etc.
    expected_keywords=["keyword1", "keyword2", "keyword3"],
    expected_topics=["Topic from chunk header"],
    min_relevance_score=0.5,  # Adjust based on query difficulty
    description="Brief description of what this tests"
)
```

**Guidelines**:
- Use actual content from the corpus
- Include 3-5 expected keywords
- Include 1-3 expected topics (from chunk headers)
- Set realistic `min_relevance_score` (0.3 for hard, 0.5 for medium, 0.6 for easy)
- Test the query manually first to verify expected results exist

---

## Report Analysis

The JSON report includes:
- `summary`: Overall statistics
- `performance`: Timing metrics
- `relevance`: Score metrics
- `by_category`: Category breakdown
- `failed_tests`: Details of failures
- `detailed_results`: Full results for each test case

Use for:
1. Identifying weak categories
2. Performance regression detection
3. Embedding model comparison
4. System optimization prioritization
