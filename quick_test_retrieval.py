#!/usr/bin/env python3
"""
Quick retrieval test - Tests a few key queries to verify system is working
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

# Quick test queries
TEST_QUERIES = [
    ("四聖諦的意義是什麼？", "Four Noble Truths"),
    ("如何修習禪定？", "Meditation practice"),
    ("什麼是五戒？", "Five Precepts"),
    ("念佛的方法", "Buddhist chanting"),
    ("什麼是空？", "Emptiness"),
]


def test_query(query: str, description: str, top_k: int = 3):
    """Test a single query"""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"Description: {description}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/retrieve",
            json={"question": query, "top_k": top_k},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        elapsed = time.time() - start_time

        contexts = result.get("contexts", [])

        print(f"Retrieval time: {elapsed:.3f}s")
        print(f"Results found: {len(contexts)}")

        for i, ctx in enumerate(contexts[:top_k]):
            content = ctx.get("content", "")
            metadata = ctx.get("metadata", {})
            header = metadata.get("header", "Unknown")
            score = ctx.get("score", 0.0)

            print(f"\n--- Result {i+1} (Score: {score:.4f}) ---")
            print(f"Title: {header}")
            print(f"Preview: {content[:200]}...")

        return True, elapsed, len(contexts)

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, 0, 0


def main():
    """Run quick tests"""
    print(f"\n{'#'*60}")
    print(f"# Quick Retrieval Test")
    print(f"# Testing {len(TEST_QUERIES)} queries")
    print(f"{'#'*60}")

    # Check system health
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5).json()
        print(f"\nSystem status:")
        print(f"  Initialized: {health.get('initialized')}")
        print(f"  Vector store connected: {health.get('vector_store_connected')}")
        print(f"  Pipeline ready: {health.get('pipeline_ready')}")

        if not health.get("initialized"):
            print("\n❌ System not initialized. Please wait for initialization to complete.")
            return
    except Exception as e:
        print(f"\n❌ Cannot connect to server: {e}")
        return

    # Run tests
    results = []
    for query, description in TEST_QUERIES:
        success, elapsed, count = test_query(query, description)
        results.append((query, success, elapsed, count))
        time.sleep(0.5)

    # Summary
    print(f"\n{'#'*60}")
    print(f"# SUMMARY")
    print(f"{'#'*60}")

    successful = sum(1 for _, s, _, _ in results if s)
    total_time = sum(e for _, _, e, _ in results)
    avg_time = total_time / len(results) if results else 0

    print(f"\nTests passed: {successful}/{len(results)}")
    print(f"Total time: {total_time:.3f}s")
    print(f"Average time per query: {avg_time:.3f}s")

    if successful == len(results):
        print(f"\n✅ All tests passed!")
    else:
        print(f"\n⚠️  Some tests failed")


if __name__ == "__main__":
    main()
