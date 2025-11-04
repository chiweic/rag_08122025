import json
import logging
from typing import List, Dict, Any, Optional
import re
import jieba
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class QueryRecommender:
    """Query recommendation system based on FAQ similarity using Qdrant."""

    def __init__(self, vector_store=None, embeddings=None, faq_collection_name: str = "ddm_faq"):
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.faq_collection_name = faq_collection_name

        # Create separate vector store for FAQ collection
        if vector_store:
            from vector_store import QdrantVectorStore
            from config import settings
            self.faq_vector_store = QdrantVectorStore(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                collection_name=faq_collection_name
            )

            # Verify FAQ collection exists
            try:
                collection_info = self.faq_vector_store.get_collection_info()
                if collection_info:
                    logger.info(f"Query recommender initialized with FAQ collection '{faq_collection_name}' ({collection_info['points_count']} questions)")
                else:
                    logger.warning(f"FAQ collection '{faq_collection_name}' not found. Please run init_faq_collection.py first.")
                    self.faq_vector_store = None
            except Exception as e:
                logger.warning(f"FAQ collection '{faq_collection_name}' not available: {e}")
                self.faq_vector_store = None
        else:
            logger.warning("No vector store provided, FAQ recommendations will not be available")
            self.faq_vector_store = None

    def _load_faq_questions(self, faq_path: str):
        """Load FAQ questions from JSON file."""
        try:
            faq_file = Path(faq_path)
            if not faq_file.exists():
                logger.warning(f"FAQ file not found: {faq_path}")
                return

            with open(faq_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.faq_questions = data.get('questions', [])

            logger.info(f"Loaded {len(self.faq_questions)} FAQ questions from {faq_path}")
        except Exception as e:
            logger.error(f"Error loading FAQ questions: {e}")
            self.faq_questions = []

    def _generate_faq_embeddings(self):
        """Generate embeddings for all FAQ questions."""
        try:
            if not self.faq_questions:
                logger.warning("No FAQ questions to generate embeddings for")
                return

            logger.info(f"Generating embeddings for {len(self.faq_questions)} FAQ questions...")

            # Generate embeddings in batch
            self.faq_embeddings = []
            batch_size = 100

            for i in range(0, len(self.faq_questions), batch_size):
                batch = self.faq_questions[i:i + batch_size]
                batch_embeddings = self.embeddings.embed_documents(batch)
                self.faq_embeddings.extend(batch_embeddings)

                if (i + batch_size) % 500 == 0:
                    logger.info(f"Generated embeddings for {i + batch_size}/{len(self.faq_questions)} questions")

            # Convert to numpy array for faster similarity computation
            self.faq_embeddings = np.array(self.faq_embeddings)
            logger.info(f"Generated embeddings with shape: {self.faq_embeddings.shape}")

        except Exception as e:
            logger.error(f"Error generating FAQ embeddings: {e}")
            self.faq_embeddings = None

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
        """Get related queries based on FAQ similarity using Qdrant vector search."""
        if not self.faq_vector_store:
            logger.warning("FAQ vector store not available")
            return []

        if not self.embeddings:
            logger.warning("Embeddings not available")
            return []

        try:
            # Generate embedding for user query
            query_embedding = self.embeddings.embed_query(user_query)

            # Search for similar FAQ questions in Qdrant
            similar_faqs = self.faq_vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k * 2,  # Get more candidates to filter
                filter_dict=None
            )

            # Convert to related questions format
            related_questions = []

            for faq in similar_faqs:
                if len(related_questions) >= top_k:
                    break

                similarity_score = faq.get('score', 0)
                question_text = faq.get('text', '')

                # Skip if below threshold or exact match
                if similarity_score < min_similarity or question_text == user_query:
                    continue

                related_questions.append({
                    'text': question_text,
                    'similarity_score': float(similarity_score),
                    'reason': '相關問題'
                })

            logger.info(f"Found {len(related_questions)} related FAQ questions for query: {user_query}")
            return related_questions

        except Exception as e:
            logger.error(f"Error getting related queries from FAQ collection: {e}")
            return []

    def _keyword_filter(self, user_query: str, max_candidates: int = 1000) -> List[str]:
        """Filter FAQ questions by keyword matching for efficiency."""
        try:
            # Extract keywords from user query using jieba
            query_words = set(jieba.cut(user_query))
            query_words = {w for w in query_words if len(w) > 1}  # Filter single characters

            if not query_words:
                return []

            # Score each FAQ question by keyword overlap
            scored_questions = []
            for question in self.faq_questions:
                question_words = set(jieba.cut(question))
                overlap = len(query_words & question_words)
                if overlap > 0:
                    scored_questions.append((question, overlap))

            # Sort by overlap score and return top candidates
            scored_questions.sort(key=lambda x: x[1], reverse=True)
            return [q for q, _ in scored_questions[:max_candidates]]

        except Exception as e:
            logger.error(f"Error in keyword filtering: {e}")
            return []

    def _get_fallback_queries(self, user_query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Return random FAQ questions as fallback."""
        import random
        if not self.faq_questions:
            return []

        sample_size = min(top_k * 2, len(self.faq_questions))
        sampled = random.sample(self.faq_questions, sample_size)

        return [
            {
                'text': q,
                'similarity_score': 0.5,
                'reason': '推薦問題'
            }
            for q in sampled[:top_k]
        ]
    
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