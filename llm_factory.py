from typing import Optional, Any
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.embeddings import Embeddings
import logging
from config import settings
from ollama_embeddings import OllamaEmbeddings
from dashscope_embeddings import DashScopeEmbeddings

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory class for creating LLM instances based on configuration."""
    
    @staticmethod
    def create_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        streaming: bool = False
    ) -> BaseLanguageModel:
        """Create an LLM instance based on the provider."""
        provider = provider or settings.llm_provider
        model = model or settings.llm_model
        max_tokens = max_tokens or settings.llm_max_tokens
        
        logger.info(f"Creating LLM: provider={provider}, model={model}")
        
        if provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not found in settings")
            
            # Set temperature=1.0 for models that only support default temperature
            temp_restricted_models = ["gpt-5-mini"]
            temperature = 1.0 if model in temp_restricted_models else None
            
            llm_kwargs = {
                "api_key": settings.openai_api_key,
                "model": model or "gpt-4o-mini",
                "max_tokens": max_tokens,
                "streaming": streaming
            }
            
            if temperature is not None:
                llm_kwargs["temperature"] = temperature
                
            return ChatOpenAI(**llm_kwargs)
        
        elif provider == "deepseek":
            if not settings.deepseek_api_key:
                raise ValueError("DeepSeek API key not found in settings")
            # DeepSeek uses OpenAI-compatible API
            return ChatOpenAI(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com/v1",
                model=model or "deepseek-chat",
                max_tokens=max_tokens,
                streaming=streaming
            )
        
        elif provider == "google":
            if not settings.google_api_key:
                raise ValueError("Google API key not found in settings")
            return ChatGoogleGenerativeAI(
                google_api_key=settings.google_api_key,
                model=model or "gemini-1.5-flash",
                max_output_tokens=max_tokens,
                streaming=streaming
            )
        
        elif provider == "dashscope":
            if not settings.dashscope_api_key:
                raise ValueError("DASHSCOPE API key not found in settings")
            # DASHSCOPE uses OpenAI-compatible API
            return ChatOpenAI(
                api_key=settings.dashscope_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model=model or "qwen3-235b-a22b-instruct-2507",
                max_tokens=max_tokens,
                streaming=streaming
            )
        
        elif provider == "custom":
            if not settings.custom_llm_base_url:
                raise ValueError("Custom LLM base URL not found in settings")
            # Custom endpoint uses OpenAI-compatible API
            return ChatOpenAI(
                api_key=settings.custom_llm_api_key or "empty",
                base_url=settings.custom_llm_base_url,
                model=model or "output/qwen3-4b_lora_sft_5000",
                max_tokens=max_tokens,
                streaming=streaming
            )
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")


class EmbeddingFactory:
    """Factory class for creating embedding instances based on configuration."""
    
    @staticmethod
    def create_embeddings(
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Embeddings:
        """Create an embeddings instance based on the provider."""
        provider = provider or settings.embedding_provider
        model = model or settings.embedding_model
        
        logger.info(f"Creating Embeddings: provider={provider}, model={model}")
        
        if provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not found in settings")
            return OpenAIEmbeddings(
                api_key=settings.openai_api_key,
                model=model or "text-embedding-3-small"
            )
        
        elif provider == "google":
            if not settings.google_api_key:
                raise ValueError("Google API key not found in settings")

            # Google embeddings support output_dimensionality (768, 1536, or 3072)
            embedding_kwargs = {
                "google_api_key": settings.google_api_key,
                "model": model or "models/embedding-001"
            }

            # Add output_dimensionality if dimension is specified and not default 768
            if settings.embedding_dimension and settings.embedding_dimension != 768:
                embedding_kwargs["output_dimensionality"] = settings.embedding_dimension
                logger.info(f"Using Google embeddings with output_dimensionality={settings.embedding_dimension}")

            return GoogleGenerativeAIEmbeddings(**embedding_kwargs)
        
        elif provider in ["huggingface", "local"]:
            # Use HuggingFace embeddings for local models
            model_name = model or "BAAI/bge-small-zh-v1.5"

            # Check if it's a local path
            import os
            import torch

            # GPU fallback mechanism - try devices in order of preference
            devices_to_try = ['cuda:1', 'cuda:0', 'cuda', 'cpu']
            device = 'cpu'  # Default fallback

            for test_device in devices_to_try:
                try:
                    if test_device.startswith('cuda') and not torch.cuda.is_available():
                        continue

                    # Test if device works with a simple operation
                    if test_device.startswith('cuda'):
                        test_tensor = torch.randn(10).to(test_device)
                        _ = test_tensor * 2  # Simple operation to test compatibility

                    device = test_device
                    logger.info(f"Using device: {device} for embeddings")
                    break

                except Exception as e:
                    logger.warning(f"Device {test_device} failed, trying next: {e}")
                    continue

            if device == 'cpu':
                logger.info("Using CPU for embeddings (GPU compatibility issues)")
            else:
                logger.info(f"Successfully using GPU device: {device}")

            if os.path.exists(model_name):
                logger.info(f"Loading local fine-tuned model from: {model_name}")
                return HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={'device': device},
                    encode_kwargs={'normalize_embeddings': True}
                )
            else:
                # Load from HuggingFace hub
                return HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={'device': device},
                    encode_kwargs={'normalize_embeddings': True}
                )

        elif provider == "ollama":
            if not settings.ollama_base_url:
                raise ValueError("Ollama base URL not found in settings")

            logger.info(f"Using Ollama embeddings from {settings.ollama_base_url} with {settings.ollama_max_workers} workers")
            return OllamaEmbeddings(
                base_url=settings.ollama_base_url,
                model=model or "bge-m3",
                api_key=settings.ollama_api_key,
                max_workers=settings.ollama_max_workers
            )

        elif provider == "dashscope":
            if not settings.dashscope_api_key:
                raise ValueError("DashScope API key not found in settings")
            # DashScope uses custom wrapper for compatibility
            logger.info(f"Using DashScope embeddings with model {model}")
            return DashScopeEmbeddings(
                api_key=settings.dashscope_api_key,
                model=model or "text-embedding-v4",
                max_workers=1  # Sequential processing to avoid rate limits
            )

        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
    
    @staticmethod
    def get_embedding_dimension(provider: Optional[str] = None, model: Optional[str] = None) -> int:
        """Get the embedding dimension for the specified provider and model.
        
        This method now dynamically detects the dimension by creating a test embedding.
        """
        provider = provider or settings.embedding_provider
        model = model or settings.embedding_model
        
        # Try to dynamically detect dimension by creating a test embedding
        try:
            logger.info(f"Detecting embedding dimension for {provider}/{model}")
            factory = EmbeddingFactory()
            embeddings = factory.create_embeddings(provider, model)
            
            # Generate a test embedding to get dimension
            test_text = "test"
            test_embedding = embeddings.embed_query(test_text)
            dimension = len(test_embedding)
            
            logger.info(f"Detected embedding dimension: {dimension}")
            return dimension
            
        except Exception as e:
            logger.warning(f"Failed to auto-detect embedding dimension: {e}")
            
            # Fallback to known dimensions
            dimension_map = {
                "openai": {
                    "text-embedding-3-small": 1536,
                    "text-embedding-3-large": 3072,
                    "text-embedding-ada-002": 1536
                },
                "google": {
                    "models/embedding-001": 768
                },
                "huggingface": {
                    "BAAI/bge-small-zh-v1.5": 512,
                    "BAAI/bge-base-zh-v1.5": 768,
                    "BAAI/bge-large-zh-v1.5": 1024,
                    "intfloat/multilingual-e5-large": 1024,
                    "intfloat/multilingual-e5-base": 768,
                    "intfloat/multilingual-e5-small": 384,
                    "sentence-transformers/all-MiniLM-L6-v2": 384,
                    "sentence-transformers/all-mpnet-base-v2": 768
                },
                "local": {
                    "/home/chiweic/repo/synthetic_dataset/emb_finetune_small_32/final": 512,
                    "BAAI/bge-small-zh-v1.5": 512,
                    "BAAI/bge-base-zh-v1.5": 768,
                    "BAAI/bge-large-zh-v1.5": 1024,
                    "intfloat/multilingual-e5-large": 1024,
                    "intfloat/multilingual-e5-base": 768,
                    "intfloat/multilingual-e5-small": 384
                },
                "ollama": {
                    "bge-m3": 1024,
                    "bge-large": 1024,
                    "nomic-embed-text": 768
                },
                "dashscope": {
                    "text-embedding-v3": 1024,
                    "text-embedding-v4": 1024
                }
            }
            
            if provider in dimension_map and model in dimension_map[provider]:
                return dimension_map[provider][model]
            
            # Return default or configured dimension
            return settings.embedding_dimension