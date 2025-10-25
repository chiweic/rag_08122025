"""
Embedding Configuration Manager
Tracks embedding model changes and manages collection recreation
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)

class EmbeddingConfigManager:
    """Manages embedding configuration and detects changes"""
    
    def __init__(self, config_file: str = "embedding_config.json"):
        self.config_file = Path(config_file)
        self.current_config = self._get_current_config()
    
    def _get_current_config(self) -> Dict[str, Any]:
        """Get current embedding configuration"""
        return {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "timestamp": None  # Will be set when saved
        }
    
    def load_saved_config(self) -> Optional[Dict[str, Any]]:
        """Load previously saved embedding configuration"""
        if not self.config_file.exists():
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load embedding config: {e}")
            return None
    
    def save_config(self, dimension: int) -> None:
        """Save current embedding configuration with dimension"""
        import time
        
        config = self.current_config.copy()
        config["dimension"] = dimension
        config["timestamp"] = time.time()
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved embedding config: {config}")
        except Exception as e:
            logger.error(f"Failed to save embedding config: {e}")
    
    def has_model_changed(self) -> bool:
        """Check if embedding model has changed since last initialization"""
        saved_config = self.load_saved_config()
        
        if saved_config is None:
            logger.info("No previous embedding config found")
            return True
        
        current = self.current_config
        
        # Check if provider or model changed
        if (saved_config.get("provider") != current["provider"] or 
            saved_config.get("model") != current["model"]):
            
            logger.info(f"Embedding model changed:")
            logger.info(f"  Previous: {saved_config.get('provider')}/{saved_config.get('model')}")
            logger.info(f"  Current: {current['provider']}/{current['model']}")
            return True
        
        return False
    
    def should_recreate_collections(self) -> bool:
        """Determine if collections should be recreated due to model change"""
        return self.has_model_changed()