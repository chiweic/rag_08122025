"""
Custom DashScope Embeddings wrapper for LangChain
"""

import requests
import logging
import time
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain.schema.embeddings import Embeddings

logger = logging.getLogger(__name__)


class DashScopeEmbeddings(Embeddings):
    """DashScope embeddings integration for LangChain."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-v4",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout: int = 60,
        max_workers: int = 10
    ):
        """
        Initialize DashScope embeddings.

        Args:
            api_key: DashScope API key
            model: Model name (e.g., text-embedding-v3, text-embedding-v4)
            base_url: Base URL for DashScope API
            timeout: Request timeout in seconds
            max_workers: Maximum concurrent workers for parallel requests
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_workers = max_workers

        # Prepare headers
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        logger.info(f"Initialized DashScopeEmbeddings: model={model}, max_workers={max_workers}")

    def _generate_embedding(self, text: str, max_retries: int = 3) -> List[float]:
        """Generate embedding for a single text with retry logic."""
        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model,
            "input": text  # DashScope expects "input" not "prompt"
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                result = response.json()
                # DashScope returns: {"data": [{"embedding": [...]}]}
                if "data" in result and len(result["data"]) > 0:
                    return result["data"][0]["embedding"]
                else:
                    raise ValueError(f"No embedding in response: {result}")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code >= 500:
                    # Server error - retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        logger.warning(f"{e.response.status_code} error on attempt {attempt+1}/{max_retries}, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Failed after {max_retries} retries: {e}")
                        raise
                else:
                    # Other HTTP errors - don't retry
                    logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                    raise
            except Exception as e:
                logger.error(f"Failed to generate embedding: {e}")
                raise

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents using parallel requests.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings (preserving input order)
        """
        if not texts:
            return []

        logger.info(f"Embedding {len(texts)} documents with {self.max_workers} parallel workers")

        # Use ThreadPoolExecutor for parallel API requests
        embeddings = [None] * len(texts)  # Pre-allocate to preserve order

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self._generate_embedding, text): i
                for i, text in enumerate(texts)
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    embedding = future.result()
                    embeddings[index] = embedding
                    completed += 1

                    if completed % 10 == 0 or completed == len(texts):
                        logger.info(f"Embedded {completed}/{len(texts)} documents")

                except Exception as e:
                    logger.error(f"Failed to embed document at index {index}: {e}")
                    raise

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a query text.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector
        """
        return self._generate_embedding(text)
