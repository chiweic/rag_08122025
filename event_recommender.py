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
        """Build semantic search index for events using Qdrant."""
        if not self.events:
            logger.warning("No events to index")
            return

        # Skip embedding generation - we'll use vector_store.search() directly
        # Events are already in Qdrant with embeddings
        logger.info(f"Event recommender will use Qdrant vector store for {len(self.events)} events")
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
        
        # Use Qdrant vector store for semantic search
        if self.vector_store and self.embeddings:
            try:
                # First embed the query
                query_embedding = self.embeddings.embed_query(user_query)

                # Search Qdrant for events (filter by source_type=event)
                search_results = self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=top_k * 2,  # Get more results to filter
                    filter_dict={"source_type": "event"}
                )

                # Convert to event objects and filter by date if needed
                recommendations = []
                for result in search_results:
                    # Find the event in our events list by ID
                    metadata = result.get('metadata', {})
                    event_id = metadata.get('event_id')
                    if event_id and event_id in self.events_by_id:
                        event = self.events_by_id[event_id].copy()

                        # Check if upcoming only
                        if upcoming_only:
                            if not event.get('end_date') or event['end_date'] < date.today():
                                continue

                        # Add similarity score
                        score = result.get('score', 0)
                        if score >= min_similarity:
                            event['similarity_score'] = float(score)
                            event['relevance'] = 'high' if score > 0.7 else 'medium' if score > 0.5 else 'low'
                            recommendations.append(event)

                            if len(recommendations) >= top_k:
                                break

                return recommendations

            except Exception as e:
                logger.error(f"Error in Qdrant search: {e}")
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