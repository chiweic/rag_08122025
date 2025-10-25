"""
Enhanced RAG Pipeline with Multi-Collection Support
Handles retrieval from multiple collections and synthesis
"""

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import asyncio

from vector_store_v2 import MultiCollectionVectorStore, SearchConfig
from llm_factory import LLMFactory, EmbeddingFactory

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """Configuration for RAG pipeline"""
    text_limit: int = 3
    audio_limit: int = 1
    event_limit: int = 1
    similarity_threshold: float = 0.3
    temperature: float = 0.7
    max_tokens: int = 1000
    include_sources: bool = True
    stream: bool = False


class MultiCollectionRAGPipeline:
    """RAG Pipeline with multi-collection support"""
    
    def __init__(
        self,
        vector_store: MultiCollectionVectorStore,
        llm_factory: Optional[LLMFactory] = None,
        embedding_factory: Optional[EmbeddingFactory] = None
    ):
        self.vector_store = vector_store
        self.llm_factory = llm_factory or LLMFactory()
        self.embedding_factory = embedding_factory or EmbeddingFactory()
        
        # Initialize models
        self.llm = self.llm_factory.create_llm()
        self.embeddings = self.embedding_factory.create_embeddings()
    
    def retrieve(
        self,
        question: str,
        config: RAGConfig
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], float]:
        """Retrieve relevant chunks from multiple collections"""
        start_time = time.time()
        
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(question)
        
        # Configure search
        search_config = SearchConfig(
            text_limit=config.text_limit,
            audio_limit=config.audio_limit,
            event_limit=config.event_limit,
            similarity_threshold=config.similarity_threshold
        )
        
        # Search across collections
        results = self.vector_store.multi_collection_search(
            query_embedding,
            search_config
        )
        
        retrieval_time = time.time() - start_time
        logger.info(f"Retrieved {sum(len(r) for r in results.values())} chunks in {retrieval_time:.2f}s")
        
        return results, retrieval_time
    
    def format_context(self, results: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format retrieved chunks into context for LLM"""
        context_parts = []
        
        # Format text chunks
        if 'text' in results and results['text']:
            context_parts.append("【文本參考 Text References】")
            for i, chunk in enumerate(results['text'], 1):
                text = chunk.get('text', '')
                source = chunk.get('metadata', {}).get('source', 'Unknown')
                context_parts.append(f"{i}. {text[:500]}...")
                context_parts.append(f"   來源: {source}\n")
        
        # Format audio chunks
        if 'audio' in results and results['audio']:
            context_parts.append("【音頻參考 Audio References】")
            for i, chunk in enumerate(results['audio'], 1):
                text = chunk.get('text', '')
                title = chunk.get('audio_title', 'Unknown Audio')
                speaker = chunk.get('speaker', '聖嚴法師')
                context_parts.append(f"{i}. [{speaker} - {title}]")
                context_parts.append(f"   {text[:400]}...")
                context_parts.append("")
        
        # Format event chunks
        if 'event' in results and results['event']:
            context_parts.append("【活動參考 Event References】")
            for i, chunk in enumerate(results['event'], 1):
                text = chunk.get('text', '')
                title = chunk.get('title', 'Unknown Event')
                context_parts.append(f"{i}. {title}")
                context_parts.append(f"   {text[:300]}...")
                context_parts.append("")
        
        return "\n".join(context_parts)
    
    def format_sources(self, results: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Format sources for API response"""
        sources = []
        
        # Process text sources
        for chunk in results.get('text', []):
            source = {
                'type': 'text',
                'content': chunk.get('text', ''),
                'score': chunk.get('score', 0),
                'metadata': chunk.get('metadata', {})
            }
            # Ensure metadata has source_type
            source['metadata']['source_type'] = 'text'
            sources.append(source)
        
        # Process audio sources
        for chunk in results.get('audio', []):
            source = {
                'type': 'audio',
                'content': chunk.get('text', ''),
                'score': chunk.get('score', 0),
                'metadata': {
                    'source_type': 'audio',
                    'audio_title': chunk.get('audio_title', ''),
                    'audio_url': chunk.get('audio_url', ''),
                    'speaker': chunk.get('speaker', '聖嚴法師'),
                    'section': chunk.get('section', ''),
                    'timestamp_start': chunk.get('timestamp_start', ''),
                    'timestamp_end': chunk.get('timestamp_end', ''),
                    **chunk.get('metadata', {})
                }
            }
            sources.append(source)
        
        # Process event sources
        for chunk in results.get('event', []):
            source = {
                'type': 'event',
                'content': chunk.get('text', ''),
                'score': chunk.get('score', 0),
                'metadata': {
                    'source_type': 'event',
                    'event_title': chunk.get('title', ''),
                    'event_date': chunk.get('date', ''),
                    'event_location': chunk.get('location', ''),
                    **chunk.get('metadata', {})
                }
            }
            sources.append(source)
        
        # Sort by score
        sources.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return sources
    
    def synthesize(
        self,
        question: str,
        context: str,
        config: RAGConfig
    ) -> Tuple[str, float]:
        """Synthesize answer from context"""
        start_time = time.time()
        
        # Build prompt
        prompt = f"""你是一位專業的佛教導師助手，請根據以下參考資料回答問題。

重要：請始終使用繁體中文回答，無論問題使用什麼語言。

問題：{question}

參考資料：
{context}

請提供準確、有幫助的回答。如果參考資料中包含音頻或活動信息，請適當引用。
如果參考資料不足以回答問題，請誠實說明。

回答："""

        # Generate response
        try:
            response = self.llm.invoke(
                prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            
            if hasattr(response, 'content'):
                answer = response.content
            else:
                answer = str(response)
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            answer = "抱歉，生成回答時出現錯誤。"
        
        synthesis_time = time.time() - start_time
        logger.info(f"Generated answer in {synthesis_time:.2f}s")
        
        return answer, synthesis_time
    
    def query(
        self,
        question: str,
        config: Optional[RAGConfig] = None
    ) -> Dict[str, Any]:
        """Complete RAG query pipeline"""
        if config is None:
            config = RAGConfig()
        
        total_start = time.time()
        
        # Retrieve relevant chunks
        results, retrieval_time = self.retrieve(question, config)
        
        # Format context
        context = self.format_context(results)
        
        # Synthesize answer
        answer, synthesis_time = self.synthesize(question, context, config)
        
        # Prepare response
        response = {
            'answer': answer,
            'computation_time': time.time() - total_start,
            'retrieval_time': retrieval_time,
            'synthesis_time': synthesis_time,
            'chunks_retrieved': {
                'text': len(results.get('text', [])),
                'audio': len(results.get('audio', [])),
                'event': len(results.get('event', []))
            }
        }
        
        # Add sources if requested
        if config.include_sources:
            response['sources'] = self.format_sources(results)
        
        return response
    
    async def query_stream(
        self,
        question: str,
        config: Optional[RAGConfig] = None
    ):
        """Streaming version of query pipeline"""
        if config is None:
            config = RAGConfig(stream=True)
        
        total_start = time.time()
        
        # Yield start event
        yield {
            'type': 'start',
            'timestamp': time.time()
        }
        
        # Retrieve relevant chunks
        results, retrieval_time = self.retrieve(question, config)
        
        # Yield sources event
        yield {
            'type': 'sources',
            'sources': self.format_sources(results),
            'retrieval_time': retrieval_time,
            'chunks_retrieved': {
                'text': len(results.get('text', [])),
                'audio': len(results.get('audio', [])),
                'event': len(results.get('event', []))
            }
        }
        
        # Format context
        context = self.format_context(results)
        
        # Build prompt
        prompt = f"""你是一位專業的佛教導師助手，請根據以下參考資料回答問題。

重要：請始終使用繁體中文回答，無論問題使用什麼語言。

問題：{question}

參考資料：
{context}

請提供準確、有幫助的回答。如果參考資料中包含音頻或活動信息，請適當引用。
如果參考資料不足以回答問題，請誠實說明。

回答："""

        synthesis_start = time.time()
        
        # Stream response
        try:
            # For streaming, we'd need to use a streaming-capable LLM
            # For now, we'll simulate streaming by chunking the response
            response = self.llm.invoke(
                prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            
            if hasattr(response, 'content'):
                answer = response.content
            else:
                answer = str(response)
            
            # Simulate streaming by chunking
            chunk_size = 50
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i+chunk_size]
                yield {
                    'type': 'answer',
                    'content': chunk
                }
                await asyncio.sleep(0.01)  # Small delay to simulate streaming
                
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield {
                'type': 'error',
                'error': str(e)
            }
        
        # Yield completion event
        yield {
            'type': 'complete',
            'total_time': time.time() - total_start,
            'synthesis_time': time.time() - synthesis_start
        }