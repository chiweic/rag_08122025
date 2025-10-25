#!/usr/bin/env python3
"""
Test script for the multi-collection RAG system
"""

import asyncio
import logging
from data_loader_v2 import MultiTypeDataLoader, ChunkTypes
from vector_store_v2 import MultiCollectionVectorStore, SearchConfig
from rag_pipeline_v2 import MultiCollectionRAGPipeline, RAGConfig
from llm_factory import EmbeddingFactory, LLMFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_data_loader():
    """Test the multi-type data loader"""
    print("="*50)
    print("Testing Multi-Type Data Loader")
    print("="*50)
    
    loader = MultiTypeDataLoader()
    loaded_data = loader.load_all_chunks()
    
    stats = loader.get_chunk_statistics(loaded_data)
    
    print(f"Total chunks loaded: {stats['total_chunks']}")
    print(f"By type:")
    for chunk_type, count in stats['by_type'].items():
        print(f"  {chunk_type}: {count}")
    
    # Test document preparation
    for chunk_type in ChunkTypes.all_types():
        chunks = loaded_data.get_by_type(chunk_type)
        if chunks:
            documents = loader.prepare_documents_for_vectordb(chunks[:2], chunk_type)
            print(f"\n{chunk_type.title()} sample document structure:")
            sample = documents[0]
            print(f"  ID: {sample['id']}")
            print(f"  Text length: {len(sample['text'])}")
            print(f"  Metadata keys: {list(sample['metadata'].keys())}")
            print(f"  Source type: {sample['metadata'].get('source_type', 'None')}")
    
    return loaded_data


async def test_vector_store(loaded_data):
    """Test the multi-collection vector store"""
    print("\n" + "="*50)
    print("Testing Multi-Collection Vector Store")
    print("="*50)
    
    # Initialize vector store
    vector_store = MultiCollectionVectorStore(
        url="http://localhost:6333",
        embedding_dim=768  # Use correct dimension for BAAI/bge-base-zh-v1.5
    )
    
    # Create collections
    print("Creating collections...")
    vector_store.create_all_collections(recreate=True)
    
    # Initialize embedding model
    embedding_factory = EmbeddingFactory()
    embeddings_model = embedding_factory.create_embeddings()
    
    # Load a small sample from each type for testing
    loader = MultiTypeDataLoader()
    
    for chunk_type in ChunkTypes.all_types():
        chunks = loaded_data.get_by_type(chunk_type)
        
        if not chunks:
            print(f"No {chunk_type} chunks found, skipping")
            continue
        
        # Take only first 10 chunks for testing
        test_chunks = chunks[:10]
        print(f"Testing {len(test_chunks)} {chunk_type} chunks...")
        
        # Prepare documents
        documents = loader.prepare_documents_for_vectordb(test_chunks, chunk_type)
        
        # Generate embeddings
        texts = [doc['text'] for doc in documents]
        embeddings_list = embeddings_model.embed_documents(texts)
        
        # Add to vector store
        vector_store.add_documents(
            collection_type=chunk_type,
            documents=documents,
            embeddings=embeddings_list
        )
    
    # Test search
    print("\nTesting search functionality...")
    query = "什麼是禪修"
    query_embedding = embeddings_model.embed_query(query)
    
    search_config = SearchConfig(
        text_limit=2,
        audio_limit=1,
        event_limit=1
    )
    
    results = vector_store.multi_collection_search(query_embedding, search_config)
    
    print(f"\nSearch results for '{query}':")
    for collection_type, hits in results.items():
        print(f"\n{collection_type.title()} results ({len(hits)}):")
        for i, hit in enumerate(hits, 1):
            score = hit.get('score', 0)
            text_preview = hit.get('text', '')[:100] + '...'
            print(f"  {i}. Score: {score:.3f}")
            print(f"     Preview: {text_preview}")
            
            # Show type-specific metadata
            if collection_type == 'audio':
                title = hit.get('audio_title', 'Unknown')
                speaker = hit.get('speaker', 'Unknown')
                print(f"     Audio: {title} by {speaker}")
            elif collection_type == 'event':
                title = hit.get('event_title', 'Unknown')
                category = hit.get('event_category', 'Unknown')
                print(f"     Event: {title} ({category})")
    
    return vector_store


async def test_rag_pipeline(vector_store):
    """Test the multi-collection RAG pipeline"""
    print("\n" + "="*50)
    print("Testing Multi-Collection RAG Pipeline")
    print("="*50)
    
    # Initialize RAG pipeline
    llm_factory = LLMFactory()
    embedding_factory = EmbeddingFactory()
    
    rag_pipeline = MultiCollectionRAGPipeline(
        vector_store=vector_store,
        llm_factory=llm_factory,
        embedding_factory=embedding_factory
    )
    
    # Test query
    query = "什麼是禪修？有什麼活動可以參加？"
    print(f"Testing query: {query}")
    
    config = RAGConfig(
        text_limit=2,
        audio_limit=1,
        event_limit=1,
        include_sources=True,
        temperature=0.7
    )
    
    print("Running query...")
    result = rag_pipeline.query(query, config)
    
    print(f"\nQuery Results:")
    print(f"Answer length: {len(result['answer'])} characters")
    print(f"Retrieval time: {result['retrieval_time']:.2f}s")
    print(f"Synthesis time: {result['synthesis_time']:.2f}s")
    print(f"Total time: {result['computation_time']:.2f}s")
    
    print(f"\nChunks retrieved:")
    for chunk_type, count in result['chunks_retrieved'].items():
        print(f"  {chunk_type}: {count}")
    
    print(f"\nSources found: {len(result.get('sources', []))}")
    
    # Show sample sources by type
    sources = result.get('sources', [])
    for source in sources[:3]:  # Show first 3 sources
        source_type = source.get('type', 'unknown')
        score = source.get('score', 0)
        print(f"\nSource ({source_type}, score: {score:.3f}):")
        
        if source_type == 'audio':
            metadata = source.get('metadata', {})
            title = metadata.get('audio_title', 'Unknown')
            speaker = metadata.get('speaker', 'Unknown')
            print(f"  Audio: {title} by {speaker}")
        elif source_type == 'event':
            metadata = source.get('metadata', {})
            title = metadata.get('event_title', 'Unknown')
            category = metadata.get('event_category', 'Unknown')
            print(f"  Event: {title} ({category})")
        else:
            print(f"  Text source")
        
        content_preview = source.get('content', '')[:150] + '...'
        print(f"  Preview: {content_preview}")
    
    print(f"\nGenerated Answer:")
    print("-" * 30)
    print(result['answer'][:500] + ('...' if len(result['answer']) > 500 else ''))
    
    return result


async def main():
    """Run all tests"""
    try:
        # Test data loading
        loaded_data = await test_data_loader()
        
        # Test vector store
        vector_store = await test_vector_store(loaded_data)
        
        # Test RAG pipeline
        result = await test_rag_pipeline(vector_store)
        
        print("\n" + "="*50)
        print("All Tests Completed Successfully!")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n✅ Multi-collection RAG system is working correctly!")
    else:
        print("\n❌ Tests failed. Please check the logs above.")