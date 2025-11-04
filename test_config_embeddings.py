#!/usr/bin/env python3
"""
Test that the config loads STAPI embeddings correctly
"""

from config import settings
from llm_factory import LLMFactory

def test_config():
    print("=" * 60)
    print("Testing Configuration")
    print("=" * 60)

    print(f"\nEmbedding Provider: {settings.embedding_provider}")
    print(f"Embedding Model: {settings.embedding_model}")
    print(f"Embedding Dimension: {settings.embedding_dimension}")
    print(f"Ollama Base URL: {settings.ollama_base_url}")

    print("\n" + "=" * 60)
    print("Creating embeddings from factory...")
    print("=" * 60)

    embeddings = LLMFactory.create_embeddings()

    print(f"\n✓ Embeddings created successfully!")
    print(f"Type: {type(embeddings).__name__}")

    # Test a quick embedding
    print("\nTesting embedding generation...")
    test_text = "測試文本"
    embedding = embeddings.embed_query(test_text)
    print(f"✓ Generated embedding with dimension: {len(embedding)}")

    print("\n" + "=" * 60)
    print("✓ Configuration test passed!")
    print("=" * 60)

if __name__ == "__main__":
    test_config()
