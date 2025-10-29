#!/usr/bin/env python3
"""
Standalone script for Ollama embedding initialization.
Runs in foreground with detailed logging and progress tracking.
"""

import requests
import time
import json
import sys
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configuration
OLLAMA_URL = "http://ollama.changpt.org"
OLLAMA_API_KEY = "ddm_api_key"
OLLAMA_MODEL = "bge-m3"
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "ddm_rag"
EMBEDDING_DIM = 1024
BATCH_SIZE = 1
UPLOAD_BATCH_SIZE = 50  # Upload to Qdrant in batches


def log(msg):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def generate_embedding(text, max_retries=3):
    """Generate embedding with retry logic."""
    url = f"{OLLAMA_URL}/api/embeddings"
    headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
    payload = {"model": OLLAMA_MODEL, "prompt": text}

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result["embedding"]

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 500:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    log(f"⚠️  500 error, retry {attempt+1}/{max_retries} in {wait_time}s...")
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


def load_documents():
    """Load documents from text_chunks.jsonl."""
    log("Loading documents from chunks/text_chunks.jsonl...")
    documents = []

    with open("chunks/text_chunks.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            # Combine header and content
            text = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()

            doc = {
                "id": chunk.get("id", ""),
                "text": text,
                "metadata": {
                    "chunk_id": chunk.get("id", ""),
                    "header": chunk.get("header", ""),
                    **chunk.get("metadata", {})
                }
            }
            documents.append(doc)

    log(f"✅ Loaded {len(documents)} documents")
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
    log("Ollama Embedding Initialization (Foreground)")
    log("=" * 60)
    log(f"Ollama URL: {OLLAMA_URL}")
    log(f"Model: {OLLAMA_MODEL}")
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

    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_docs)
        batch_docs = documents[start_idx:end_idx]
        batch_num = batch_idx + 1

        log(f"📦 Batch {batch_num}/{total_batches} ({len(batch_docs)} docs, indices {start_idx}-{end_idx-1})")

        # Generate embeddings for this batch
        for i, doc in enumerate(batch_docs):
            doc_idx = start_idx + i
            try:
                embedding = generate_embedding(doc["text"])

                # Create Qdrant point
                point = PointStruct(
                    id=doc_idx,
                    vector=embedding,
                    payload={
                        "text": doc["text"],
                        **doc["metadata"]
                    }
                )
                all_points.append(point)

                # Progress indicator
                if (i + 1) % 10 == 0 or (i + 1) == len(batch_docs):
                    log(f"   ✓ Embedded {i+1}/{len(batch_docs)} documents in batch")

            except Exception as e:
                log(f"   ❌ Failed doc {doc_idx}: {e}")
                failed_docs.append((doc_idx, str(e)))
                # Continue with next document instead of stopping

        log(f"✅ Batch {batch_num}/{total_batches} complete")

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

        log("")

    # Final statistics
    elapsed = time.time() - start_time
    log("=" * 60)
    log("Initialization Complete!")
    log("=" * 60)
    log(f"Total documents: {total_docs}")
    log(f"Successfully embedded: {total_docs - len(failed_docs)}")
    log(f"Failed: {len(failed_docs)}")
    log(f"Time elapsed: {elapsed/60:.1f} minutes ({elapsed:.1f} seconds)")
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
