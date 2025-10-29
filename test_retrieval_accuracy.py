#!/usr/bin/env python3
"""
Retrieval Accuracy and Performance Test Suite
Tests the quality and speed of the RAG retrieval system
"""

import requests
import json
import time
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import statistics


@dataclass
class TestCase:
    """A single test case for retrieval testing"""
    query: str
    category: str
    expected_keywords: List[str]  # Keywords that should appear in top results
    expected_topics: List[str]  # Topics that should be found
    min_relevance_score: float = 0.5  # Minimum expected relevance score
    description: str = ""


@dataclass
class TestResult:
    """Result of a single test"""
    test_case: TestCase
    retrieval_time: float
    top_k_results: int
    found_keywords: List[str]
    found_topics: List[str]
    relevance_scores: List[float]
    passed: bool
    failure_reason: str = ""


class RetrievalTester:
    """Test suite for RAG retrieval accuracy and performance"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.test_cases = self._create_test_cases()
        self.results: List[TestResult] = []

    def _create_test_cases(self) -> List[TestCase]:
        """Create comprehensive test cases based on the Buddhist text corpus"""
        return [
            # ==== Core Buddhist Teachings ====
            TestCase(
                query="四聖諦的意義是什麼？",
                category="core_teachings",
                expected_keywords=["四聖諦", "苦", "集", "滅", "道"],
                expected_topics=["四聖諦的意義與重要性", "原始佛教與四聖諦", "八正道"],
                min_relevance_score=0.6,
                description="Test retrieval of Four Noble Truths"
            ),
            TestCase(
                query="什麼是八正道？",
                category="core_teachings",
                expected_keywords=["八正道", "正見", "正思", "正語", "正業"],
                expected_topics=["八正道", "道諦", "修行"],
                min_relevance_score=0.6,
                description="Test retrieval of Eightfold Path"
            ),
            TestCase(
                query="五蘊是什麼？",
                category="core_teachings",
                expected_keywords=["五蘊", "色", "受", "想", "行", "識"],
                expected_topics=["五蘊", "無我", "緣起"],
                min_relevance_score=0.6,
                description="Test retrieval of Five Aggregates"
            ),
            TestCase(
                query="什麼是三法印？",
                category="core_teachings",
                expected_keywords=["三法印", "無常", "無我", "涅槃"],
                expected_topics=["三法印", "佛法", "真理"],
                min_relevance_score=0.6,
                description="Test retrieval of Three Dharma Seals"
            ),

            # ==== Meditation and Practice ====
            TestCase(
                query="如何修習禪定？",
                category="practice",
                expected_keywords=["禪定", "坐禪", "修行", "調身", "調息", "調心"],
                expected_topics=["禪定", "修行方法", "坐禪"],
                min_relevance_score=0.5,
                description="Test retrieval of meditation practice"
            ),
            TestCase(
                query="念佛的方法",
                category="practice",
                expected_keywords=["念佛", "持名", "觀想", "淨土"],
                expected_topics=["念佛", "淨土法門", "修行"],
                min_relevance_score=0.5,
                description="Test retrieval of Buddhist chanting methods"
            ),
            TestCase(
                query="如何培養菩提心？",
                category="practice",
                expected_keywords=["菩提心", "慈悲", "智慧", "發心"],
                expected_topics=["菩提心", "菩薩道", "修行"],
                min_relevance_score=0.5,
                description="Test retrieval of Bodhicitta cultivation"
            ),

            # ==== Buddhist Ethics ====
            TestCase(
                query="五戒的內容",
                category="ethics",
                expected_keywords=["五戒", "不殺生", "不偷盜", "不邪淫", "不妄語", "不飲酒"],
                expected_topics=["五戒", "戒律", "在家居士"],
                min_relevance_score=0.6,
                description="Test retrieval of Five Precepts"
            ),
            TestCase(
                query="什麼是六度？",
                category="ethics",
                expected_keywords=["六度", "布施", "持戒", "忍辱", "精進", "禪定", "智慧"],
                expected_topics=["六度", "菩薩道", "波羅蜜"],
                min_relevance_score=0.6,
                description="Test retrieval of Six Perfections"
            ),

            # ==== Buddhist Cosmology ====
            TestCase(
                query="什麼是因果？",
                category="cosmology",
                expected_keywords=["因果", "業", "輪迴", "報應"],
                expected_topics=["因果", "業力", "三世因果"],
                min_relevance_score=0.5,
                description="Test retrieval of karma and causation"
            ),
            TestCase(
                query="佛教對生死的看法",
                category="cosmology",
                expected_keywords=["生死", "輪迴", "解脫", "涅槃"],
                expected_topics=["生死", "輪迴", "解脫道"],
                min_relevance_score=0.5,
                description="Test retrieval of life and death views"
            ),

            # ==== Pure Land Buddhism ====
            TestCase(
                query="極樂世界在哪裡？",
                category="pure_land",
                expected_keywords=["極樂世界", "淨土", "阿彌陀佛", "西方"],
                expected_topics=["極樂世界", "淨土", "往生"],
                min_relevance_score=0.5,
                description="Test retrieval of Pure Land"
            ),
            TestCase(
                query="如何往生淨土？",
                category="pure_land",
                expected_keywords=["往生", "念佛", "信願行", "淨土"],
                expected_topics=["往生", "淨土法門", "念佛"],
                min_relevance_score=0.5,
                description="Test retrieval of rebirth in Pure Land"
            ),

            # ==== Buddhist Figures ====
            TestCase(
                query="觀世音菩薩的功德",
                category="figures",
                expected_keywords=["觀世音", "觀音", "菩薩", "慈悲", "救苦"],
                expected_topics=["觀世音菩薩", "菩薩", "慈悲"],
                min_relevance_score=0.5,
                description="Test retrieval of Avalokitesvara"
            ),
            TestCase(
                query="釋迦牟尼佛的生平",
                category="figures",
                expected_keywords=["釋迦牟尼", "佛陀", "悉達多", "成道", "涅槃"],
                expected_topics=["佛陀", "釋迦牟尼", "生平"],
                min_relevance_score=0.5,
                description="Test retrieval of Buddha's biography"
            ),

            # ==== Monastery Life ====
            TestCase(
                query="出家的意義",
                category="monastic",
                expected_keywords=["出家", "僧侶", "修行", "解脫"],
                expected_topics=["出家", "僧團", "修行"],
                min_relevance_score=0.5,
                description="Test retrieval of monastic ordination"
            ),

            # ==== Daily Life Application ====
            TestCase(
                query="學佛對日常生活的影響",
                category="daily_life",
                expected_keywords=["學佛", "日常", "生活", "修行", "實踐"],
                expected_topics=["學佛", "日常生活", "實踐"],
                min_relevance_score=0.4,
                description="Test retrieval of Buddhism in daily life"
            ),
            TestCase(
                query="如何面對煩惱？",
                category="daily_life",
                expected_keywords=["煩惱", "修行", "智慧", "對治"],
                expected_topics=["煩惱", "修行", "智慧"],
                min_relevance_score=0.4,
                description="Test retrieval of dealing with afflictions"
            ),

            # ==== Buddhist Philosophy ====
            TestCase(
                query="什麼是空？",
                category="philosophy",
                expected_keywords=["空", "緣起", "性空", "般若"],
                expected_topics=["空", "般若", "中觀"],
                min_relevance_score=0.5,
                description="Test retrieval of Emptiness"
            ),
            TestCase(
                query="佛教的無我觀",
                category="philosophy",
                expected_keywords=["無我", "我", "五蘊", "解脫"],
                expected_topics=["無我", "佛教", "哲理"],
                min_relevance_score=0.5,
                description="Test retrieval of Non-self doctrine"
            ),

            # ==== Challenging/Ambiguous Queries ====
            TestCase(
                query="如何開悟？",
                category="advanced",
                expected_keywords=["開悟", "悟", "證悟", "智慧", "修行"],
                expected_topics=["開悟", "證悟", "修行"],
                min_relevance_score=0.4,
                description="Test retrieval of enlightenment (challenging)"
            ),
            TestCase(
                query="佛教與科學的關係",
                category="advanced",
                expected_keywords=["佛教", "科學", "佛法"],
                expected_topics=["佛法", "科學"],
                min_relevance_score=0.3,
                description="Test retrieval of Buddhism and science (challenging)"
            ),
        ]

    def run_retrieval_test(self, test_case: TestCase, top_k: int = 5) -> TestResult:
        """Run a single retrieval test"""
        print(f"\n{'='*60}")
        print(f"Test: {test_case.description}")
        print(f"Query: '{test_case.query}'")
        print(f"Category: {test_case.category}")
        print(f"{'='*60}")

        # Measure retrieval time
        start_time = time.time()

        try:
            response = requests.post(
                f"{self.base_url}/retrieve",
                json={"query": test_case.query, "top_k": top_k},
                timeout=30
            )
            response.raise_for_status()

            retrieval_time = time.time() - start_time
            result_data = response.json()

        except Exception as e:
            print(f"❌ Request failed: {e}")
            return TestResult(
                test_case=test_case,
                retrieval_time=0,
                top_k_results=0,
                found_keywords=[],
                found_topics=[],
                relevance_scores=[],
                passed=False,
                failure_reason=f"Request failed: {str(e)}"
            )

        # Extract results
        contexts = result_data.get("documents", [])

        if not contexts:
            print(f"❌ No results found")
            return TestResult(
                test_case=test_case,
                retrieval_time=retrieval_time,
                top_k_results=0,
                found_keywords=[],
                found_topics=[],
                relevance_scores=[],
                passed=False,
                failure_reason="No results returned"
            )

        # Analyze results
        found_keywords = []
        found_topics = []
        relevance_scores = []

        for i, ctx in enumerate(contexts):
            content = ctx.get("text", "")
            metadata = ctx.get("metadata", {})
            title = metadata.get("title", "")
            score = ctx.get("score", 0.0)

            relevance_scores.append(score)

            print(f"\n--- Result {i+1} (Score: {score:.4f}) ---")
            print(f"Title: {title}")
            print(f"Content preview: {content[:150]}...")

            # Check for expected keywords
            combined_text = (title + " " + content).lower()
            for keyword in test_case.expected_keywords:
                if keyword.lower() in combined_text and keyword not in found_keywords:
                    found_keywords.append(keyword)
                    print(f"  ✓ Found keyword: {keyword}")

            # Check for expected topics (from title)
            for topic in test_case.expected_topics:
                if topic in title and topic not in found_topics:
                    found_topics.append(topic)
                    print(f"  ✓ Found topic: {topic}")

        # Determine if test passed
        keyword_coverage = len(found_keywords) / len(test_case.expected_keywords) if test_case.expected_keywords else 0
        topic_coverage = len(found_topics) / len(test_case.expected_topics) if test_case.expected_topics else 0
        avg_score = statistics.mean(relevance_scores) if relevance_scores else 0

        # Pass criteria: at least 50% keyword coverage OR 33% topic coverage AND avg score > min threshold
        passed = (
            (keyword_coverage >= 0.5 or topic_coverage >= 0.33) and
            avg_score >= test_case.min_relevance_score
        )

        failure_reason = ""
        if not passed:
            if keyword_coverage < 0.5 and topic_coverage < 0.33:
                failure_reason = f"Low coverage: keywords {keyword_coverage:.1%}, topics {topic_coverage:.1%}"
            elif avg_score < test_case.min_relevance_score:
                failure_reason = f"Low relevance score: {avg_score:.3f} < {test_case.min_relevance_score}"

        print(f"\n{'='*60}")
        print(f"Retrieval time: {retrieval_time:.3f}s")
        print(f"Keywords found: {len(found_keywords)}/{len(test_case.expected_keywords)} ({keyword_coverage:.1%})")
        print(f"Topics found: {len(found_topics)}/{len(test_case.expected_topics)} ({topic_coverage:.1%})")
        print(f"Avg relevance score: {avg_score:.3f} (min: {test_case.min_relevance_score})")
        print(f"Result: {'✅ PASSED' if passed else '❌ FAILED'}")
        if failure_reason:
            print(f"Reason: {failure_reason}")

        return TestResult(
            test_case=test_case,
            retrieval_time=retrieval_time,
            top_k_results=len(contexts),
            found_keywords=found_keywords,
            found_topics=found_topics,
            relevance_scores=relevance_scores,
            passed=passed,
            failure_reason=failure_reason
        )

    def run_all_tests(self, top_k: int = 5) -> Dict[str, Any]:
        """Run all test cases and generate report"""
        print(f"\n{'#'*60}")
        print(f"# RAG Retrieval Accuracy & Performance Test Suite")
        print(f"# Total test cases: {len(self.test_cases)}")
        print(f"# Top K: {top_k}")
        print(f"# Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}\n")

        self.results = []

        for test_case in self.test_cases:
            result = self.run_retrieval_test(test_case, top_k)
            self.results.append(result)
            time.sleep(0.5)  # Brief pause between tests

        # Generate summary report
        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        if not self.results:
            return {"error": "No test results available"}

        passed_tests = [r for r in self.results if r.passed]
        failed_tests = [r for r in self.results if not r.passed]

        # Category breakdown
        category_stats = {}
        for result in self.results:
            cat = result.test_case.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0, "failed": 0}
            category_stats[cat]["total"] += 1
            if result.passed:
                category_stats[cat]["passed"] += 1
            else:
                category_stats[cat]["failed"] += 1

        # Performance stats
        retrieval_times = [r.retrieval_time for r in self.results]
        relevance_scores = []
        for r in self.results:
            relevance_scores.extend(r.relevance_scores)

        report = {
            "summary": {
                "total_tests": len(self.results),
                "passed": len(passed_tests),
                "failed": len(failed_tests),
                "pass_rate": len(passed_tests) / len(self.results) * 100,
            },
            "performance": {
                "avg_retrieval_time": statistics.mean(retrieval_times),
                "min_retrieval_time": min(retrieval_times),
                "max_retrieval_time": max(retrieval_times),
                "median_retrieval_time": statistics.median(retrieval_times),
            },
            "relevance": {
                "avg_score": statistics.mean(relevance_scores) if relevance_scores else 0,
                "min_score": min(relevance_scores) if relevance_scores else 0,
                "max_score": max(relevance_scores) if relevance_scores else 0,
                "median_score": statistics.median(relevance_scores) if relevance_scores else 0,
            },
            "by_category": category_stats,
            "failed_tests": [
                {
                    "query": r.test_case.query,
                    "category": r.test_case.category,
                    "reason": r.failure_reason,
                    "description": r.test_case.description
                }
                for r in failed_tests
            ]
        }

        # Print report
        print(f"\n{'#'*60}")
        print(f"# TEST REPORT")
        print(f"{'#'*60}\n")

        print(f"Overall Results:")
        print(f"  Total tests: {report['summary']['total_tests']}")
        print(f"  Passed: {report['summary']['passed']} ({report['summary']['pass_rate']:.1f}%)")
        print(f"  Failed: {report['summary']['failed']}")

        print(f"\nPerformance:")
        print(f"  Avg retrieval time: {report['performance']['avg_retrieval_time']:.3f}s")
        print(f"  Min retrieval time: {report['performance']['min_retrieval_time']:.3f}s")
        print(f"  Max retrieval time: {report['performance']['max_retrieval_time']:.3f}s")
        print(f"  Median retrieval time: {report['performance']['median_retrieval_time']:.3f}s")

        print(f"\nRelevance Scores:")
        print(f"  Avg score: {report['relevance']['avg_score']:.3f}")
        print(f"  Min score: {report['relevance']['min_score']:.3f}")
        print(f"  Max score: {report['relevance']['max_score']:.3f}")
        print(f"  Median score: {report['relevance']['median_score']:.3f}")

        print(f"\nBy Category:")
        for cat, stats in category_stats.items():
            pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"  {cat}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")

        if failed_tests:
            print(f"\nFailed Tests ({len(failed_tests)}):")
            for fail in report['failed_tests']:
                print(f"  - {fail['query']} ({fail['category']})")
                print(f"    Reason: {fail['reason']}")

        print(f"\n{'#'*60}\n")

        return report

    def save_report(self, filename: str = "retrieval_test_report.json"):
        """Save detailed report to JSON file"""
        if not self.results:
            print("No results to save")
            return

        detailed_results = []
        for result in self.results:
            detailed_results.append({
                "test_case": {
                    "query": result.test_case.query,
                    "category": result.test_case.category,
                    "description": result.test_case.description,
                    "expected_keywords": result.test_case.expected_keywords,
                    "expected_topics": result.test_case.expected_topics,
                    "min_relevance_score": result.test_case.min_relevance_score,
                },
                "result": {
                    "passed": result.passed,
                    "retrieval_time": result.retrieval_time,
                    "top_k_results": result.top_k_results,
                    "found_keywords": result.found_keywords,
                    "found_topics": result.found_topics,
                    "relevance_scores": result.relevance_scores,
                    "failure_reason": result.failure_reason,
                }
            })

        report = self.generate_report()
        report["detailed_results"] = detailed_results
        report["timestamp"] = datetime.now().isoformat()

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"Detailed report saved to: {filename}")


def main():
    """Run the test suite"""
    tester = RetrievalTester(base_url="http://localhost:8000")

    # Check if system is ready
    try:
        health = requests.get(f"{tester.base_url}/health", timeout=5).json()
        if not health.get("initialized"):
            print("❌ System not initialized. Please run /initialize first.")
            return
        print(f"✓ System is ready: {health}")
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return

    # Run all tests
    report = tester.run_all_tests(top_k=5)

    # Save detailed report
    tester.save_report("retrieval_test_report.json")

    print(f"\nTest suite completed!")
    print(f"Pass rate: {report['summary']['pass_rate']:.1f}%")


if __name__ == "__main__":
    main()
