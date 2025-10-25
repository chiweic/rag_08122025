import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import jieba
import re

logger = logging.getLogger(__name__)


class BookRecommender:
    """Book recommendation system based on semantic similarity."""
    
    def __init__(self, books_file: str = "ddm_books.json"):
        self.books_file = Path(books_file)
        self.books = []
        self.vectorizer = None
        self.book_vectors = None
        self.load_books()
        self.build_search_index()
    
    def load_books(self):
        """Load books from JSON file."""
        try:
            with open(self.books_file, 'r', encoding='utf-8') as f:
                self.books = json.load(f)
            logger.info(f"Loaded {len(self.books)} books from {self.books_file}")
        except Exception as e:
            logger.error(f"Error loading books: {e}")
            self.books = []
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess Chinese text for similarity comparison."""
        if not text:
            return ""
        
        # Clean text
        text = re.sub(r'[^\u4e00-\u9fff\w\s]', ' ', text)  # Keep Chinese chars and alphanumeric
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Segment Chinese text
        words = jieba.cut(text)
        return ' '.join(words)
    
    def build_search_index(self):
        """Build TF-IDF vectors for all books."""
        if not self.books:
            return
        
        # Combine title and content for each book
        book_texts = []
        for book in self.books:
            combined_text = f"{book.get('title', '')} {book.get('content_introduction', '')}"
            processed_text = self.preprocess_text(combined_text)
            book_texts.append(processed_text)
        
        # Build TF-IDF vectors
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words=None,  # No built-in stop words for Chinese
            ngram_range=(1, 2),
            min_df=2
        )
        
        try:
            self.book_vectors = self.vectorizer.fit_transform(book_texts)
            logger.info(f"Built search index with {self.book_vectors.shape[1]} features")
        except Exception as e:
            logger.error(f"Error building search index: {e}")
            self.book_vectors = None
    
    def get_recommendations(
        self, 
        query: str, 
        top_k: int = 5,
        min_similarity: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Get book recommendations based on query similarity."""
        if not self.books or self.book_vectors is None:
            return []
        
        try:
            # Preprocess query
            processed_query = self.preprocess_text(query)
            if not processed_query:
                return []
            
            # Transform query to vector
            query_vector = self.vectorizer.transform([processed_query])
            
            # Compute similarities
            similarities = cosine_similarity(query_vector, self.book_vectors).flatten()
            
            # Get top recommendations
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            recommendations = []
            for idx in top_indices:
                similarity_score = similarities[idx]
                if similarity_score >= min_similarity:
                    book = self.books[idx].copy()
                    book['similarity_score'] = float(similarity_score)
                    book['recommendation_reason'] = self._get_recommendation_reason(query, book)
                    recommendations.append(book)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []
    
    def _get_recommendation_reason(self, query: str, book: Dict[str, Any]) -> str:
        """Generate a reason for why this book is recommended."""
        title = book.get('title', '')
        content = book.get('content_introduction', '')
        
        # Simple keyword matching for explanation
        query_words = set(jieba.cut(query.lower()))
        title_words = set(jieba.cut(title.lower()))
        content_words = set(jieba.cut(content.lower()))
        
        common_title = query_words.intersection(title_words)
        common_content = query_words.intersection(content_words)
        
        if common_title:
            return f"標題包含相關關鍵詞：{', '.join(list(common_title)[:3])}"
        elif common_content:
            return f"內容涉及相關主題：{', '.join(list(common_content)[:3])}"
        else:
            return "基於語義相似性推薦"
    
    def get_book_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Get book details by ISBN."""
        for book in self.books:
            if book.get('isbn') == isbn:
                return book
        return None
    
    def get_books_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get books by category (based on title/content keywords)."""
        category_books = []
        category_lower = category.lower()
        
        for book in self.books:
            title = book.get('title', '').lower()
            content = book.get('content_introduction', '').lower()
            
            if category_lower in title or category_lower in content:
                category_books.append(book)
                if len(category_books) >= limit:
                    break
        
        return category_books
    
    def get_random_recommendations(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get random book recommendations."""
        if not self.books:
            return []
        
        import random
        return random.sample(self.books, min(count, len(self.books)))