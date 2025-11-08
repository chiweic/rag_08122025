#!/usr/bin/env python3
"""
LLM 配置管理模塊
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class LLMProviderConfig:
    """LLM 供應商配置"""
    model_name: str
    base_url: str
    api_key: str
    max_tokens: int
    temperature: float
    timeout: int
    max_context_chars: int

class LLMConfigManager:
    """LLM 配置管理器"""
    
    def __init__(self):
        self.providers = {
            'deepseek': self._load_deepseek_config(),
            'openai': self._load_openai_config(),
            'local': self._load_local_config(),
            'dashscope': self._load_dashscope_config(),
            'gemini': self._load_gemini_config()
        }
        self.default_provider = os.getenv('CHUNKER_LLM_PROVIDER', 'deepseek')
    
    def _load_gemini_config(self) -> LLMProviderConfig:
        return LLMProviderConfig(
            model_name=os.getenv('GEMINI_MODEL', 'gemini-1.5-pro'),
            base_url=os.getenv('GEMINI_BASE_URL', 'https://gemini.api.google.com/v1'),
            api_key=os.getenv('GEMINI_API_KEY', ''),
            max_tokens=int(os.getenv('GEMINI_MAX_TOKENS', 4000)),
            temperature=float(os.getenv('GEMINI_TEMPERATURE', 0.1)),
            timeout=int(os.getenv('GEMINI_TIMEOUT', 120)),
            max_context_chars=int(os.getenv('GEMINI_MAX_CONTEXT_CHARS', 80000))
        )
    
    
    def _load_deepseek_config(self) -> LLMProviderConfig:
        return LLMProviderConfig(
            model_name=os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
            base_url=os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
            api_key=os.getenv('DEEPSEEK_API_KEY', ''),
            max_tokens=int(os.getenv('DEEPSEEK_MAX_TOKENS', 4000)),
            temperature=float(os.getenv('DEEPSEEK_TEMPERATURE', 0.1)),
            timeout=int(os.getenv('DEEPSEEK_TIMEOUT', 120)),
            max_context_chars=int(os.getenv('MAX_CONTEXT_CHARS', 80000))
        )
    
    def _load_dashscope_config(self) -> LLMProviderConfig:
        return LLMProviderConfig(
            model_name=os.getenv('DASHSCOPE_MODEL', 'deepseek-chat'),
            base_url=os.getenv('DASHSCOPE_BASE_URL', 'https://api.deepseek.com'),
            api_key=os.getenv('DASHSCOPE_API_KEY', ''),
            max_tokens=int(os.getenv('DASHSCOPE_MAX_TOKENS', 4000)),
            temperature=float(os.getenv('DASHSCOPE_TEMPERATURE', 0.1)),
            timeout=int(os.getenv('DASHSCOPE_TIMEOUT', 120)),
            max_context_chars=int(os.getenv('DASHSCOPE_MAX_CONTEXT_CHARS', 80000))
        )
    
    def _load_openai_config(self) -> LLMProviderConfig:
        return LLMProviderConfig(
            model_name=os.getenv('OPENAI_MODEL', 'gpt-4-turbo'),
            base_url=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
            api_key=os.getenv('OPENAI_API_KEY', ''),
            max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', 4000)),
            temperature=float(os.getenv('OPENAI_TEMPERATURE', 0.1)),
            timeout=int(os.getenv('OPENAI_TIMEOUT', 120)),
            max_context_chars=int(os.getenv('OPENAI_MAX_CONTEXT_CHARS', 80000))
        )
    
    def _load_local_config(self) -> LLMProviderConfig:
        return LLMProviderConfig(
            model_name=os.getenv('LOCAL_MODEL', 'llama2'),
            base_url=os.getenv('LOCAL_BASE_URL', 'http://localhost:8080/v1'),
            api_key=os.getenv('LOCAL_API_KEY', 'sk-no-key-required'),
            max_tokens=int(os.getenv('LOCAL_MAX_TOKENS', 2000)),
            temperature=float(os.getenv('LOCAL_TEMPERATURE', 0.3)),
            timeout=int(os.getenv('LOCAL_TIMEOUT', 60)),
            max_context_chars=int(os.getenv('LOCAL_MAX_CONTEXT_CHARS', 40000))
        )
    
    def get_provider_config(self, provider: Optional[str] = None) -> LLMProviderConfig:
        """獲取指定供應商的配置"""
        provider = provider or self.default_provider
        if provider not in self.providers:
            raise ValueError(f"不支持的 LLM 供應商: {provider}")
        return self.providers[provider]
    
    def get_available_providers(self) -> list:
        """獲取可用的供應商列表"""
        return list(self.providers.keys())
    
    def validate_config(self, provider: Optional[str] = None) -> bool:
        """驗證配置是否完整"""
        config = self.get_provider_config(provider)
        return all([
            config.model_name,
            config.base_url,
            config.api_key
        ])

# 全局配置實例
config_manager = LLMConfigManager()