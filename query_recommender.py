import json
import logging
from typing import List, Dict, Any, Optional
import re
import jieba

logger = logging.getLogger(__name__)


class QueryRecommender:
    """Query recommendation system based on vector store similarity."""
    
    def __init__(self, vector_store=None, embeddings=None):
        self.vector_store = vector_store
        self.embeddings = embeddings
        logger.info("Query recommender initialized with vector store")
    
    def load_query_bank(self):
        """Load predefined query bank with Buddhist questions."""
        self.query_bank = [
            # Basic Buddhism
            {"text": "什麼是佛教？", "category": "basic", "popularity": 10},
            {"text": "佛教的核心教義是什麼？", "category": "basic", "popularity": 9},
            {"text": "如何開始學佛？", "category": "basic", "popularity": 8},
            {"text": "佛教與其他宗教有什麼不同？", "category": "basic", "popularity": 7},
            {"text": "什麼是三寶？", "category": "basic", "popularity": 8},
            {"text": "什麼是四聖諦？", "category": "basic", "popularity": 9},
            {"text": "什麼是八正道？", "category": "basic", "popularity": 8},
            
            # Meditation and Practice
            {"text": "如何開始禪修？", "category": "meditation", "popularity": 10},
            {"text": "禪修有什麼好處？", "category": "meditation", "popularity": 9},
            {"text": "禪修時應該注意什麼？", "category": "meditation", "popularity": 8},
            {"text": "什麼是正念？", "category": "meditation", "popularity": 9},
            {"text": "如何在日常生活中修行？", "category": "practice", "popularity": 8},
            {"text": "念佛的方法和功德是什麼？", "category": "practice", "popularity": 7},
            {"text": "持咒有什麼作用？", "category": "practice", "popularity": 6},
            {"text": "如何培養慈悲心？", "category": "practice", "popularity": 8},
            
            # Philosophy and Concepts
            {"text": "什麼是空性？", "category": "philosophy", "popularity": 7},
            {"text": "因果法則是如何運作的？", "category": "philosophy", "popularity": 8},
            {"text": "什麼是輪迴？", "category": "philosophy", "popularity": 8},
            {"text": "如何理解無我？", "category": "philosophy", "popularity": 6},
            {"text": "什麼是菩提心？", "category": "philosophy", "popularity": 7},
            {"text": "什麼是涅槃？", "category": "philosophy", "popularity": 7},
            {"text": "佛性是什麼意思？", "category": "philosophy", "popularity": 6},
            
            # Sheng Yen Specific
            {"text": "聖嚴法師的主要教導是什麼？", "category": "shengyen", "popularity": 8},
            {"text": "聖嚴法師如何解釋禪修？", "category": "shengyen", "popularity": 7},
            {"text": "聖嚴法師對現代生活的建議？", "category": "shengyen", "popularity": 7},
            {"text": "聖嚴法師的著作有哪些？", "category": "shengyen", "popularity": 6},
            {"text": "聖嚴法師如何看待人生煩惱？", "category": "shengyen", "popularity": 7},
            
            # Daily Life Buddhism
            {"text": "如何將佛法應用到工作中？", "category": "daily", "popularity": 8},
            {"text": "佛教徒應該如何處理人際關係？", "category": "daily", "popularity": 8},
            {"text": "面對困難時如何用佛法思考？", "category": "daily", "popularity": 9},
            {"text": "如何用佛法處理情緒問題？", "category": "daily", "popularity": 9},
            {"text": "佛教如何看待死亡？", "category": "daily", "popularity": 7},
            {"text": "佛教徒應該如何飲食？", "category": "daily", "popularity": 5},
            
            # Study and Learning
            {"text": "應該如何讀佛經？", "category": "study", "popularity": 6},
            {"text": "初學者應該先學什麼經典？", "category": "study", "popularity": 7},
            {"text": "如何找到適合的佛法老師？", "category": "study", "popularity": 6},
            {"text": "學佛需要多長時間？", "category": "study", "popularity": 5},
            {"text": "如何驗證自己的修行進步？", "category": "study", "popularity": 6}
        ]
        
        logger.info(f"Loaded {len(self.query_bank)} queries into query bank")
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess Chinese text for similarity comparison."""
        if not text:
            return ""
        
        # Clean text
        text = re.sub(r'[^\u4e00-\u9fff\w\s？！。，]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Segment Chinese text
        words = jieba.cut(text)
        return ' '.join(words)
    
    def build_query_index(self):
        """Build TF-IDF vectors for all queries."""
        if not self.query_bank:
            return
        
        # Preprocess all queries
        query_texts = []
        for query in self.query_bank:
            processed_text = self.preprocess_text(query['text'])
            query_texts.append(processed_text)
        
        # Build TF-IDF vectors
        self.vectorizer = TfidfVectorizer(
            max_features=3000,
            stop_words=None,
            ngram_range=(1, 2),
            min_df=1
        )
        
        try:
            self.query_vectors = self.vectorizer.fit_transform(query_texts)
            logger.info(f"Built query index with {self.query_vectors.shape[1]} features")
        except Exception as e:
            logger.error(f"Error building query index: {e}")
            self.query_vectors = None
    
    def get_related_queries(
        self, 
        user_query: str, 
        top_k: int = 3,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Get related queries based on vector store similarity."""
        if not self.vector_store or not self.embeddings:
            logger.warning("Vector store or embeddings not available")
            return []
        
        try:
            # Generate embedding for user query
            query_embedding = self.embeddings.embed_query(user_query)
            
            # Search for similar chunks in vector store
            similar_chunks = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k * 2,  # Get more candidates to filter from
                filter_dict=None
            )
            
            # Convert chunk titles to related questions
            related_questions = []
            seen_titles = set()
            
            for chunk in similar_chunks:
                if len(related_questions) >= top_k:
                    break
                    
                # Get chunk metadata
                metadata = chunk.get('metadata', {})
                title = metadata.get('title', '').strip()
                similarity_score = chunk.get('score', 0)
                
                # Skip if no title, too low similarity, or already seen
                if (not title or 
                    similarity_score < min_similarity or 
                    title in seen_titles or
                    title == user_query):
                    continue
                
                related_questions.append({
                    'text': title,
                    'similarity_score': float(similarity_score),
                    'reason': '相關主題'
                })
                seen_titles.add(title)
            
            return related_questions[:top_k]
            
        except Exception as e:
            logger.error(f"Error getting related queries: {e}")
            return []
    
    def _get_recommendation_reason(self, user_query: str, recommended_query: Dict[str, Any]) -> str:
        """Generate a reason for why this query is recommended."""
        category_reasons = {
            "basic": "基礎概念",
            "meditation": "禪修相關", 
            "practice": "修行實踐",
            "philosophy": "佛學哲理",
            "shengyen": "聖嚴法師",
            "daily": "日常應用",
            "study": "學習方法"
        }
        
        category = recommended_query.get('category', 'basic')
        return category_reasons.get(category, "相關主題")
    
    def get_queries_by_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get queries by category."""
        category_queries = [q for q in self.query_bank if q.get('category') == category]
        category_queries.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        return category_queries[:limit]
    
    def get_popular_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most popular queries."""
        popular = sorted(self.query_bank, key=lambda x: x.get('popularity', 0), reverse=True)
        return popular[:limit]