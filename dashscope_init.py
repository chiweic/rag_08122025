#!/usr/bin/env python3
"""
DashScope Embedding Initialization Script
Uses Alibaba Cloud DashScope API for fast embedding generation
Model: text-embedding-v4 (1024-dim)
"""

import requests
import time
import json
import sys
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configuration
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_API_KEY = "sk-a90d848a7c794e29b55881dfe8371642"
DASHSCOPE_MODEL = "text-embedding-v4"
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "ddm_rag"
EMBEDDING_DIM = 1024
BATCH_SIZE = 50  # Process 50 documents at a time
UPLOAD_BATCH_SIZE = 100  # Upload to Qdrant in batches of 100


def log(msg):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def generate_embedding(text, max_retries=3):
    """Generate embedding using DashScope API with retry logic."""
    url = f"{DASHSCOPE_URL}/embeddings"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DASHSCOPE_MODEL,
        "input": text
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result["data"][0]["embedding"]

        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    log(f"⚠️  {e.response.status_code} error, retry {attempt+1}/{max_retries} in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    log(f"❌ Failed after {max_retries} retries: {e}")
                    raise
            else:
                log(f"❌ HTTP {e.response.status_code}: {e}")
                raise

        except Exception as e:
            log(f"❌ Error: {e}")
            raise

    return None

import glob
def load_documents():
    """Load documents from all chunk files (text, audio, event)."""
    documents = []

    # jsons from the chunks directory
    chunk_files= glob.glob("chunks/*.jsonl")

    # Load text chunks
    log("Loading documents from chunks...")
    text_count = 0

    for chunk_file in chunk_files:
        log(f"Loading documents from {chunk_file}...")
        with open(chunk_file, "r", encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                # check id and text
                id = chunk.get("id", "")
                if not id:
                    log(f"❌ Missing id in chunk: {chunk}")
                text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
                if not text:
                    log(f"❌ Missing text in chunk id {id}")
                # metadata
                metadata = chunk.get("metadata", {})
                if not isinstance(metadata, dict):
                    log(f"❌ Invalid metadata in chunk id {id}: {metadata}")
                # add to list
                documents.append({
                    "id": id,
                    "text": text,
                    "metadata": metadata
                })
                text_count += 1
    
    log(f"✅ Loaded {text_count} text documents")
    return documents


def init_qdrant():
    """Initialize Qdrant collection."""
    log("Initializing Qdrant collection...")
    client = QdrantClient(url=QDRANT_URL)

    # Delete existing collection
    try:
        client.delete_collection(QDRANT_COLLECTION)
        log(f"🗑️  Deleted existing collection: {QDRANT_COLLECTION}")
    except Exception:
        pass

    # Create new collection
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
    )
    log(f"✅ Created collection: {QDRANT_COLLECTION} (dim={EMBEDDING_DIM})")

    return client


def main():
    """Main initialization process."""
    start_time = time.time()

    log("=" * 60)
    log("DashScope Embedding Initialization")
    log("=" * 60)
    log(f"DashScope URL: {DASHSCOPE_URL}")
    log(f"Model: {DASHSCOPE_MODEL}")
    log(f"Dimension: {EMBEDDING_DIM}")
    log(f"Batch size: {BATCH_SIZE}")
    log("")

    # Load documents
    documents = load_documents()
    total_docs = len(documents)
    total_batches = (total_docs + BATCH_SIZE - 1) // BATCH_SIZE

    # Initialize Qdrant
    qdrant_client = init_qdrant()
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

        for i, doc in enumerate(batch_docs):
            doc_idx = start_idx + i
            try:
                embedding = generate_embedding(doc["text"])

                # Create Qdrant point
                point = PointStruct(
                    id = doc_idx,
                    vector = embedding,
                    payload={
                        "text": doc["text"],
                        "chunk_id": doc["id"],  # Preserve original chunk ID
                        **doc["metadata"]
                    }
                )
                all_points.append(point)
                successful_count += 1

                # Progress indicator
                if (i + 1) % 10 == 0 or (i + 1) == len(batch_docs):
                    log(f"   ✓ Embedded {i+1}/{len(batch_docs)} documents in batch")

            except Exception as e:
                log(f"   ❌ Failed doc {doc_idx}: {e}")
                failed_docs.append((doc_idx, str(e)))
                # Continue with next document instead of stopping

        batch_elapsed = time.time() - batch_start_time
        log(f"✅ Batch {batch_num}/{total_batches} complete ({batch_elapsed:.1f}s)")

        # Upload to Qdrant every UPLOAD_BATCH_SIZE points or at end
        if len(all_points) >= UPLOAD_BATCH_SIZE or batch_num == total_batches:
            log(f"💾 Uploading {len(all_points)} points to Qdrant...")
            try:
                qdrant_client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=all_points
                )
                log(f"✅ Uploaded {len(all_points)} points to Qdrant")
                all_points = []  # Clear buffer
            except Exception as e:
                log(f"❌ Failed to upload to Qdrant: {e}")
                # Save progress to file
                with open("failed_upload_points.json", "w") as f:
                    json.dump([p.dict() for p in all_points], f)
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
    log(f"Average time per document: {elapsed/successful_count:.2f}s")
    log("")

    if failed_docs:
        log("Failed documents:")
        for doc_idx, error in failed_docs:
            log(f"  - Doc {doc_idx}: {error}")
        log("")

    # Verify Qdrant
    info = qdrant_client.get_collection(QDRANT_COLLECTION)
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
