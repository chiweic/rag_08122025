#!/usr/bin/env python3
"""
Initialize FAQ collection in Qdrant with embeddings.
This script loads FAQ questions from faq.json and creates a Qdrant collection with embeddings.
"""

import json
import logging
from pathlib import Path
from tqdm import tqdm

from config import settings
from vector_store import QdrantVectorStore
from llm_factory import EmbeddingFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_faq_questions(faq_path: str = "faq.json"):
    """Load FAQ questions from JSON file."""
    try:
        faq_file = Path(faq_path)
        if not faq_file.exists():
            logger.error(f"FAQ file not found: {faq_path}")
            return []

        with open(faq_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            questions = data.get('questions', [])

        logger.info(f"Loaded {len(questions)} FAQ questions from {faq_path}")
        return questions
    except Exception as e:
        logger.error(f"Error loading FAQ questions: {e}")
        return []


def create_faq_collection(collection_name: str = "ddm_faq", limit: int = None):
    """Create Qdrant collection for FAQ questions with embeddings."""

    # Load FAQ questions
    logger.info("Loading FAQ questions...")
    faq_questions = load_faq_questions()

    if not faq_questions:
        logger.error("No FAQ questions loaded. Exiting.")
        return

    # Limit to first N questions if specified
    if limit:
        faq_questions = faq_questions[:limit]
        logger.info(f"Limited to first {limit} FAQ questions for testing")

    logger.info(f"Processing {len(faq_questions)} FAQ questions...")

    # Initialize embeddings model
    logger.info("Initializing embeddings model...")
    embeddings = EmbeddingFactory.create_embeddings()

    # Initialize vector store
    logger.info(f"Connecting to Qdrant at {settings.qdrant_url}...")
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection_name=collection_name
    )

    # Get embedding dimension (DashScope text-embedding-v4 is 1024-dim)
    # We'll get this from the first embedding
    test_embedding = embeddings.embed_query("test")
    embedding_dim = len(test_embedding)
    logger.info(f"Embedding dimension: {embedding_dim}")

    # Check if collection already exists
    try:
        collection_info = vector_store.get_collection_info()
        if collection_info:
            logger.warning(f"Collection '{collection_name}' already exists with {collection_info['points_count']} points")
            response = input("Do you want to recreate it? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Exiting without changes.")
                return

            # Recreate collection
            logger.info(f"Recreating collection '{collection_name}'...")
            vector_store.create_collection(vector_size=embedding_dim, recreate=True)
    except Exception as e:
        logger.info(f"Collection does not exist yet, will create new one")
        # Create collection
        logger.info(f"Creating collection '{collection_name}' with vector size {embedding_dim}...")
        vector_store.create_collection(vector_size=embedding_dim, recreate=False)

    # Generate embeddings in batches
    logger.info("Generating embeddings for FAQ questions...")
    batch_size = 100
    all_embeddings = []

    for i in tqdm(range(0, len(faq_questions), batch_size), desc="Embedding batches"):
        batch = faq_questions[i:i + batch_size]

        # Generate embeddings for this batch
        batch_embeddings = embeddings.embed_documents(batch)
        all_embeddings.extend(batch_embeddings)

    logger.info(f"Generated embeddings for {len(faq_questions)} questions")

    # Prepare documents
    documents = []
    for i, question in enumerate(faq_questions):
        documents.append({
            'id': i,  # Include ID in document to avoid collision
            'text': question,
            'metadata': {
                'question': question,
                'source': 'faq',
                'faq_id': i
            }
        })

    # Upload to Qdrant in batches
    logger.info(f"Uploading {len(documents)} FAQ questions to Qdrant...")
    upload_batch_size = 50

    for i in tqdm(range(0, len(documents), upload_batch_size), desc="Uploading batches"):
        doc_batch = documents[i:i + upload_batch_size]
        emb_batch = all_embeddings[i:i + upload_batch_size]
        vector_store.add_documents(doc_batch, emb_batch)

    # Verify upload
    collection_info = vector_store.get_collection_info()
    logger.info(f"✅ FAQ collection created successfully!")
    logger.info(f"   Collection: {collection_name}")
    logger.info(f"   Points: {collection_info.get('points_count', 'unknown')}")
    logger.info(f"   Vector size: {collection_info.get('vector_size', embedding_dim)}")
    logger.info(f"   Status: {collection_info.get('status', 'unknown')}")


if __name__ == "__main__":
    import sys

    # Check for limit argument
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            logger.info(f"Using limit: {limit} questions")
        except ValueError:
            logger.error(f"Invalid limit: {sys.argv[1]}")
            sys.exit(1)

    create_faq_collection(limit=limit)
