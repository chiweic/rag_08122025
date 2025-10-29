#!/usr/bin/env python3
"""
Test script for audio recommendation endpoint
Tests semantic search for Buddhist audio teachings using Qdrant vector store
"""

import requests
import json
import time
from typing import List, Dict

BASE_URL = "http://localhost:8000"

# Test queries covering different audio teaching topics
TEST_QUERIES = [
    {
        "query_and_answer": "什麼是禪修？禪修是修習禪定的方法，透過觀察呼吸和身心來培養專注力。",
        "description": "Meditation practice explanation",
        "expected_keywords": ["禪修", "禪"],
        "top_k": 3
    },
    {
        "query_and_answer": "四聖諦是什麼？四聖諦包括苦、集、滅、道，是佛教的核心教義。",
        "description": "Four Noble Truths teaching",
        "expected_keywords": ["四聖諦", "苦", "道"],
        "top_k": 3
    },
    {
        "query_and_answer": "如何修習念佛？念佛是專注於佛號，培養正念和信心的修行方法。",
        "description": "Buddhist chanting practice",
        "expected_keywords": ["念佛", "修"],
        "top_k": 3
    },
    {
        "query_and_answer": "什麼是空性？空性是指一切事物沒有獨立自性，都是因緣和合而生。",
        "description": "Emptiness teaching",
        "expected_keywords": ["空", "因緣"],
        "top_k": 3
    },
    {
        "query_and_answer": "如何在日常生活中修行？日常修行包括正念覺察、慈悲心和布施等實踐。",
        "description": "Daily practice guidance",
        "expected_keywords": ["日常", "修行", "生活"],
        "top_k": 5
    },
    {
        "query_and_answer": "什麼是菩薩道？菩薩道是發菩提心，自利利他，廣度眾生的修行之道。",
        "description": "Bodhisattva path teaching",
        "expected_keywords": ["菩薩", "眾生"],
        "top_k": 3
    }
]


def test_audio_recommendation(test_case: Dict) -> Dict:
    """Test a single audio recommendation query"""
    query_and_answer = test_case["query_and_answer"]
    description = test_case["description"]
    top_k = test_case.get("top_k", 3)

    print(f"\n{'='*80}")
    print(f"Query: {query_and_answer}")
    print(f"Description: {description}")
    print(f"Top K: {top_k}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/audio/recommend",
            json={
                "query_and_answer": query_and_answer,
                "top_k": top_k,
                "min_similarity": 0.1
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        elapsed = time.time() - start_time
        recommendations = result.get("recommendations", [])
        count = result.get("count", 0)

        print(f"\n✓ Request successful")
        print(f"Response time: {elapsed:.3f}s")
        print(f"Audio chunks found: {count}")

        # Analyze results
        if count == 0:
            print(f"\n⚠️  No audio chunks found for query")
            return {
                "query": query_and_answer[:50] + "...",
                "success": True,
                "count": 0,
                "elapsed": elapsed,
                "passed": False,
                "reason": "No results"
            }

        # Display recommendations
        for i, audio in enumerate(recommendations):
            print(f"\n--- Audio {i+1} ---")
            print(f"Title: {audio.get('audio_title', 'N/A')}")
            print(f"Speaker: {audio.get('speaker', 'N/A')}")
            print(f"Section: {audio.get('section', 'N/A')}")
            print(f"Timestamp: {audio.get('timestamp_start', 'N/A')} - {audio.get('timestamp_end', 'N/A')}")
            print(f"Audio URL: {audio.get('audio_url', 'N/A')}")
            print(f"Similarity Score: {audio.get('similarity_score', 0.0):.4f}")
            print(f"Relevance: {audio.get('relevance', 'N/A')}")

            # Show brief content
            header = audio.get('header', '')
            content = audio.get('content', '')
            if header:
                print(f"Header: {header[:100]}...")
            if content and len(content) > 200:
                print(f"Content: {content[:200]}...")
            elif content:
                print(f"Content: {content}")

        # Validation checks
        passed = True
        reasons = []

        # Check expected keywords
        if "expected_keywords" in test_case:
            expected_keywords = test_case["expected_keywords"]
            found_keywords = []

            for audio in recommendations:
                audio_text = (
                    f"{audio.get('audio_title', '')} "
                    f"{audio.get('header', '')} "
                    f"{audio.get('content', '')}"
                ).lower()

                for keyword in expected_keywords:
                    if keyword.lower() in audio_text and keyword not in found_keywords:
                        found_keywords.append(keyword)

            print(f"\nKeyword Check:")
            print(f"  Expected: {expected_keywords}")
            print(f"  Found: {found_keywords}")

            if not found_keywords:
                passed = False
                reasons.append("No expected keywords found")

        # Check similarity scores
        scores = [a.get('similarity_score', 0) for a in recommendations]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        print(f"\nSimilarity Scores:")
        print(f"  Average: {avg_score:.4f}")
        print(f"  Min: {min_score:.4f}")
        print(f"  Max: {max_score:.4f}")

        if avg_score < 0.3:
            print(f"⚠️  Low average similarity score: {avg_score:.4f}")

        # Check speaker diversity
        speakers = set(a.get('speaker', 'Unknown') for a in recommendations)
        print(f"\nSpeakers: {', '.join(speakers)}")

        if passed:
            print(f"\n✅ Test PASSED")
        else:
            print(f"\n❌ Test FAILED: {', '.join(reasons)}")

        return {
            "query": query_and_answer[:50] + "...",
            "success": True,
            "count": count,
            "elapsed": elapsed,
            "avg_score": avg_score,
            "min_score": min_score,
            "max_score": max_score,
            "speakers": list(speakers),
            "passed": passed,
            "reasons": reasons
        }

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        return {
            "query": query_and_answer[:50] + "...",
            "success": False,
            "error": str(e),
            "elapsed": time.time() - start_time,
            "passed": False
        }
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return {
            "query": query_and_answer[:50] + "...",
            "success": False,
            "error": str(e),
            "elapsed": time.time() - start_time,
            "passed": False
        }


def test_audio_by_id():
    """Test the audio by ID endpoint"""
    print(f"\n{'='*80}")
    print(f"Testing /audio/{{audio_id}} endpoint")
    print(f"{'='*80}")

    # First get a recommendation to get a valid audio_id
    try:
        response = requests.post(
            f"{BASE_URL}/audio/recommend",
            json={
                "query_and_answer": "禪修",
                "top_k": 1
            },
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        recommendations = result.get("recommendations", [])
        if not recommendations:
            print("⚠️  No audio to test with")
            return False

        audio_id = recommendations[0].get("audio_id")
        if not audio_id:
            print("⚠️  No audio_id found")
            return False

        print(f"Testing with audio_id: {audio_id}")

        # Now test the audio by ID endpoint
        response = requests.get(
            f"{BASE_URL}/audio/{audio_id}",
            timeout=10
        )
        response.raise_for_status()
        audio = response.json()

        print(f"✓ Found audio:")
        print(f"  Title: {audio.get('audio_title', 'N/A')}")
        print(f"  Speaker: {audio.get('speaker', 'N/A')}")
        print(f"  URL: {audio.get('audio_url', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all audio recommendation tests"""
    print(f"\n{'#'*80}")
    print(f"# AUDIO RECOMMENDATION TEST SUITE")
    print(f"# Testing {len(TEST_QUERIES)} semantic search queries")
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

    # Run recommendation tests
    results = []
    for test_case in TEST_QUERIES:
        result = test_audio_recommendation(test_case)
        results.append(result)
        time.sleep(0.5)  # Small delay between requests

    # Test audio by ID endpoint
    print(f"\n{'='*80}")
    audio_by_id_success = test_audio_by_id()

    # Summary
    print(f"\n{'#'*80}")
    print(f"# TEST SUMMARY")
    print(f"{'#'*80}")

    successful_requests = sum(1 for r in results if r.get("success"))
    passed_tests = sum(1 for r in results if r.get("passed"))
    total_time = sum(r.get("elapsed", 0) for r in results)
    avg_time = total_time / len(results) if results else 0

    # Calculate average scores for successful tests with results
    results_with_scores = [r for r in results if r.get("success") and r.get("count", 0) > 0]
    avg_similarity = sum(r.get("avg_score", 0) for r in results_with_scores) / len(results_with_scores) if results_with_scores else 0

    # Collect all unique speakers
    all_speakers = set()
    for r in results:
        if r.get("speakers"):
            all_speakers.update(r["speakers"])

    print(f"\nSuccessful requests: {successful_requests}/{len(results)}")
    print(f"Tests passed: {passed_tests}/{len(results)}")
    print(f"Total time: {total_time:.3f}s")
    print(f"Average time per query: {avg_time:.3f}s")
    print(f"Average similarity score: {avg_similarity:.4f}")
    print(f"Unique speakers found: {len(all_speakers)}")
    print(f"Audio by ID endpoint: {'✓' if audio_by_id_success else '✗'}")

    # Show failed tests
    failed = [r for r in results if not r.get("passed")]
    if failed:
        print(f"\n⚠️  Failed Tests:")
        for r in failed:
            reasons = r.get("reasons", ["Unknown error"])
            print(f"  - {r['query']}: {', '.join(reasons)}")

    if passed_tests == len(results) and audio_by_id_success:
        print(f"\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  Some tests failed or returned no results")

    # Save results to JSON
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_tests": len(results),
        "successful_requests": successful_requests,
        "passed_tests": passed_tests,
        "avg_time": avg_time,
        "avg_similarity": avg_similarity,
        "unique_speakers": len(all_speakers),
        "speakers": list(all_speakers),
        "audio_by_id_success": audio_by_id_success,
        "test_results": results
    }

    with open("audio_recommendation_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Detailed report saved to: audio_recommendation_test_report.json")


if __name__ == "__main__":
    main()
