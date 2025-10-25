#!/usr/bin/env python3
"""
Script to reorganize existing chunks into type-specific files
"""

import json
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reorganize_chunks(chunks_dir: str = "chunks"):
    """Reorganize existing chunks into type-specific files"""
    chunks_path = Path(chunks_dir)
    
    text_chunks = []
    audio_chunks = []
    event_chunks = []
    
    # Statistics
    stats = defaultdict(int)
    
    # Process all existing JSONL files
    for file_path in chunks_path.glob("*.jsonl"):
        # Skip if already organized
        if file_path.name in ["text_chunks.jsonl", "audio_chunks.jsonl", "event_chunks.jsonl"]:
            logger.info(f"Skipping already organized file: {file_path.name}")
            continue
        
        logger.info(f"Processing {file_path.name}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                    
                try:
                    chunk = json.loads(line)
                    
                    # Determine chunk type
                    chunk_id = chunk.get('id', '')
                    metadata = chunk.get('metadata', {})
                    source_type = metadata.get('source_type', '')
                    
                    # Categorize chunk
                    if source_type == 'audio' or 'audio_chunk' in chunk_id:
                        audio_chunks.append(chunk)
                        stats['audio'] += 1
                    elif source_type == 'event' or 'event' in chunk_id.lower() or 'events_' in file_path.name:
                        # Ensure event chunks have proper metadata
                        if 'source_type' not in metadata:
                            metadata['source_type'] = 'event'
                        event_chunks.append(chunk)
                        stats['event'] += 1
                    else:
                        # Default to text chunk
                        if 'source_type' not in metadata:
                            metadata['source_type'] = 'text'
                        text_chunks.append(chunk)
                        stats['text'] += 1
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing line {line_num} in {file_path.name}: {e}")
                except Exception as e:
                    logger.error(f"Error processing line {line_num} in {file_path.name}: {e}")
    
    # Write organized chunks
    def write_chunks(chunks, filename):
        if chunks:
            output_path = chunks_path / filename
            logger.info(f"Writing {len(chunks)} chunks to {filename}")
            with open(output_path, 'w', encoding='utf-8') as f:
                for chunk in chunks:
                    f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
            return True
        else:
            logger.warning(f"No chunks to write for {filename}")
            return False
    
    # Write files
    results = {
        'text': write_chunks(text_chunks, "text_chunks.jsonl"),
        'audio': write_chunks(audio_chunks, "audio_chunks.jsonl"),
        'event': write_chunks(event_chunks, "event_chunks.jsonl")
    }
    
    # Print summary
    print("\n" + "="*50)
    print("Chunk Reorganization Complete!")
    print("="*50)
    print(f"\nChunks organized:")
    print(f"  Text chunks:  {stats['text']:,}")
    print(f"  Audio chunks: {stats['audio']:,}")
    print(f"  Event chunks: {stats['event']:,}")
    print(f"  Total:        {sum(stats.values()):,}")
    
    print(f"\nFiles created:")
    for chunk_type, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {chunk_type}_chunks.jsonl")
    
    # Verify files
    print(f"\nVerifying files:")
    for filename in ["text_chunks.jsonl", "audio_chunks.jsonl", "event_chunks.jsonl"]:
        file_path = chunks_path / filename
        if file_path.exists():
            line_count = sum(1 for _ in open(file_path, 'r'))
            print(f"  ✓ {filename}: {line_count:,} chunks")
        else:
            print(f"  ✗ {filename}: Not found")
    
    return stats


if __name__ == "__main__":
    reorganize_chunks()