#!/usr/bin/env python3
"""
Convert raw events.json to structured event_chunks.jsonl
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_keyphrases(text: str, max_phrases: int = 5) -> List[str]:
    """Extract key phrases from text."""
    keywords = []
    
    # Common Buddhist terms and event-related terms to look for
    event_terms = [
        '禪修', '靜坐', '念佛', '淨土', '菩薩', '佛法', '修行', '智慧', '慈悲',
        '解脫', '覺悟', '三寶', '因果', '業力', '輪迴', '涅槃', '般若',
        '空性', '中道', '八正道', '四聖諦', '十二因緣', '六度', '布施',
        '持戒', '忍辱', '精進', '禪定', '般若', '迴向', '發願', '懺悔',
        '共修', '法會', '講座', '課程', '訓練', '體驗', '學習', '讀書會',
        '青年', '初級', '中級', '高級', '精進', '基礎', '進階'
    ]
    
    for term in event_terms:
        if term in text:
            keywords.append(term)
            if len(keywords) >= max_phrases:
                break
    
    return keywords


def create_event_chunk(event: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a single event to chunk format"""
    
    # Generate unique chunk ID
    chunk_id = hashlib.md5(
        f"event_{event['id']}_{event['title']}".encode()
    ).hexdigest()
    
    # Create header
    header = f"{event['title']} - {event['category']}"
    
    # Create content by combining all relevant information
    content_parts = [
        f"活動名稱：{event['title']}",
        f"時間：{event['time_period']}",
        f"地點：{event['location']}",
        f"類別：{event['category']}"
    ]
    
    # Add details if available
    details = event.get('details', {})
    if details:
        if details.get('organizer'):
            content_parts.append(f"主辦單位：{details['organizer']}")
        if details.get('target_audience'):
            content_parts.append(f"對象：{details['target_audience']}")
        if details.get('venue'):
            content_parts.append(f"詳細地點：{details['venue']}")
        if details.get('content'):
            content_parts.append(f"內容介紹：{details['content']}")
    
    content = '\n'.join(content_parts)
    
    # Extract keyphrases from title and content
    full_text = f"{event['title']} {content}"
    keyphrases = extract_keyphrases(full_text)
    
    # Create metadata
    metadata = {
        'source_type': 'event',
        'event_id': event['id'],
        'event_title': event['title'],
        'event_category': event['category'],
        'event_location': event['location'],
        'event_time_period': event['time_period'],
        'event_url': event['url'],
        'source': event['url'],
        'category': 'event',
        'keyphrases': keyphrases,
        'created_at': datetime.now().isoformat(),
        'organizer': details.get('organizer', ''),
        'target_audience': details.get('target_audience', ''),
        'venue': details.get('venue', ''),
        'views': event.get('views', ''),
        'language': event.get('language', 'zh-TW')
    }
    
    # Create chunk
    chunk = {
        'id': f"event_chunk_{chunk_id}",
        'header': header,
        'content': content,
        'metadata': metadata
    }
    
    return chunk


def convert_events_to_chunks(
    input_file: str = "events.json",
    output_file: str = "chunks/event_chunks.jsonl"
):
    """Convert events.json to event_chunks.jsonl"""
    
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(exist_ok=True)
    
    # Load events
    logger.info(f"Loading events from {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            events = json.load(f)
    except Exception as e:
        logger.error(f"Error loading {input_path}: {e}")
        return
    
    logger.info(f"Found {len(events)} events")
    
    # Convert events to chunks
    chunks = []
    categories = {}
    locations = {}
    
    for event in events:
        try:
            chunk = create_event_chunk(event)
            chunks.append(chunk)
            
            # Track statistics
            category = event.get('category', 'Unknown')
            categories[category] = categories.get(category, 0) + 1
            
            location = event.get('location', 'Unknown')
            locations[location] = locations.get(location, 0) + 1
            
        except Exception as e:
            logger.error(f"Error processing event {event.get('id', 'Unknown')}: {e}")
    
    # Write chunks to JSONL file
    logger.info(f"Writing {len(chunks)} chunks to {output_path}")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"Error writing to {output_path}: {e}")
        return
    
    # Print statistics
    print("\n" + "="*50)
    print("Event Conversion Complete!")
    print("="*50)
    print(f"Converted {len(chunks)} events to chunks")
    print(f"Output file: {output_path}")
    
    print(f"\nEvents by category:")
    for category, count in sorted(categories.items()):
        print(f"  {category}: {count}")
    
    print(f"\nTop locations:")
    for location, count in sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {location}: {count}")
    
    # Verify output file
    with open(output_path, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    print(f"\nVerification: {line_count} lines written to {output_path}")
    
    return len(chunks)


if __name__ == "__main__":
    convert_events_to_chunks()