#!/usr/bin/env python3
"""
Test script for event recommendation endpoint
Tests semantic search for Buddhist events using Qdrant vector store
"""

import requests
import json
import time
from typing import List, Dict

BASE_URL = "http://localhost:8000"

# Test queries covering different event types and topics
TEST_QUERIES = [
    {
        "query": "禪修活動",
        "description": "Meditation/Zen practice events",
        "expected_category": "禪修",
        "top_k": 3,
        "upcoming_only": False
    },
    {
        "query": "念佛共修",
        "description": "Buddhist chanting practice",
        "expected_keywords": ["念佛", "共修"],
        "top_k": 3,
        "upcoming_only": False
    },
    {
        "query": "佛學課程",
        "description": "Buddhist study courses",
        "expected_keywords": ["課程", "學習"],
        "top_k": 3,
        "upcoming_only": False
    },
    {
        "query": "法會活動",
        "description": "Dharma ceremony events",
        "expected_keywords": ["法會"],
        "top_k": 3,
        "upcoming_only": False
    },
    {
        "query": "初學者佛教活動",
        "description": "Beginner-friendly Buddhist activities",
        "expected_keywords": ["初", "入門", "基礎"],
        "top_k": 5,
        "upcoming_only": False
    },
    {
        "query": "週末禪修",
        "description": "Weekend meditation retreats",
        "expected_keywords": ["禪", "週"],
        "top_k": 3,
        "upcoming_only": True  # Only upcoming events
    }
]


def test_event_recommendation(test_case: Dict) -> Dict:
    """Test a single event recommendation query"""
    query = test_case["query"]
    description = test_case["description"]
    top_k = test_case.get("top_k", 3)
    upcoming_only = test_case.get("upcoming_only", False)

    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"Description: {description}")
    print(f"Top K: {top_k} | Upcoming Only: {upcoming_only}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/events/recommend",
            json={
                "query": query,
                "top_k": top_k,
                "min_similarity": 0.1,
                "upcoming_only": upcoming_only
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
        print(f"Events found: {count}")

        # Analyze results
        if count == 0:
            print(f"\n⚠️  No events found for query: {query}")
            return {
                "query": query,
                "success": True,
                "count": 0,
                "elapsed": elapsed,
                "passed": False,
                "reason": "No results"
            }

        # Display recommendations
        for i, event in enumerate(recommendations):
            print(f"\n--- Event {i+1} ---")
            print(f"Title: {event.get('title', 'N/A')}")
            print(f"Category: {event.get('category', 'N/A')}")
            print(f"Location: {event.get('location', 'N/A')}")
            print(f"Time Period: {event.get('time_period', 'N/A')}")
            print(f"Similarity Score: {event.get('similarity_score', 0.0):.4f}")
            print(f"Relevance: {event.get('relevance', 'N/A')}")

            # Show brief content
            content = event.get('content', '')
            if content and len(content) > 200:
                print(f"Content: {content[:200]}...")
            elif content:
                print(f"Content: {content}")

        # Validation checks
        passed = True
        reasons = []

        # Check expected category
        if "expected_category" in test_case:
            expected_cat = test_case["expected_category"]
            categories = [e.get('category', '') for e in recommendations]
            if not any(expected_cat in cat for cat in categories):
                passed = False
                reasons.append(f"Expected category '{expected_cat}' not found")

        # Check expected keywords
        if "expected_keywords" in test_case:
            expected_keywords = test_case["expected_keywords"]
            found_keywords = []

            for event in recommendations:
                event_text = f"{event.get('title', '')} {event.get('content', '')}".lower()
                for keyword in expected_keywords:
                    if keyword.lower() in event_text and keyword not in found_keywords:
                        found_keywords.append(keyword)

            print(f"\nKeyword Check:")
            print(f"  Expected: {expected_keywords}")
            print(f"  Found: {found_keywords}")

            if not found_keywords:
                passed = False
                reasons.append("No expected keywords found")

        # Check similarity scores
        avg_score = sum(e.get('similarity_score', 0) for e in recommendations) / len(recommendations)
        print(f"\nAverage Similarity Score: {avg_score:.4f}")

        if avg_score < 0.3:
            print(f"⚠️  Low average similarity score: {avg_score:.4f}")

        if passed:
            print(f"\n✅ Test PASSED")
        else:
            print(f"\n❌ Test FAILED: {', '.join(reasons)}")

        return {
            "query": query,
            "success": True,
            "count": count,
            "elapsed": elapsed,
            "avg_score": avg_score,
            "passed": passed,
            "reasons": reasons
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


def test_upcoming_events():
    """Test the upcoming events endpoint"""
    print(f"\n{'='*80}")
    print(f"Testing /events/upcoming endpoint")
    print(f"{'='*80}")

    try:
        response = requests.get(
            f"{BASE_URL}/events/upcoming",
            params={"limit": 10},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        events = result.get("events", [])
        count = result.get("count", 0)

        print(f"✓ Found {count} upcoming events")

        for i, event in enumerate(events[:3]):  # Show first 3
            print(f"\n--- Upcoming Event {i+1} ---")
            print(f"Title: {event.get('title', 'N/A')}")
            print(f"Category: {event.get('category', 'N/A')}")
            print(f"Time Period: {event.get('time_period', 'N/A')}")
            print(f"Location: {event.get('location', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all event recommendation tests"""
    print(f"\n{'#'*80}")
    print(f"# EVENT RECOMMENDATION TEST SUITE")
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
        result = test_event_recommendation(test_case)
        results.append(result)
        time.sleep(0.5)  # Small delay between requests

    # Test upcoming events endpoint
    print(f"\n{'='*80}")
    upcoming_success = test_upcoming_events()

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

    print(f"\nSuccessful requests: {successful_requests}/{len(results)}")
    print(f"Tests passed: {passed_tests}/{len(results)}")
    print(f"Total time: {total_time:.3f}s")
    print(f"Average time per query: {avg_time:.3f}s")
    print(f"Average similarity score: {avg_similarity:.4f}")
    print(f"Upcoming events endpoint: {'✓' if upcoming_success else '✗'}")

    # Show failed tests
    failed = [r for r in results if not r.get("passed")]
    if failed:
        print(f"\n⚠️  Failed Tests:")
        for r in failed:
            reasons = r.get("reasons", ["Unknown error"])
            print(f"  - {r['query']}: {', '.join(reasons)}")

    if passed_tests == len(results) and upcoming_success:
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
        "upcoming_endpoint_success": upcoming_success,
        "test_results": results
    }

    with open("event_recommendation_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Detailed report saved to: event_recommendation_test_report.json")


if __name__ == "__main__":
    main()
