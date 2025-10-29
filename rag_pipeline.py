import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.embeddings import Embeddings
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
import time
import json

from vector_store import QdrantVectorStore
from llm_factory import LLMFactory, EmbeddingFactory
from config import settings

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Main RAG pipeline for retrieval and synthesis."""
    
    def __init__(
        self,
        llm: Optional[BaseLanguageModel] = None,
        embeddings: Optional[Embeddings] = None,
        vector_store: Optional[QdrantVectorStore] = None
    ):
        self.llm = llm or LLMFactory.create_llm()
        self.embeddings = embeddings or EmbeddingFactory.create_embeddings()
        self.vector_store = vector_store or QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection_name=settings.qdrant_collection
        )
        
        # Initialize prompts
        self._init_prompts()
    
    def _init_prompts(self):
        """Initialize prompt templates."""
        self.qa_prompt = ChatPromptTemplate.from_template("""
您是一位專精於佛教教義的助理，特別熟悉聖嚴法師的著作。
請根據以下提供的內容回答問題。如果答案無法從內容中找到，請明確說明。

重要：請務必使用繁體中文回答。

相關內容：
{context}

問題：{question}

請根據提供的內容，給出全面且準確的答案。可以直接引用原文中的相關段落。

回答：""")
        
        self.summary_prompt = ChatPromptTemplate.from_template("""
請將以下佛教文本摘錄總結成一個簡潔連貫的回應。

重要：請務必使用繁體中文回答。

內容：
{context}

總結：""")
    
    def retrieve(
        self, 
        query: str, 
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Dict[str, Any]], float]:
        """Retrieve relevant documents from the vector store."""
        start_time = time.time()
        top_k = top_k or settings.retrieval_top_k
        
        try:
            # Generate embedding for the query
            query_embedding = self.embeddings.embed_query(query)
            
            # Search in vector store
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_dict=filter_dict
            )
            
            retrieval_time = time.time() - start_time
            logger.info(f"Retrieved {len(results)} documents in {retrieval_time:.2f}s")
            
            return results, retrieval_time
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            raise
    
    def synthesize(
        self, 
        question: str, 
        contexts: List[Dict[str, Any]],
        prompt_type: str = "qa"
    ) -> tuple[str, float]:
        """Synthesize an answer from retrieved contexts."""
        start_time = time.time()
        
        try:
            # Prepare context string
            context_texts = []
            for ctx in contexts:
                text = ctx.get("text", "")
                metadata = ctx.get("metadata", {})
                
                # Add source information
                source_info = f"[Source: {metadata.get('title', 'Unknown')}"
                if 'chunk_index' in metadata:
                    source_info += f", Chunk {metadata['chunk_index'] + 1}"
                source_info += "]"
                
                context_texts.append(f"{source_info}\n{text}")
            
            context_str = "\n\n---\n\n".join(context_texts)
            
            # Select prompt based on type
            if prompt_type == "summary":
                prompt = self.summary_prompt
                inputs = {"context": context_str}
            else:  # default to QA
                prompt = self.qa_prompt
                inputs = {"context": context_str, "question": question}
            
            # Create chain and invoke
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke(inputs)
            
            synthesis_time = time.time() - start_time
            logger.info(f"Synthesized response in {synthesis_time:.2f}s")
            
            return response, synthesis_time
            
        except Exception as e:
            logger.error(f"Error during synthesis: {e}")
            raise
    
    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """Complete RAG pipeline: retrieve and synthesize."""
        total_start = time.time()
        
        # Retrieve relevant documents
        contexts, retrieval_time = self.retrieve(
            query=question,
            top_k=top_k,
            filter_dict=filter_dict
        )
        
        if not contexts:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
                "computation_time": {
                    "retrieval": retrieval_time,
                    "synthesis": 0,
                    "total": time.time() - total_start
                }
            }
        
        # Synthesize answer
        answer, synthesis_time = self.synthesize(
            question=question,
            contexts=contexts,
            prompt_type="qa"
        )
        
        # Prepare response
        response = {
            "answer": answer,
            "computation_time": {
                "retrieval": retrieval_time,
                "synthesis": synthesis_time,
                "total": time.time() - total_start
            }
        }
        
        if include_sources:
            sources = []
            for ctx in contexts:
                metadata = ctx.get("metadata", {})
                source_type = metadata.get("source_type", "text")

                # Build source info based on type
                source_info = {
                    "score": ctx.get("score", 0),
                    "source_type": source_type,
                    "category": metadata.get("category", ""),
                    "chunk_id": metadata.get("chunk_id", ""),
                    "text": ctx.get("text", "")
                }

                # Type-specific fields
                if source_type == "audio":
                    source_info["title"] = metadata.get("audio_title", "Unknown Audio")
                    source_info["speaker"] = metadata.get("speaker", "")
                    source_info["timestamp"] = f"{metadata.get('timestamp_start', '')}-{metadata.get('timestamp_end', '')}"
                    source_info["audio_url"] = metadata.get("audio_url", "")
                elif source_type == "event":
                    source_info["title"] = metadata.get("event_title", "Unknown Event")
                    source_info["location"] = metadata.get("event_location", "")
                    source_info["time_period"] = metadata.get("event_time_period", "")
                else:  # text
                    source_info["title"] = metadata.get("title", "Unknown")
                    source_info["pages"] = f"{metadata.get('start_page', '')}-{metadata.get('end_page', '')}" if metadata.get('start_page') else ""
                    source_info["source"] = metadata.get("source", "")

                sources.append(source_info)
            response["sources"] = sources
        
        return response
    
    async def stream_query(
        self,
        question: str,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_sources: bool = True
    ) -> AsyncGenerator[str, None]:
        """Complete RAG pipeline with streaming response."""
        total_start = time.time()
        
        # Retrieve relevant documents
        contexts, retrieval_time = self.retrieve(
            query=question,
            top_k=top_k,
            filter_dict=filter_dict
        )
        
        # Send sources first
        if include_sources and contexts:
            sources = []
            for ctx in contexts:
                metadata = ctx.get("metadata", {})
                source_type = metadata.get("source_type", "text")

                # Build source info based on type
                source_info = {
                    "score": ctx.get("score", 0),
                    "source_type": source_type,
                    "category": metadata.get("category", ""),
                    "chunk_id": metadata.get("chunk_id", ""),
                    "text": ctx.get("text", "")
                }

                # Type-specific fields
                if source_type == "audio":
                    source_info["title"] = metadata.get("audio_title", "Unknown Audio")
                    source_info["speaker"] = metadata.get("speaker", "")
                    source_info["timestamp"] = f"{metadata.get('timestamp_start', '')}-{metadata.get('timestamp_end', '')}"
                    source_info["audio_url"] = metadata.get("audio_url", "")
                elif source_type == "event":
                    source_info["title"] = metadata.get("event_title", "Unknown Event")
                    source_info["location"] = metadata.get("event_location", "")
                    source_info["time_period"] = metadata.get("event_time_period", "")
                else:  # text
                    source_info["title"] = metadata.get("title", "Unknown")
                    source_info["pages"] = f"{metadata.get('start_page', '')}-{metadata.get('end_page', '')}" if metadata.get('start_page') else ""
                    source_info["source"] = metadata.get("source", "")

                sources.append(source_info)

            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'retrieval_time': retrieval_time})}\n\n"
        
        if not contexts:
            yield f"data: {json.dumps({'type': 'answer', 'content': 'I could not find any relevant information to answer your question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'total_time': time.time() - total_start})}\n\n"
            return
        
        # Create streaming LLM
        streaming_llm = LLMFactory.create_llm(streaming=True)
        
        # Prepare context
        context_texts = []
        for ctx in contexts:
            text = ctx.get("text", "")
            metadata = ctx.get("metadata", {})
            
            source_info = f"[Source: {metadata.get('title', 'Unknown')}"
            if 'chunk_index' in metadata:
                source_info += f", Chunk {metadata['chunk_index'] + 1}"
            source_info += "]"
            
            context_texts.append(f"{source_info}\n{text}")
        
        context_str = "\n\n---\n\n".join(context_texts)
        
        # Stream synthesis
        synthesis_start = time.time()
        inputs = {"context": context_str, "question": question}
        chain = self.qa_prompt | streaming_llm | StrOutputParser()
        
        try:
            async for chunk in chain.astream(inputs):
                if chunk:
                    # Add padding to force browser streaming (minimum ~1KB)
                    padding = " " * (1024 - len(chunk) - 100) if len(chunk) < 924 else ""
                    yield f"data: {json.dumps({'type': 'answer', 'content': chunk})}\n\n{padding}\n\n"
            
            synthesis_time = time.time() - synthesis_start
            total_time = time.time() - total_start
            
            yield f"data: {json.dumps({'type': 'done', 'synthesis_time': synthesis_time, 'total_time': total_time})}\n\n"
            
        except Exception as e:
            logger.error(f"Error during streaming synthesis: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    def update_configuration(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        """Update LLM or embedding configuration."""
        if llm_provider or llm_model or temperature is not None:
            logger.info(f"Updating LLM configuration")
            self.llm = LLMFactory.create_llm(
                provider=llm_provider,
                model=llm_model
            )
        
        if embedding_provider or embedding_model:
            logger.info(f"Updating embedding configuration")
            self.embeddings = EmbeddingFactory.create_embeddings(
                provider=embedding_provider,
                model=embedding_model
            )