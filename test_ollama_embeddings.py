#!/usr/bin/env python3
"""
Isolated test for Ollama embeddings API
Host: ollama.changpt.org
Model: bge-m3
Authorization: Bearer ddm_api_key
"""

import requests
import json
import numpy as np
from typing import List, Dict, Any


class OllamaEmbeddingTest:
    def __init__(self, base_url: str, model: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def test_connection(self) -> bool:
        """Test if we can connect to the Ollama API"""
        print(f"Testing connection to {self.base_url}...")
        try:
            # Try to list models or check health
            response = requests.get(
                f"{self.base_url}/api/tags",
                headers=self.headers,
                timeout=10
            )
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return response.status_code == 200
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def generate_embedding(self, text: str) -> Dict[str, Any]:
        """Generate embedding for a single text"""
        print(f"\nGenerating embedding for: '{text[:50]}...'")
        try:
            # OpenAI-compatible embedding API endpoint (for DashScope/OpenAI)
            if "dashscope" in self.base_url or "openai" in self.base_url:
                url = f"{self.base_url}/embeddings"
                payload = {
                    "model": self.model,
                    "input": text
                }
            else:
                # Ollama format
                url = f"{self.base_url}/api/embeddings"
                payload = {
                    "model": self.model,
                    "prompt": text
                }

            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=120  # Increased timeout for qwen3-embedding
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                # Parse OpenAI-compatible format (DashScope/OpenAI)
                if "data" in result:
                    # OpenAI format: {"data": [{"embedding": [...]}]}
                    return {"embedding": result["data"][0]["embedding"]}
                # Ollama format: {"embedding": [...]}
                return result
            else:
                print(f"Error Response: {response.text}")
                return {"error": response.text}

        except Exception as e:
            print(f"Error generating embedding: {e}")
            return {"error": str(e)}

    def generate_batch_embeddings(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Generate embeddings for multiple texts"""
        print(f"\nGenerating embeddings for {len(texts)} texts...")
        results = []
        for i, text in enumerate(texts):
            print(f"Processing {i+1}/{len(texts)}: '{text[:30]}...'")
            result = self.generate_embedding(text)
            results.append(result)
        return results

    def test_embedding_dimension(self, text: str) -> int:
        """Test and return the embedding dimension"""
        result = self.generate_embedding(text)
        if "embedding" in result:
            dimension = len(result["embedding"])
            print(f"\n✓ Embedding dimension: {dimension}")
            return dimension
        else:
            print(f"\n✗ Failed to get embedding dimension")
            return 0

    def test_similarity(self, text1: str, text2: str, text3: str):
        """Test semantic similarity between texts"""
        print(f"\n=== Testing Semantic Similarity ===")
        print(f"Text 1: '{text1}'")
        print(f"Text 2 (similar): '{text2}'")
        print(f"Text 3 (different): '{text3}'")

        emb1 = self.generate_embedding(text1)
        emb2 = self.generate_embedding(text2)
        emb3 = self.generate_embedding(text3)

        if all("embedding" in e for e in [emb1, emb2, emb3]):
            vec1 = np.array(emb1["embedding"])
            vec2 = np.array(emb2["embedding"])
            vec3 = np.array(emb3["embedding"])

            # Cosine similarity
            sim_1_2 = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            sim_1_3 = np.dot(vec1, vec3) / (np.linalg.norm(vec1) * np.linalg.norm(vec3))

            print(f"\nCosine Similarity:")
            print(f"  Text1 <-> Text2 (should be high): {sim_1_2:.4f}")
            print(f"  Text1 <-> Text3 (should be low):  {sim_1_3:.4f}")

            if sim_1_2 > sim_1_3:
                print("✓ Similarity test PASSED: Similar texts have higher similarity")
            else:
                print("✗ Similarity test FAILED: Similar texts should have higher similarity")
        else:
            print("✗ Failed to generate embeddings for similarity test")


def main():
    print("=" * 60)
    print("Ollama Embeddings API Test")
    print("=" * 60)

    # Configuration - DashScope (Alibaba Cloud)
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "text-embedding-v3"  # DashScope embedding model
    API_KEY = "sk-90eac46056f04ac6ba2db2cfe72e8f74"  # From .env DASHSCOPE_API_KEY

    print(f"\nConfiguration:")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Model: {MODEL}")
    print(f"  API Key: {API_KEY}")
    print()

    # Initialize test client
    tester = OllamaEmbeddingTest(BASE_URL, MODEL, API_KEY)

    # Test 1: Connection
    print("\n" + "=" * 60)
    print("Test 1: Connection Test")
    print("=" * 60)
    connection_ok = tester.test_connection()

    if not connection_ok:
        print("\n⚠ Connection test failed. Trying embedding endpoint directly...")

    # Test 2: Single embedding
    print("\n" + "=" * 60)
    print("Test 2: Single Embedding Generation")
    print("=" * 60)
    test_text = "什麼是四聖諦？"
    result = tester.generate_embedding(test_text)

    if "embedding" in result:
        print(f"\n✓ Successfully generated embedding")
        print(f"  Embedding length: {len(result['embedding'])}")
        print(f"  First 5 values: {result['embedding'][:5]}")
    else:
        print(f"\n✗ Failed to generate embedding")
        print(f"  Error: {result.get('error', 'Unknown error')}")

    # Test 3: Embedding dimension
    print("\n" + "=" * 60)
    print("Test 3: Embedding Dimension Test")
    print("=" * 60)
    dimension = tester.test_embedding_dimension("佛教的基本教義")

    # Test 4: Batch embeddings
    print("\n" + "=" * 60)
    print("Test 4: Batch Embedding Generation")
    print("=" * 60)
    test_texts = [
        "禪修的方法",
        "念佛的意義",
        "菩薩道的實踐"
    ]
    batch_results = tester.generate_batch_embeddings(test_texts)
    successful = sum(1 for r in batch_results if "embedding" in r)
    print(f"\n✓ Successfully generated {successful}/{len(test_texts)} embeddings")

    # Test 5: Semantic similarity with REAL chunk data
    print("\n" + "=" * 60)
    print("Test 5: Semantic Similarity Test (REAL CHUNK DATA)")
    print("=" * 60)

    # Load first 3 documents from actual chunks
    import json
    with open("chunks/text_chunks.jsonl", "r", encoding="utf-8") as f:
        chunks = []
        for i, line in enumerate(f):
            if i >= 3:
                break
            chunk = json.loads(line)
            text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
            chunks.append(text)

    print(f"Using REAL documents from chunks/text_chunks.jsonl")
    print(f"Doc 1 length: {len(chunks[0])} chars")
    print(f"Doc 2 length: {len(chunks[1])} chars")
    print(f"Doc 3 length: {len(chunks[2])} chars")

    tester.test_similarity(
        chunks[0],  # First real document
        chunks[1],  # Second real document
        chunks[2]   # Third real document
    )

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Embedding Dimension: {dimension}")
    print("\n✓ All tests completed!")


if __name__ == "__main__":
    main()
