#!/usr/bin/env python3
"""
Test script to verify STAPI embeddings integration
"""

import sys
from stapi_embeddings import STAPIEmbeddings

def test_stapi_embeddings():
    """Test STAPI embedding generation"""

    print("=" * 60)
    print("Testing STAPI Embeddings")
    print("=" * 60)

    # Initialize embeddings with STAPI endpoint
    embeddings = STAPIEmbeddings(
        base_url="http://ollama.changpt.org/v1",
        model="BAAI/bge-large-zh-v1.5",
        api_key="dummy_key",
        max_workers=1
    )

    # Test single query embedding
    print("\n1. Testing single query embedding...")
    test_query = "什麼是禪修？"
    print(f"   Query: {test_query}")

    try:
        query_embedding = embeddings.embed_query(test_query)
        print(f"   ✓ Success! Embedding dimension: {len(query_embedding)}")
        print(f"   First 5 values: {query_embedding[:5]}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test batch document embedding
    print("\n2. Testing batch document embedding...")
    test_docs = [
        "禪修是一種修行方法",
        "聖嚴法師教導禪法",
        "正念呼吸是禪修的基礎"
    ]
    print(f"   Documents: {len(test_docs)}")

    try:
        doc_embeddings = embeddings.embed_documents(test_docs)
        print(f"   ✓ Success! Generated {len(doc_embeddings)} embeddings")
        for i, emb in enumerate(doc_embeddings):
            print(f"   Doc {i+1}: dimension={len(emb)}, first value={emb[0]:.6f}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_stapi_embeddings()
    sys.exit(0 if success else 1)
