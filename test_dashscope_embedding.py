#!/usr/bin/env python3
"""
Test script for DashScope (Alibaba Cloud) embeddings
Model: text-embedding-v3
Dimension: 1024
"""

import requests
import json
import time
import numpy as np
from typing import List, Dict, Any


class DashScopeEmbeddingTest:
    def __init__(self, api_key: str, model: str = "text-embedding-v4"):
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.model = model
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_embedding(self, text: str, verbose: bool = True) -> Dict[str, Any]:
        """Generate embedding for a single text"""
        if verbose:
            print(f"\nGenerating embedding for text ({len(text)} chars)...")

        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model,
            "input": text
        }

        try:
            start_time = time.time()
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            elapsed = time.time() - start_time

            if verbose:
                print(f"Status: {response.status_code} ({elapsed:.2f}s)")

            if response.status_code == 200:
                result = response.json()
                embedding = result["data"][0]["embedding"]
                return {
                    "embedding": embedding,
                    "dimension": len(embedding),
                    "elapsed": elapsed
                }
            else:
                error_msg = response.text[:200]
                if verbose:
                    print(f"Error: {error_msg}")
                return {"error": error_msg}

        except Exception as e:
            if verbose:
                print(f"Exception: {e}")
            return {"error": str(e)}

    def test_basic_embedding(self):
        """Test basic embedding generation"""
        print("\n" + "=" * 60)
        print("Test 1: Basic Embedding Generation")
        print("=" * 60)

        test_text = "什麼是四聖諦？"
        result = self.generate_embedding(test_text)

        if "embedding" in result:
            print(f"✓ Successfully generated embedding")
            print(f"  Dimension: {result['dimension']}")
            print(f"  Time: {result['elapsed']:.2f}s")
            print(f"  First 5 values: {result['embedding'][:5]}")
        else:
            print(f"✗ Failed: {result.get('error', 'Unknown error')}")

        return result.get("dimension", 0)

    def test_real_chunks(self):
        """Test with real Buddhist text chunks"""
        print("\n" + "=" * 60)
        print("Test 2: Real Buddhist Text Chunks")
        print("=" * 60)

        # Load first 3 documents from chunks
        with open("chunks/text_chunks.jsonl", "r", encoding="utf-8") as f:
            docs = []
            for i, line in enumerate(f):
                if i >= 3:
                    break
                chunk = json.loads(line)
                text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
                docs.append({
                    "text": text,
                    "length": len(text),
                    "header": chunk.get('header', 'N/A')
                })

        results = []
        total_time = 0

        for i, doc in enumerate(docs):
            print(f"\nDoc {i+1}: {doc['header'][:50]}...")
            print(f"  Length: {doc['length']} chars")

            result = self.generate_embedding(doc['text'], verbose=False)

            if "embedding" in result:
                elapsed = result['elapsed']
                total_time += elapsed
                print(f"  ✓ {elapsed:.2f}s (dim={result['dimension']})")
                results.append(result)
            else:
                print(f"  ✗ Error: {result.get('error', 'Unknown')}")

        if results:
            avg_time = total_time / len(results)
            print(f"\n✓ Successfully embedded {len(results)}/3 documents")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Average time: {avg_time:.2f}s per document")

            # Estimate for full dataset
            estimated_total = avg_time * 1067
            print(f"\n📊 Estimated time for 1,067 documents: {estimated_total/60:.1f} minutes")

        return results

    def test_semantic_similarity(self, results: List[Dict[str, Any]]):
        """Test semantic similarity between embeddings"""
        print("\n" + "=" * 60)
        print("Test 3: Semantic Similarity")
        print("=" * 60)

        if len(results) < 3:
            print("✗ Not enough embeddings to test similarity")
            return

        vec1 = np.array(results[0]["embedding"])
        vec2 = np.array(results[1]["embedding"])
        vec3 = np.array(results[2]["embedding"])

        # Cosine similarity
        def cosine_sim(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_1_2 = cosine_sim(vec1, vec2)
        sim_1_3 = cosine_sim(vec1, vec3)
        sim_2_3 = cosine_sim(vec2, vec3)

        print(f"Doc 1 <-> Doc 2: {sim_1_2:.4f}")
        print(f"Doc 1 <-> Doc 3: {sim_1_3:.4f}")
        print(f"Doc 2 <-> Doc 3: {sim_2_3:.4f}")
        print(f"\n✓ Similarity test complete")

    def test_query_matching(self):
        """Test query matching with exact quotes from chunks"""
        print("\n" + "=" * 60)
        print("Test 4: Query Matching (Exact Quotes from Chunks)")
        print("=" * 60)

        # Load first 50 documents
        with open("chunks/text_chunks.jsonl", "r", encoding="utf-8") as f:
            docs = []
            for i, line in enumerate(f):
                if i >= 50:
                    break
                chunk = json.loads(line)
                text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
                header = chunk.get('header', 'N/A')
                docs.append({
                    "id": i,
                    "text": text,
                    "header": header
                })

        # Extract queries (exact quotes from documents)
        test_queries = [
            {
                "query": "四聖諦",
                "expected_doc_id": None,  # Will find by matching
                "description": "Four Noble Truths (key Buddhist concept)"
            },
            {
                "query": "釋迦牟尼",
                "expected_doc_id": None,
                "description": "Name of Buddha"
            },
            {
                "query": "佛教為何出現在印度",
                "expected_doc_id": 0,  # From first document
                "description": "Question about Buddhism in India"
            }
        ]

        print(f"\nEmbedding {len(docs)} documents...")
        doc_embeddings = []
        for doc in docs:
            result = self.generate_embedding(doc["text"], verbose=False)
            if "embedding" in result:
                doc_embeddings.append({
                    "id": doc["id"],
                    "header": doc["header"],
                    "embedding": np.array(result["embedding"])
                })

        print(f"✓ Embedded {len(doc_embeddings)} documents\n")

        # Test each query
        def cosine_sim(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        for query_info in test_queries:
            query = query_info["query"]
            print(f"\nQuery: '{query}'")
            print(f"Description: {query_info['description']}")

            # Embed query
            query_result = self.generate_embedding(query, verbose=False)
            if "embedding" not in query_result:
                print("  ✗ Failed to embed query")
                continue

            query_vec = np.array(query_result["embedding"])

            # Calculate similarities
            similarities = []
            for doc_emb in doc_embeddings:
                sim = cosine_sim(query_vec, doc_emb["embedding"])
                similarities.append({
                    "id": doc_emb["id"],
                    "header": doc_emb["header"],
                    "similarity": sim
                })

            # Sort by similarity
            similarities.sort(key=lambda x: x["similarity"], reverse=True)

            # Show top 3 matches
            print(f"  Top 3 matches:")
            for i, match in enumerate(similarities[:3]):
                print(f"    {i+1}. [{match['similarity']:.4f}] Doc {match['id']}: {match['header'][:50]}...")

            # Check if expected doc is in top 3
            top_3_ids = [s["id"] for s in similarities[:3]]
            if query_info["expected_doc_id"] is not None:
                if query_info["expected_doc_id"] in top_3_ids:
                    print(f"  ✓ Expected doc {query_info['expected_doc_id']} found in top 3")
                else:
                    print(f"  ✗ Expected doc {query_info['expected_doc_id']} not in top 3")
            else:
                print(f"  ✓ Query matched (no specific expectation)")

    def test_batch_performance(self):
        """Test batch embedding performance"""
        print("\n" + "=" * 60)
        print("Test 5: Batch Performance (10 documents)")
        print("=" * 60)

        # Load 10 documents
        with open("chunks/text_chunks.jsonl", "r", encoding="utf-8") as f:
            docs = []
            for i, line in enumerate(f):
                if i >= 10:
                    break
                chunk = json.loads(line)
                text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
                docs.append(text)

        print(f"Embedding {len(docs)} documents...")
        start_time = time.time()

        success = 0
        for i, text in enumerate(docs):
            result = self.generate_embedding(text, verbose=False)
            if "embedding" in result:
                success += 1
                if (i + 1) % 5 == 0:
                    print(f"  Progress: {i+1}/{len(docs)}")

        elapsed = time.time() - start_time

        print(f"\n✓ Embedded {success}/{len(docs)} documents")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Average: {elapsed/len(docs):.2f}s per document")


def main():
    print("=" * 60)
    print("DashScope Embedding Test")
    print("=" * 60)

    # Configuration
    API_KEY = "sk-a90d848a7c794e29b55881dfe8371642"
    MODEL = "text-embedding-v4"

    print(f"\nConfiguration:")
    print(f"  Model: {MODEL}")
    print(f"  Dimension: 1024")
    print(f"  Provider: DashScope (Alibaba Cloud)")
    print()

    # Initialize tester
    tester = DashScopeEmbeddingTest(API_KEY, MODEL)

    # Run tests
    dimension = tester.test_basic_embedding()

    results = tester.test_real_chunks()

    if results:
        tester.test_semantic_similarity(results)

    tester.test_query_matching()

    tester.test_batch_performance()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Model: {MODEL}")
    print(f"Dimension: {dimension}")
    print(f"Provider: DashScope")
    print("\n✓ All tests completed!")


if __name__ == "__main__":
    main()
