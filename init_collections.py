#!/usr/bin/env python3
"""
Unified Collection Initialization Script

Initializes Qdrant collections with embeddings from various data sources.
Uses EmbeddingFactory to support any embedding provider configured in .env

Supported collections:
- main: Main document chunks (text, audio, events)
- faq: FAQ questions for query recommendations

Usage:
  python init_collections.py main          # Initialize main collection
  python init_collections.py faq           # Initialize FAQ collection
  python init_collections.py faq --limit 100  # Test with 100 FAQs
  python init_collections.py all           # Initialize all collections
"""

import time
import json
import sys
import glob
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

from config import settings
from llm_factory import EmbeddingFactory

# Configuration
BATCH_SIZE = 50  # Generate embeddings in batches
UPLOAD_BATCH_SIZE = 100  # Upload to Qdrant in batches


def log(msg):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def load_main_documents():
    """Load documents from chunk files (text, audio, event)."""
    documents = []
    chunk_files = glob.glob("chunks/*.jsonl")

    log("Loading main documents from chunks/*.jsonl...")

    for chunk_file in chunk_files:
        log(f"  Reading {chunk_file}...")
        count = 0
        with open(chunk_file, "r", encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                doc_id = chunk.get("id", "")
                if not doc_id:
                    log(f"    ⚠️  Skipping chunk without id")
                    continue

                text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
                if not text:
                    log(f"    ⚠️  Skipping chunk {doc_id} without text")
                    continue

                metadata = chunk.get("metadata", {})
                if not isinstance(metadata, dict):
                    metadata = {}

                documents.append({
                    "id": doc_id,
                    "text": text,
                    "metadata": metadata
                })
                count += 1

        log(f"  ✓ Loaded {count} documents from {chunk_file}")

    log(f"✅ Loaded {len(documents)} total documents")
    return documents


def load_faq_documents(faq_path: str = "faq.json", limit: int = None):
    """Load FAQ questions from JSON file."""
    faq_file = Path(faq_path)
    if not faq_file.exists():
        log(f"❌ FAQ file not found: {faq_path}")
        return []

    log(f"Loading FAQ questions from {faq_path}...")
    with open(faq_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        questions = data.get('questions', [])

    if limit:
        questions = questions[:limit]
        log(f"  Limited to first {limit} questions for testing")

    # Convert to document format
    documents = []
    for i, question in enumerate(questions):
        documents.append({
            "id": i,
            "text": question,
            "metadata": {
                "question": question,
                "source": "faq",
                "faq_id": i
            }
        })

    log(f"✅ Loaded {len(documents)} FAQ questions")
    return documents


def init_qdrant(collection_name: str, embedding_dim: int, recreate: bool = False):
    """Initialize or verify Qdrant collection."""
    log(f"Connecting to Qdrant at {settings.qdrant_url}...")
    client = QdrantClient(url=settings.qdrant_url)

    # Check if collection exists
    try:
        info = client.get_collection(collection_name)
        log(f"⚠️  Collection '{collection_name}' already exists with {info.points_count} points")

        if not recreate:
            response = input(f"Recreate collection '{collection_name}'? (yes/no): ")
            recreate = response.lower() == 'yes'

        if recreate:
            client.delete_collection(collection_name)
            log(f"🗑️  Deleted existing collection: {collection_name}")
        else:
            log("❌ Exiting without changes")
            return None
    except Exception:
        log(f"Collection '{collection_name}' does not exist, will create new one")

    # Create collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
    )
    log(f"✅ Created collection: {collection_name} (dim={embedding_dim})")

    return client


def generate_embeddings_batch(embeddings, documents, batch_size=BATCH_SIZE):
    """Generate embeddings for documents in batches with progress tracking."""
    all_embeddings = []
    total_batches = (len(documents) + batch_size - 1) // batch_size

    log(f"Generating embeddings in {total_batches} batches of {batch_size}...")

    for i in tqdm(range(0, len(documents), batch_size), desc="Embedding batches"):
        batch = documents[i:i + batch_size]
        batch_texts = [doc["text"] for doc in batch]

        try:
            batch_embeddings = embeddings.embed_documents(batch_texts)
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            log(f"  ⚠️  Batch embedding failed, falling back to individual: {e}")
            # Fallback to individual embeddings
            for text in batch_texts:
                try:
                    emb = embeddings.embed_query(text)
                    all_embeddings.append(emb)
                except Exception as e2:
                    log(f"  ❌ Failed to embed document: {e2}")
                    raise

    log(f"✅ Generated {len(all_embeddings)} embeddings")
    return all_embeddings


def upload_to_qdrant(client, collection_name, documents, embeddings, upload_batch_size=UPLOAD_BATCH_SIZE):
    """Upload documents and embeddings to Qdrant in batches."""
    total_batches = (len(documents) + upload_batch_size - 1) // upload_batch_size
    log(f"Uploading {len(documents)} points in {total_batches} batches...")

    for i in tqdm(range(0, len(documents), upload_batch_size), desc="Upload batches"):
        batch_docs = documents[i:i + upload_batch_size]
        batch_embs = embeddings[i:i + upload_batch_size]

        # Create points
        points = []
        for doc, emb in zip(batch_docs, batch_embs):
            # Use deterministic hash for string IDs (MD5 to avoid session-dependent hash())
            if isinstance(doc["id"], int):
                point_id = doc["id"]
            else:
                # MD5 hash is deterministic across sessions
                hash_digest = hashlib.md5(str(doc["id"]).encode('utf-8')).hexdigest()
                # Convert first 8 hex chars to int (32-bit positive integer)
                point_id = int(hash_digest[:8], 16)

            point = PointStruct(
                id=point_id,
                vector=emb,
                payload={
                    "text": doc["text"],
                    "chunk_id": str(doc["id"]),
                    **doc["metadata"]
                }
            )
            points.append(point)

        # Upload batch
        try:
            client.upsert(collection_name=collection_name, points=points)
        except Exception as e:
            log(f"❌ Failed to upload batch: {e}")
            raise

    log(f"✅ Uploaded {len(documents)} points to Qdrant")


def init_collection(collection_type: str, limit: int = None, recreate: bool = False):
    """Initialize a specific collection."""
    start_time = time.time()

    log("=" * 60)
    log(f"Initializing Collection: {collection_type.upper()}")
    log("=" * 60)
    log(f"Embedding Provider: {settings.embedding_provider}")
    log(f"Embedding Model: {settings.embedding_model}")
    log(f"Qdrant URL: {settings.qdrant_url}")
    log("")

    # Initialize embeddings
    log("Initializing embedding model...")
    embeddings = EmbeddingFactory.create_embeddings()

    # Get embedding dimension
    test_embedding = embeddings.embed_query("test")
    embedding_dim = len(test_embedding)
    log(f"✅ Embedding dimension: {embedding_dim}")
    log("")

    # Load documents based on collection type
    if collection_type == "main":
        collection_name = settings.qdrant_collection  # Default: ddm_rag
        documents = load_main_documents()
    elif collection_type == "faq":
        collection_name = "ddm_faq"
        documents = load_faq_documents(limit=limit)
    else:
        log(f"❌ Unknown collection type: {collection_type}")
        return False

    if not documents:
        log("❌ No documents loaded, exiting")
        return False

    log(f"Collection: {collection_name}")
    log(f"Documents: {len(documents)}")
    log("")

    # Initialize Qdrant
    client = init_qdrant(collection_name, embedding_dim, recreate=recreate)
    if not client:
        return False
    log("")

    # Generate embeddings
    all_embeddings = generate_embeddings_batch(embeddings, documents)
    log("")

    # Upload to Qdrant
    upload_to_qdrant(client, collection_name, documents, all_embeddings)
    log("")

    # Verify
    info = client.get_collection(collection_name)
    elapsed = time.time() - start_time

    log("=" * 60)
    log("✅ Collection Initialized Successfully!")
    log("=" * 60)
    log(f"Collection: {collection_name}")
    log(f"Documents: {len(documents)}")
    log(f"Points in Qdrant: {info.points_count}")
    log(f"Vector dimension: {info.config.params.vectors.size}")
    log(f"Time elapsed: {elapsed/60:.1f} minutes ({elapsed:.1f} seconds)")
    if len(documents) > 0:
        log(f"Average time per document: {elapsed/len(documents):.2f}s")
    log("")

    return True


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Initialize Qdrant collections with embeddings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python init_collections.py main              # Initialize main collection
  python init_collections.py faq               # Initialize FAQ collection
  python init_collections.py faq --limit 100   # Test with 100 FAQs
  python init_collections.py all               # Initialize all collections
  python init_collections.py all --recreate    # Recreate all without prompts
        """
    )

    parser.add_argument(
        'collection',
        choices=['main', 'faq', 'all'],
        help='Collection to initialize (main, faq, or all)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of FAQ questions (for testing)'
    )
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Recreate collections without prompting'
    )

    args = parser.parse_args()

    try:
        if args.collection == 'all':
            # Initialize all collections
            success_main = init_collection('main', recreate=args.recreate)
            log("")
            success_faq = init_collection('faq', limit=args.limit, recreate=args.recreate)

            if success_main and success_faq:
                log("=" * 60)
                log("✅ All collections initialized successfully!")
                log("=" * 60)
            else:
                log("⚠️  Some collections failed to initialize")
                sys.exit(1)
        else:
            # Initialize specific collection
            success = init_collection(args.collection, limit=args.limit, recreate=args.recreate)
            if not success:
                sys.exit(1)

    except KeyboardInterrupt:
        log("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
