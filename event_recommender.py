import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import numpy as np
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventRecommender:
    def __init__(self, 
                 vector_store=None, 
                 embeddings=None,
                 events_file: str = "chunks/event_chunks.jsonl"):
        """
        Initialize the event recommender system.
        
        Args:
            vector_store: Vector store for semantic search (optional)
            embeddings: Embedding model (optional)
            events_file: Path to the events JSONL file
        """
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.events_file = Path(events_file)
        self.events = []
        self.events_by_id = {}
        
        # Load events from file
        self.load_events()
        
        # Initialize semantic search if embeddings provided
        if self.embeddings:
            self.build_search_index()
        
        logger.info(f"Event recommender initialized with {len(self.events)} events")
    
    def load_events(self):
        """Load events from JSONL file."""
        if not self.events_file.exists():
            logger.warning(f"Events file {self.events_file} not found")
            return
        
        with open(self.events_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        event_chunk = json.loads(line)
                        # Extract event information from the chunk
                        metadata = event_chunk.get('metadata', {})
                        event = {
                            'id': metadata.get('event_id', event_chunk.get('id')),
                            'title': metadata.get('event_title', ''),
                            'category': metadata.get('event_category', ''),
                            'location': metadata.get('event_location', ''),
                            'venue': metadata.get('venue', ''),
                            'time_period': metadata.get('event_time_period', ''),
                            'organizer': metadata.get('organizer', ''),
                            'target_audience': metadata.get('target_audience', ''),
                            'content': event_chunk.get('content', ''),
                            'url': metadata.get('event_url', ''),
                            'views': int(metadata.get('views', 0)),
                            'keyphrases': metadata.get('keyphrases', []),
                            'created_at': metadata.get('created_at', ''),
                            'chunk_id': event_chunk.get('id', '')
                        }
                        
                        # Parse dates from time_period
                        self.parse_event_dates(event)
                        
                        self.events.append(event)
                        self.events_by_id[event['id']] = event
                    except Exception as e:
                        logger.error(f"Error parsing event: {e}")
    
    def parse_event_dates(self, event):
        """Parse start and end dates from time_period string."""
        time_period = event.get('time_period', '')
        if '～' in time_period:
            parts = time_period.split('～')
            try:
                # Parse start date
                start_str = parts[0].strip()
                event['start_date'] = datetime.strptime(start_str, '%Y/%m/%d').date()
                
                # Parse end date
                if len(parts) > 1:
                    end_str = parts[1].strip()
                    event['end_date'] = datetime.strptime(end_str, '%Y/%m/%d').date()
                else:
                    event['end_date'] = event['start_date']
            except Exception as e:
                logger.debug(f"Could not parse dates for {event['title']}: {e}")
                event['start_date'] = None
                event['end_date'] = None
        else:
            # Single date event
            try:
                event['start_date'] = datetime.strptime(time_period.strip(), '%Y/%m/%d').date()
                event['end_date'] = event['start_date']
            except:
                event['start_date'] = None
                event['end_date'] = None
    
    def build_search_index(self):
        """Build semantic search index for events."""
        if not self.events:
            logger.warning("No events to index")
            return
        
        # Create searchable text for each event
        self.event_texts = []
        for event in self.events:
            search_text = f"{event['title']} {event['category']} {event['location']} {event['content']}"
            self.event_texts.append(search_text)
        
        # Generate embeddings for all events
        try:
            logger.info(f"Generating embeddings for {len(self.event_texts)} events...")
            self.event_embeddings = self.embeddings.embed_documents(self.event_texts)
            self.event_embeddings = np.array(self.event_embeddings)
            logger.info(f"Generated embeddings with shape {self.event_embeddings.shape}")
        except Exception as e:
            logger.error(f"Error generating event embeddings: {e}")
            self.event_embeddings = None
    
    def get_event_recommendations(self,
                                 user_query: str,
                                 top_k: int = 6,
                                 min_similarity: float = 0.1,
                                 upcoming_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get event recommendations based on user query.
        
        Args:
            user_query: User's search query
            top_k: Number of recommendations to return
            min_similarity: Minimum similarity threshold
            upcoming_only: Filter for upcoming events only
            
        Returns:
            List of recommended events with similarity scores
        """
        if not self.events:
            return []
        
        # Filter events if needed
        filtered_events = self.events
        if upcoming_only:
            today = date.today()
            filtered_events = [
                e for e in self.events 
                if e.get('end_date') and e['end_date'] >= today
            ]
        
        if not filtered_events:
            return []
        
        # If we have embeddings, use semantic search
        if self.embeddings and self.event_embeddings is not None:
            try:
                # Generate query embedding
                query_embedding = self.embeddings.embed_query(user_query)
                query_embedding = np.array(query_embedding)
                
                # Calculate similarities
                similarities = np.dot(self.event_embeddings, query_embedding)
                
                # Get indices of filtered events
                filtered_indices = [self.events.index(e) for e in filtered_events]
                
                # Get scores for filtered events
                filtered_scores = [(i, similarities[i]) for i in filtered_indices]
                filtered_scores.sort(key=lambda x: x[1], reverse=True)
                
                # Get top k recommendations
                recommendations = []
                for idx, score in filtered_scores[:top_k]:
                    if score >= min_similarity:
                        event = self.events[idx].copy()
                        event['similarity_score'] = float(score)
                        event['relevance'] = 'high' if score > 0.4 else 'medium' if score > 0.2 else 'low'
                        recommendations.append(event)
                
                return recommendations
                
            except Exception as e:
                logger.error(f"Error in semantic search: {e}")
                # Fall back to keyword search
        
        # Fallback: keyword-based search
        return self.keyword_search(user_query, filtered_events, top_k)
    
    def keyword_search(self, query: str, events: List[Dict], top_k: int) -> List[Dict[str, Any]]:
        """Simple keyword-based event search."""
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        scored_events = []
        for event in events:
            score = 0
            search_text = f"{event['title']} {event['category']} {event['location']} {event['content']}".lower()
            
            # Count matching terms
            for term in query_terms:
                if term in search_text:
                    score += search_text.count(term)
            
            if score > 0:
                event_copy = event.copy()
                event_copy['similarity_score'] = score / len(query_terms)  # Normalize
                event_copy['relevance'] = 'medium'
                scored_events.append(event_copy)
        
        # Sort by score and return top k
        scored_events.sort(key=lambda x: x['similarity_score'], reverse=True)
        return scored_events[:top_k]
    
    def get_upcoming_events(self, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Get upcoming events sorted by start date.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of upcoming events
        """
        today = date.today()
        
        # Filter for upcoming events (events that haven't ended yet)
        upcoming = [
            e for e in self.events 
            if e.get('end_date') and e['end_date'] >= today
        ]
        
        # Sort by start date
        upcoming.sort(key=lambda x: x['start_date'])
        
        # Return limited results
        results = []
        for event in upcoming[:limit]:
            event_copy = event.copy()
            # Format dates for display
            if event_copy.get('start_date'):
                event_copy['start_date'] = event_copy['start_date'].isoformat()
            if event_copy.get('end_date'):
                event_copy['end_date'] = event_copy['end_date'].isoformat()
            results.append(event_copy)
        
        return results
    
    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by ID."""
        event = self.events_by_id.get(event_id)
        if event:
            event_copy = event.copy()
            # Format dates for display
            if event_copy.get('start_date'):
                event_copy['start_date'] = event_copy['start_date'].isoformat()
            if event_copy.get('end_date'):
                event_copy['end_date'] = event_copy['end_date'].isoformat()
            return event_copy
        return None
    
    def get_events_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get events filtered by category."""
        matching_events = [
            e for e in self.events 
            if category.lower() in e.get('category', '').lower()
        ]
        
        # Sort by views (popularity)
        matching_events.sort(key=lambda x: x.get('views', 0), reverse=True)
        
        results = []
        for event in matching_events[:limit]:
            event_copy = event.copy()
            # Format dates for display
            if event_copy.get('start_date'):
                event_copy['start_date'] = event_copy['start_date'].isoformat()
            if event_copy.get('end_date'):
                event_copy['end_date'] = event_copy['end_date'].isoformat()
            results.append(event_copy)
        
        return results