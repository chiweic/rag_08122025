#!/usr/bin/env python3
"""
Test script for primary query endpoint (full RAG pipeline)
Tests retrieval + synthesis with LLM answer generation
"""

import requests
import json
import time
from typing import List, Dict

BASE_URL = "http://localhost:8000"

# Test queries covering different Buddhist topics and complexity levels
TEST_QUERIES = [
    {
        "query": "什麼是四聖諦？",
        "description": "Basic Buddhist doctrine - Four Noble Truths",
        "expected_keywords": ["苦", "集", "滅", "道"],
        "top_k": 5,
        "include_sources": True
    },
    {
        "query": "如何開始禪修？",
        "description": "Practical meditation guidance for beginners",
        "expected_keywords": ["禪", "呼吸", "坐"],
        "top_k": 5,
        "include_sources": True
    },
    {
        "query": "什麼是五戒？",
        "description": "Five Precepts in Buddhism",
        "expected_keywords": ["戒", "不殺"],
        "top_k": 3,
        "include_sources": True
    },
    {
        "query": "念佛的正確方法是什麼？",
        "description": "Pure Land practice methodology",
        "expected_keywords": ["念佛", "阿彌陀佛"],
        "top_k": 5,
        "include_sources": True
    },
    {
        "query": "什麼是空性？",
        "description": "Emptiness teaching - advanced concept",
        "expected_keywords": ["空", "緣起"],
        "top_k": 5,
        "include_sources": True
    },
    {
        "query": "如何在日常生活中修行？",
        "description": "Daily Buddhist practice integration",
        "expected_keywords": ["生活", "修行"],
        "top_k": 5,
        "include_sources": True
    },
    {
        "query": "什麼是菩薩道？",
        "description": "Bodhisattva path teaching",
        "expected_keywords": ["菩薩", "利他"],
        "top_k": 5,
        "include_sources": True
    },
    {
        "query": "聖嚴法師對禪修的教導",
        "description": "Master Sheng Yen's meditation teachings",
        "expected_keywords": ["聖嚴", "禪"],
        "top_k": 5,
        "include_sources": True
    }
]


def test_query(test_case: Dict) -> Dict:
    """Test a single query through the full RAG pipeline"""
    query = test_case["query"]
    description = test_case["description"]
    top_k = test_case.get("top_k", 5)
    include_sources = test_case.get("include_sources", True)

    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"Description: {description}")
    print(f"Top K: {top_k} | Include Sources: {include_sources}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/query",
            json={
                "question": query,
                "top_k": top_k,
                "include_sources": include_sources,
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()

        elapsed = time.time() - start_time

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        computation_time = result.get("computation_time", {})

        print(f"\n✓ Request successful")
        print(f"Total time: {elapsed:.3f}s")
        print(f"Retrieval time: {computation_time.get('retrieval_time', 0):.3f}s")
        print(f"Synthesis time: {computation_time.get('synthesis_time', 0):.3f}s")

        # Check answer quality
        answer_length = len(answer)
        print(f"\nAnswer length: {answer_length} characters")

        if answer_length == 0:
            print(f"\n⚠️  Empty answer returned")
            return {
                "query": query,
                "success": True,
                "answer_length": 0,
                "sources_count": len(sources),
                "elapsed": elapsed,
                "passed": False,
                "reason": "Empty answer"
            }

        # Display answer preview
        if answer_length > 300:
            print(f"\nAnswer preview:\n{answer[:300]}...")
        else:
            print(f"\nAnswer:\n{answer}")

        # Display sources
        print(f"\nSources found: {len(sources)}")
        for i, source in enumerate(sources[:3]):  # Show first 3 sources
            print(f"\n--- Source {i+1} ---")
            print(f"Title: {source.get('title', 'N/A')}")
            print(f"Score: {source.get('score', 0):.4f}")
            print(f"Source Type: {source.get('source_type', 'N/A')}")

            # Show text preview
            text = source.get('text', '')
            if text and len(text) > 100:
                print(f"Text: {text[:100]}...")
            elif text:
                print(f"Text: {text}")

        # Validation checks
        passed = True
        reasons = []

        # Check minimum answer length
        if answer_length < 20:
            passed = False
            reasons.append(f"Answer too short ({answer_length} chars)")

        # Check if sources were retrieved
        if include_sources and len(sources) == 0:
            passed = False
            reasons.append("No sources retrieved")

        # Check expected keywords in answer
        if "expected_keywords" in test_case:
            expected_keywords = test_case["expected_keywords"]
            answer_lower = answer.lower()
            found_keywords = []

            for keyword in expected_keywords:
                if keyword.lower() in answer_lower:
                    found_keywords.append(keyword)

            print(f"\nKeyword Check:")
            print(f"  Expected: {expected_keywords}")
            print(f"  Found in answer: {found_keywords}")

            # Don't fail if keywords not found (LLM may use synonyms)
            if not found_keywords:
                print(f"  ⚠️  Note: Expected keywords not found, but LLM may use different terminology")

        # Check source relevance
        if sources:
            avg_score = sum(s.get('score', 0) for s in sources) / len(sources)
            min_score = min(s.get('score', 0) for s in sources)
            max_score = max(s.get('score', 0) for s in sources)

            print(f"\nSource Relevance Scores:")
            print(f"  Average: {avg_score:.4f}")
            print(f"  Min: {min_score:.4f}")
            print(f"  Max: {max_score:.4f}")

            if avg_score < 0.3:
                print(f"  ⚠️  Low average relevance score")

        if passed:
            print(f"\n✅ Test PASSED")
        else:
            print(f"\n❌ Test FAILED: {', '.join(reasons)}")

        return {
            "query": query,
            "success": True,
            "answer_length": answer_length,
            "sources_count": len(sources),
            "elapsed": elapsed,
            "retrieval_time": computation_time.get('retrieval_time', 0),
            "synthesis_time": computation_time.get('synthesis_time', 0),
            "avg_score": avg_score if sources else 0,
            "passed": passed,
            "reasons": reasons,
            "answer_preview": answer[:200] if len(answer) > 200 else answer
        }

    except requests.exceptions.Timeout:
        print(f"\n❌ Request timeout (>60s)")
        return {
            "query": query,
            "success": False,
            "error": "Timeout",
            "elapsed": time.time() - start_time,
            "passed": False
        }
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        return {
            "query": query,
            "success": False,
            "error": str(e),
            "elapsed": time.time() - start_time,
            "passed": False
        }
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return {
            "query": query,
            "success": False,
            "error": str(e),
            "elapsed": time.time() - start_time,
            "passed": False
        }


def test_streaming_query():
    """Test streaming query endpoint"""
    print(f"\n{'='*80}")
    print(f"Testing /query/stream endpoint")
    print(f"{'='*80}")

    query = "什麼是禪修？"

    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/query/stream",
            json={
                "question": query,
                "top_k": 3,
                "include_sources": True
            },
            stream=True,
            timeout=60
        )
        response.raise_for_status()

        print(f"Query: {query}")
        print(f"\nStreaming response:")
        print("-" * 80)

        chunks_received = 0
        answer_chunks = []
        sources_received = False

        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    chunks_received += 1
                    data_str = line_str[6:]  # Remove 'data: ' prefix

                    if data_str == '[DONE]':
                        break

                    try:
                        data = json.loads(data_str)
                        chunk_type = data.get('type')

                        if chunk_type == 'answer':
                            content = data.get('content', '')
                            answer_chunks.append(content)
                            print(content, end='', flush=True)
                        elif chunk_type == 'sources':
                            sources_received = True
                            sources = data.get('sources', [])
                            print(f"\n\n[Sources: {len(sources)} documents]")
                        elif chunk_type == 'done':
                            elapsed = time.time() - start_time
                            print(f"\n\n[Done - Total time: {elapsed:.2f}s]")

                    except json.JSONDecodeError:
                        pass

        print("\n" + "-" * 80)

        full_answer = ''.join(answer_chunks)
        print(f"\n✓ Streaming test completed")
        print(f"Chunks received: {chunks_received}")
        print(f"Answer length: {len(full_answer)} characters")
        print(f"Sources received: {'Yes' if sources_received else 'No'}")

        return chunks_received > 0 and len(full_answer) > 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Run all query pipeline tests"""
    print(f"\n{'#'*80}")
    print(f"# QUERY PIPELINE TEST SUITE")
    print(f"# Testing {len(TEST_QUERIES)} full RAG queries (Retrieval + Synthesis)")
    print(f"{'#'*80}")

    # Check system health
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5).json()
        print(f"\nSystem Status:")
        print(f"  Initialized: {health.get('initialized')}")
        print(f"  Vector store connected: {health.get('vector_store_connected')}")
        print(f"  Pipeline ready: {health.get('pipeline_ready')}")

        qdrant_info = health.get('qdrant_collection', {})
        print(f"  Qdrant points: {qdrant_info.get('points_count', 'N/A')}")

        if not health.get("initialized"):
            print("\n❌ System not initialized. Please run initialization first.")
            return

    except Exception as e:
        print(f"\n❌ Cannot connect to server: {e}")
        return

    # Run query tests
    results = []
    for test_case in TEST_QUERIES:
        result = test_query(test_case)
        results.append(result)
        time.sleep(1)  # Small delay between requests

    # Test streaming endpoint
    print(f"\n{'='*80}")
    streaming_success = test_streaming_query()

    # Summary
    print(f"\n{'#'*80}")
    print(f"# TEST SUMMARY")
    print(f"{'#'*80}")

    successful_requests = sum(1 for r in results if r.get("success"))
    passed_tests = sum(1 for r in results if r.get("passed"))
    total_time = sum(r.get("elapsed", 0) for r in results)
    avg_time = total_time / len(results) if results else 0

    # Calculate timing statistics
    results_with_times = [r for r in results if r.get("success")]
    avg_retrieval = sum(r.get("retrieval_time", 0) for r in results_with_times) / len(results_with_times) if results_with_times else 0
    avg_synthesis = sum(r.get("synthesis_time", 0) for r in results_with_times) / len(results_with_times) if results_with_times else 0

    # Calculate answer statistics
    avg_answer_length = sum(r.get("answer_length", 0) for r in results_with_times) / len(results_with_times) if results_with_times else 0
    avg_sources = sum(r.get("sources_count", 0) for r in results_with_times) / len(results_with_times) if results_with_times else 0
    avg_relevance = sum(r.get("avg_score", 0) for r in results_with_times) / len(results_with_times) if results_with_times else 0

    print(f"\nSuccessful requests: {successful_requests}/{len(results)}")
    print(f"Tests passed: {passed_tests}/{len(results)}")
    print(f"Total time: {total_time:.3f}s")
    print(f"Average time per query: {avg_time:.3f}s")
    print(f"  - Average retrieval time: {avg_retrieval:.3f}s")
    print(f"  - Average synthesis time: {avg_synthesis:.3f}s")
    print(f"\nAnswer Quality:")
    print(f"  Average answer length: {avg_answer_length:.0f} characters")
    print(f"  Average sources per query: {avg_sources:.1f}")
    print(f"  Average source relevance: {avg_relevance:.4f}")
    print(f"\nStreaming endpoint: {'✓' if streaming_success else '✗'}")

    # Show failed tests
    failed = [r for r in results if not r.get("passed")]
    if failed:
        print(f"\n⚠️  Failed Tests:")
        for r in failed:
            reasons = r.get("reasons", ["Unknown error"])
            print(f"  - {r['query']}: {', '.join(reasons)}")

    if passed_tests == len(results) and streaming_success:
        print(f"\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  Some tests failed")

    # Save results to JSON
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_tests": len(results),
        "successful_requests": successful_requests,
        "passed_tests": passed_tests,
        "avg_time": avg_time,
        "avg_retrieval_time": avg_retrieval,
        "avg_synthesis_time": avg_synthesis,
        "avg_answer_length": avg_answer_length,
        "avg_sources": avg_sources,
        "avg_relevance": avg_relevance,
        "streaming_success": streaming_success,
        "test_results": results
    }

    with open("query_pipeline_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Detailed report saved to: query_pipeline_test_report.json")


if __name__ == "__main__":
    main()
