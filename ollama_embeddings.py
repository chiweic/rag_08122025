"""
Custom Ollama Embeddings wrapper for LangChain
"""

import requests
import logging
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain.schema.embeddings import Embeddings

logger = logging.getLogger(__name__)


class OllamaEmbeddings(Embeddings):
    """Ollama embeddings integration for LangChain."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = None,
        timeout: int = 30,
        max_workers: int = 10
    ):
        """
        Initialize Ollama embeddings.

        Args:
            base_url: Base URL for Ollama API (e.g., http://ollama.changpt.org)
            model: Model name (e.g., bge-m3)
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_workers: Maximum concurrent workers for parallel requests
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_workers = max_workers

        # Prepare headers
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

        logger.info(f"Initialized OllamaEmbeddings: {base_url}, model={model}, max_workers={max_workers}")

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": self.model,
            "prompt": text
        }

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            if "embedding" in result:
                return result["embedding"]
            else:
                raise ValueError(f"No embedding in response: {result}")

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
