#!/usr/bin/env python3
"""
Generic Embedding Initialization Script
Uses EmbeddingFactory to support any embedding provider (STAPI, DashScope, OpenAI, etc.)
Automatically reads configuration from .env file
"""

import time
import json
import sys
import glob
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

from config import settings
from llm_factory import EmbeddingFactory

BATCH_SIZE = 50  # Process 50 documents at a time
UPLOAD_BATCH_SIZE = 100  # Upload to Qdrant in batches of 100


def log(msg):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def load_documents():
    """Load documents from all chunk files (text, audio, event)."""
    documents = []

    # Load all JSONL files from chunks directory
    chunk_files = glob.glob("chunks/*.jsonl")

    log("Loading documents from chunks...")
    text_count = 0

    for chunk_file in chunk_files:
        log(f"Loading documents from {chunk_file}...")
        with open(chunk_file, "r", encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)

                # Check id and text
                doc_id = chunk.get("id", "")
                if not doc_id:
                    log(f"❌ Missing id in chunk: {chunk}")
                    continue

                text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
                if not text:
                    log(f"❌ Missing text in chunk id {doc_id}")
                    continue

                # Metadata
                metadata = chunk.get("metadata", {})
                if not isinstance(metadata, dict):
                    log(f"❌ Invalid metadata in chunk id {doc_id}: {metadata}")
                    metadata = {}

                # Add to list
                documents.append({
                    "id": doc_id,
                    "text": text,
                    "metadata": metadata
                })
                text_count += 1

    log(f"✅ Loaded {text_count} text documents")
    return documents


def init_qdrant(collection_name: str, embedding_dim: int):
    """Initialize Qdrant collection."""
    log("Initializing Qdrant collection...")
    client = QdrantClient(url=settings.qdrant_url)

    # Delete existing collection
    try:
        client.delete_collection(collection_name)
        log(f"🗑️  Deleted existing collection: {collection_name}")
    except Exception:
        pass

    # Create new collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
    )
    log(f"✅ Created collection: {collection_name} (dim={embedding_dim})")

    return client


def main():
    """Main initialization process."""
    start_time = time.time()

    log("=" * 60)
    log("Generic Embedding Initialization")
    log("=" * 60)
    log(f"Embedding Provider: {settings.embedding_provider}")
    log(f"Embedding Model: {settings.embedding_model}")
    log(f"Qdrant URL: {settings.qdrant_url}")
    log(f"Collection: {settings.qdrant_collection}")
    log(f"Batch size: {BATCH_SIZE}")
    log("")

    # Initialize embeddings using factory
    log("Initializing embedding model...")
    embeddings = EmbeddingFactory.create_embeddings()

    # Get embedding dimension from a test embedding
    test_embedding = embeddings.embed_query("test")
    embedding_dim = len(test_embedding)
    log(f"✅ Embedding dimension: {embedding_dim}")
    log("")

    # Load documents
    documents = load_documents()
    total_docs = len(documents)
    total_batches = (total_docs + BATCH_SIZE - 1) // BATCH_SIZE

    # Initialize Qdrant
    qdrant_client = init_qdrant(settings.qdrant_collection, embedding_dim)
    log("")

    # Generate embeddings and upload in batches
    all_points = []
    failed_docs = []
    successful_count = 0

    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_docs)
        batch_docs = documents[start_idx:end_idx]
        batch_num = batch_idx + 1

        log(f"📦 Batch {batch_num}/{total_batches} ({len(batch_docs)} docs, indices {start_idx}-{end_idx-1})")

        # Generate embeddings for this batch
        batch_start_time = time.time()
        batch_texts = [doc["text"] for doc in batch_docs]

        try:
            # Use batch embedding for efficiency
            batch_embeddings = embeddings.embed_documents(batch_texts)

            # Create Qdrant points
            for i, (doc, embedding) in enumerate(zip(batch_docs, batch_embeddings)):
                doc_idx = start_idx + i

                point = PointStruct(
                    id=doc_idx,
                    vector=embedding,
                    payload={
                        "text": doc["text"],
                        "chunk_id": doc["id"],  # Preserve original chunk ID
                        **doc["metadata"]
                    }
                )
                all_points.append(point)
                successful_count += 1

            log(f"   ✓ Embedded {len(batch_docs)} documents in batch")

        except Exception as e:
            log(f"   ❌ Failed batch {batch_num}: {e}")
            # Try individual documents as fallback
            for i, doc in enumerate(batch_docs):
                doc_idx = start_idx + i
                try:
                    embedding = embeddings.embed_query(doc["text"])
                    point = PointStruct(
                        id=doc_idx,
                        vector=embedding,
                        payload={
                            "text": doc["text"],
                            "chunk_id": doc["id"],
                            **doc["metadata"]
                        }
                    )
                    all_points.append(point)
                    successful_count += 1
                except Exception as e2:
                    log(f"   ❌ Failed doc {doc_idx}: {e2}")
                    failed_docs.append((doc_idx, str(e2)))

        batch_elapsed = time.time() - batch_start_time
        log(f"✅ Batch {batch_num}/{total_batches} complete ({batch_elapsed:.1f}s)")

        # Upload to Qdrant every UPLOAD_BATCH_SIZE points or at end
        if len(all_points) >= UPLOAD_BATCH_SIZE or batch_num == total_batches:
            log(f"💾 Uploading {len(all_points)} points to Qdrant...")
            try:
                qdrant_client.upsert(
                    collection_name=settings.qdrant_collection,
                    points=all_points
                )
                log(f"✅ Uploaded {len(all_points)} points to Qdrant")
                all_points = []  # Clear buffer
            except Exception as e:
                log(f"❌ Failed to upload to Qdrant: {e}")
                # Save progress to file
                with open("failed_upload_points.json", "w") as f:
                    json.dump([{"id": p.id, "payload": p.payload} for p in all_points], f)
                log(f"💾 Saved failed points to failed_upload_points.json")
                sys.exit(1)

        # Estimate remaining time
        if batch_num > 0:
            elapsed = time.time() - start_time
            avg_time_per_batch = elapsed / batch_num
            remaining_batches = total_batches - batch_num
            estimated_remaining = avg_time_per_batch * remaining_batches
            log(f"⏱️  Estimated time remaining: {estimated_remaining/60:.1f} minutes")

        log("")

    # Final statistics
    elapsed = time.time() - start_time
    log("=" * 60)
    log("Initialization Complete!")
    log("=" * 60)
    log(f"Total documents: {total_docs}")
    log(f"Successfully embedded: {successful_count}")
    log(f"Failed: {len(failed_docs)}")
    log(f"Time elapsed: {elapsed/60:.1f} minutes ({elapsed:.1f} seconds)")
    if successful_count > 0:
        log(f"Average time per document: {elapsed/successful_count:.2f}s")
    log("")

    if failed_docs:
        log("Failed documents:")
        for doc_idx, error in failed_docs:
            log(f"  - Doc {doc_idx}: {error}")
        log("")

    # Verify Qdrant
    info = qdrant_client.get_collection(settings.qdrant_collection)
    log(f"Qdrant collection points: {info.points_count}")
    log("")

    log("✅ All done!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
