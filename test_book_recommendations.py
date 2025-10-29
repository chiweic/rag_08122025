#!/usr/bin/env python3
"""
Test script for book recommendation endpoint
Tests semantic search for Buddhist books from DDM (法鼓文化) catalog
"""

import requests
import json
import time
from typing import List, Dict

BASE_URL = "http://localhost:8000"

# Test queries covering different Buddhist topics
TEST_QUERIES = [
    {
        "query": "禪修入門",
        "description": "Beginner meditation books",
        "expected_keywords": ["禪", "修"],
        "top_k": 5
    },
    {
        "query": "聖嚴法師",
        "description": "Books by Master Sheng Yen",
        "expected_keywords": ["聖嚴"],
        "top_k": 5
    },
    {
        "query": "佛教基本教義",
        "description": "Basic Buddhist teachings",
        "expected_keywords": ["佛", "教"],
        "top_k": 5
    },
    {
        "query": "心靈成長",
        "description": "Spiritual growth and development",
        "expected_keywords": ["心", "成長"],
        "top_k": 5
    },
    {
        "query": "生活中的佛法",
        "description": "Buddhism in daily life",
        "expected_keywords": ["生活", "佛法"],
        "top_k": 5
    },
    {
        "query": "念佛法門",
        "description": "Pure Land practice",
        "expected_keywords": ["念佛"],
        "top_k": 3
    },
    {
        "query": "禪宗典籍",
        "description": "Zen Buddhist texts",
        "expected_keywords": ["禪"],
        "top_k": 3
    }
]


def test_book_recommendation(test_case: Dict) -> Dict:
    """Test a single book recommendation query"""
    query = test_case["query"]
    description = test_case["description"]
    top_k = test_case.get("top_k", 5)

    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"Description: {description}")
    print(f"Top K: {top_k}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/books/recommend",
            json={
                "query": query,
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
        print(f"Books found: {count}")

        # Analyze results
        if count == 0:
            print(f"\n⚠️  No books found for query: {query}")
            return {
                "query": query,
                "success": True,
                "count": 0,
                "elapsed": elapsed,
                "passed": False,
                "reason": "No results"
            }

        # Display recommendations
        for i, book in enumerate(recommendations):
            print(f"\n--- Book {i+1} ---")
            print(f"Title: {book.get('title', 'N/A')}")
            print(f"Author: {book.get('author', 'N/A')}")
            print(f"ISBN: {book.get('isbn', 'N/A')}")
            print(f"Price: {book.get('price', 'N/A')}")
            print(f"Similarity Score: {book.get('similarity_score', 0.0):.4f}")

            # Show recommendation reason if available
            reason = book.get('recommendation_reason', '')
            if reason:
                print(f"Recommendation: {reason}")

            # Show brief content introduction
            content_intro = book.get('content_introduction', '')
            if content_intro and len(content_intro) > 150:
                print(f"Introduction: {content_intro[:150]}...")
            elif content_intro:
                print(f"Introduction: {content_intro}")

            # Show URL if available
            url = book.get('url', '')
            if url:
                print(f"URL: {url}")

        # Validation checks
        passed = True
        reasons = []

        # Check expected keywords
        if "expected_keywords" in test_case:
            expected_keywords = test_case["expected_keywords"]
            found_keywords = []

            for book in recommendations:
                book_text = (
                    f"{book.get('title', '')} "
                    f"{book.get('author', '')} "
                    f"{book.get('content_introduction', '')} "
                    f"{book.get('table_of_contents', '')}"
                ).lower()

                for keyword in expected_keywords:
                    if keyword.lower() in book_text and keyword not in found_keywords:
                        found_keywords.append(keyword)

            print(f"\nKeyword Check:")
            print(f"  Expected: {expected_keywords}")
            print(f"  Found: {found_keywords}")

            if not found_keywords:
                passed = False
                reasons.append("No expected keywords found")

        # Check similarity scores
        scores = [b.get('similarity_score', 0) for b in recommendations]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        print(f"\nSimilarity Scores:")
        print(f"  Average: {avg_score:.4f}")
        print(f"  Min: {min_score:.4f}")
        print(f"  Max: {max_score:.4f}")

        if avg_score < 0.1:
            print(f"⚠️  Low average similarity score: {avg_score:.4f}")

        # Check author diversity
        authors = set(b.get('author', 'Unknown') for b in recommendations)
        print(f"\nAuthors: {', '.join(list(authors)[:5])}")
        if len(authors) > 5:
            print(f"  ... and {len(authors) - 5} more")

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
            "min_score": min_score,
            "max_score": max_score,
            "authors": list(authors),
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


def test_book_by_isbn():
    """Test the book by ISBN endpoint"""
    print(f"\n{'='*80}")
    print(f"Testing /books/{{isbn}} endpoint")
    print(f"{'='*80}")

    # First get a recommendation to get a valid ISBN
    try:
        response = requests.post(
            f"{BASE_URL}/books/recommend",
            json={
                "query": "聖嚴法師",
                "top_k": 1
            },
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        recommendations = result.get("recommendations", [])
        if not recommendations:
            print("⚠️  No books to test with")
            return False

        isbn = recommendations[0].get("isbn")
        if not isbn:
            print("⚠️  No ISBN found")
            return False

        print(f"Testing with ISBN: {isbn}")

        # Now test the book by ISBN endpoint
        response = requests.get(
            f"{BASE_URL}/books/{isbn}",
            timeout=10
        )
        response.raise_for_status()
        book = response.json()

        print(f"✓ Found book:")
        print(f"  Title: {book.get('title', 'N/A')}")
        print(f"  Author: {book.get('author', 'N/A')}")
        print(f"  ISBN: {book.get('isbn', 'N/A')}")
        print(f"  Price: {book.get('price', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_random_books():
    """Test the random books endpoint"""
    print(f"\n{'='*80}")
    print(f"Testing /books/random/{{count}} endpoint")
    print(f"{'='*80}")

    try:
        count = 5
        response = requests.get(
            f"{BASE_URL}/books/random/{count}",
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        books = result.get("books", [])
        returned_count = result.get("count", 0)

        print(f"✓ Requested {count} books, got {returned_count}")

        for i, book in enumerate(books[:3]):  # Show first 3
            print(f"\n--- Random Book {i+1} ---")
            print(f"Title: {book.get('title', 'N/A')}")
            print(f"Author: {book.get('author', 'N/A')}")
            print(f"Price: {book.get('price', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all book recommendation tests"""
    print(f"\n{'#'*80}")
    print(f"# BOOK RECOMMENDATION TEST SUITE")
    print(f"# Testing {len(TEST_QUERIES)} semantic search queries")
    print(f"{'#'*80}")

    # Check system health
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5).json()
        print(f"\nSystem Status:")
        print(f"  Initialized: {health.get('initialized')}")
        print(f"  Vector store connected: {health.get('vector_store_connected')}")
        print(f"  Pipeline ready: {health.get('pipeline_ready')}")

        if not health.get("initialized"):
            print("\n❌ System not initialized. Please run initialization first.")
            return

    except Exception as e:
        print(f"\n❌ Cannot connect to server: {e}")
        return

    # Run recommendation tests
    results = []
    for test_case in TEST_QUERIES:
        result = test_book_recommendation(test_case)
        results.append(result)
        time.sleep(0.5)  # Small delay between requests

    # Test book by ISBN endpoint
    print(f"\n{'='*80}")
    book_by_isbn_success = test_book_by_isbn()

    # Test random books endpoint
    print(f"\n{'='*80}")
    random_books_success = test_random_books()

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

    # Collect all unique authors
    all_authors = set()
    for r in results:
        if r.get("authors"):
            all_authors.update(r["authors"])

    print(f"\nSuccessful requests: {successful_requests}/{len(results)}")
    print(f"Tests passed: {passed_tests}/{len(results)}")
    print(f"Total time: {total_time:.3f}s")
    print(f"Average time per query: {avg_time:.3f}s")
    print(f"Average similarity score: {avg_similarity:.4f}")
    print(f"Unique authors found: {len(all_authors)}")
    print(f"Book by ISBN endpoint: {'✓' if book_by_isbn_success else '✗'}")
    print(f"Random books endpoint: {'✓' if random_books_success else '✗'}")

    # Show top authors
    if all_authors:
        print(f"\nAuthors found: {', '.join(list(all_authors)[:10])}")
        if len(all_authors) > 10:
            print(f"  ... and {len(all_authors) - 10} more")

    # Show failed tests
    failed = [r for r in results if not r.get("passed")]
    if failed:
        print(f"\n⚠️  Failed Tests:")
        for r in failed:
            reasons = r.get("reasons", ["Unknown error"])
            print(f"  - {r['query']}: {', '.join(reasons)}")

    if passed_tests == len(results) and book_by_isbn_success and random_books_success:
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
        "unique_authors": len(all_authors),
        "authors": list(all_authors),
        "book_by_isbn_success": book_by_isbn_success,
        "random_books_success": random_books_success,
        "test_results": results
    }

    with open("book_recommendation_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Detailed report saved to: book_recommendation_test_report.json")


if __name__ == "__main__":
    main()
