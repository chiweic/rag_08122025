#!/usr/bin/env python3
"""
GPU Embedding Test Script
Tests GPU support for embedding models and provides troubleshooting info
"""

import torch
import logging
from sentence_transformers import SentenceTransformer
from langchain_community.embeddings import HuggingFaceEmbeddings
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pytorch_gpu():
    """Test basic PyTorch GPU functionality"""
    print("=== PyTorch GPU Test ===")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"CUDA version: {torch.version.cuda}")
    print(f"Number of GPUs: {torch.cuda.device_count()}")
    
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            print(f"GPU {i}: {props.name}")
            print(f"  - Compute capability: {props.major}.{props.minor}")
            print(f"  - Total memory: {props.total_memory / 1024**3:.1f} GB")
    
    # Test basic CUDA operations
    try:
        print("\nTesting basic CUDA operations...")
        x = torch.randn(10, 10)
        print(f"Created tensor on CPU: {x.device}")
        
        if torch.cuda.is_available():
            for gpu_id in range(torch.cuda.device_count()):
                try:
                    print(f"\nTesting GPU {gpu_id}...")
                    x_gpu = x.cuda(gpu_id)
                    y_gpu = x_gpu * 2
                    result = y_gpu.cpu()
                    print(f"✅ GPU {gpu_id} works correctly")
                except Exception as e:
                    print(f"❌ GPU {gpu_id} failed: {e}")
        else:
            print("No CUDA GPUs available")
            
    except Exception as e:
        print(f"❌ CUDA test failed: {e}")


def test_sentence_transformers_gpu():
    """Test SentenceTransformers with different GPU configurations"""
    print("\n=== SentenceTransformers GPU Test ===")
    
    model_name = "BAAI/bge-small-zh-v1.5"
    test_texts = ["这是一个测试", "test sentence", "another test"]
    
    # Test CPU
    print(f"\nTesting {model_name} on CPU...")
    try:
        start_time = time.time()
        model_cpu = SentenceTransformer(model_name, device='cpu')
        embeddings_cpu = model_cpu.encode(test_texts)
        cpu_time = time.time() - start_time
        print(f"✅ CPU embedding successful")
        print(f"   Shape: {embeddings_cpu.shape}")
        print(f"   Time: {cpu_time:.2f}s")
    except Exception as e:
        print(f"❌ CPU embedding failed: {e}")
    
    # Test each GPU
    if torch.cuda.is_available():
        for gpu_id in range(torch.cuda.device_count()):
            print(f"\nTesting {model_name} on GPU {gpu_id}...")
            try:
                start_time = time.time()
                model_gpu = SentenceTransformer(model_name, device=f'cuda:{gpu_id}')
                embeddings_gpu = model_gpu.encode(test_texts)
                gpu_time = time.time() - start_time
                print(f"✅ GPU {gpu_id} embedding successful")
                print(f"   Shape: {embeddings_gpu.shape}")
                print(f"   Time: {gpu_time:.2f}s")
                print(f"   Speedup vs CPU: {cpu_time/gpu_time:.1f}x" if 'cpu_time' in locals() else "N/A")
            except Exception as e:
                print(f"❌ GPU {gpu_id} embedding failed: {e}")


def test_langchain_huggingface_gpu():
    """Test LangChain HuggingFace embeddings with GPU"""
    print("\n=== LangChain HuggingFace GPU Test ===")
    
    model_name = "BAAI/bge-small-zh-v1.5"
    test_texts = ["这是一个测试", "test sentence"]
    
    # Test CPU
    print(f"\nTesting LangChain {model_name} on CPU...")
    try:
        start_time = time.time()
        embeddings_cpu = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        results_cpu = embeddings_cpu.embed_documents(test_texts)
        cpu_time = time.time() - start_time
        print(f"✅ LangChain CPU embedding successful")
        print(f"   Dimension: {len(results_cpu[0])}")
        print(f"   Time: {cpu_time:.2f}s")
    except Exception as e:
        print(f"❌ LangChain CPU embedding failed: {e}")
    
    # Test each GPU
    if torch.cuda.is_available():
        for gpu_id in range(torch.cuda.device_count()):
            print(f"\nTesting LangChain {model_name} on GPU {gpu_id}...")
            try:
                start_time = time.time()
                embeddings_gpu = HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={'device': f'cuda:{gpu_id}'},
                    encode_kwargs={'normalize_embeddings': True}
                )
                results_gpu = embeddings_gpu.embed_documents(test_texts)
                gpu_time = time.time() - start_time
                print(f"✅ LangChain GPU {gpu_id} embedding successful")
                print(f"   Dimension: {len(results_gpu[0])}")
                print(f"   Time: {gpu_time:.2f}s")
                print(f"   Speedup vs CPU: {cpu_time/gpu_time:.1f}x" if 'cpu_time' in locals() else "N/A")
            except Exception as e:
                print(f"❌ LangChain GPU {gpu_id} embedding failed: {e}")


def test_compatibility_solutions():
    """Test potential solutions for GPU compatibility issues"""
    print("\n=== Compatibility Solutions Test ===")
    
    if not torch.cuda.is_available():
        print("No CUDA available, skipping compatibility tests")
        return
    
    # Test with fallback mechanism
    print("\nTesting fallback mechanism...")
    
    def create_embeddings_with_fallback(model_name, preferred_device='cuda:0'):
        """Create embeddings with automatic fallback"""
        devices_to_try = [preferred_device, 'cuda:1', 'cuda', 'cpu']
        
        for device in devices_to_try:
            try:
                print(f"  Trying device: {device}")
                if device.startswith('cuda') and not torch.cuda.is_available():
                    continue
                
                # Quick test to see if device works
                if device.startswith('cuda'):
                    test_tensor = torch.randn(10).to(device)
                    _ = test_tensor * 2  # Simple operation
                
                embeddings = HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={'device': device},
                    encode_kwargs={'normalize_embeddings': True}
                )
                
                # Test with actual embedding
                test_result = embeddings.embed_query("test")
                print(f"  ✅ Success with device: {device}")
                return embeddings, device
                
            except Exception as e:
                print(f"  ❌ Failed with device {device}: {e}")
                continue
        
        raise Exception("All devices failed")
    
    try:
        embeddings, device = create_embeddings_with_fallback("BAAI/bge-small-zh-v1.5")
        print(f"✅ Fallback mechanism successful, using device: {device}")
    except Exception as e:
        print(f"❌ All fallback options failed: {e}")


def main():
    """Run all GPU tests"""
    print("GPU Embedding Support Test")
    print("=" * 50)
    
    test_pytorch_gpu()
    test_sentence_transformers_gpu()
    test_langchain_huggingface_gpu()
    test_compatibility_solutions()
    
    print("\n" + "=" * 50)
    print("Test complete!")


if __name__ == "__main__":
    main()