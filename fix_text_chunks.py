#!/usr/bin/env python3
"""
Fix text chunks to have proper IDs and metadata
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_text_chunks(
    input_file: str = "chunks/text_chunks.jsonl",
    output_file: str = "chunks/text_chunks_fixed.jsonl"
):
    """Fix text chunks to have consistent format"""
    
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    if not input_path.exists():
        logger.error(f"Input file {input_path} not found")
        return
    
    logger.info(f"Processing {input_path}")
    
    fixed_chunks = []
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            
            try:
                chunk = json.loads(line)
                
                # Get original ID and create new text-prefixed ID
                original_id = chunk.get('id', '')
                if original_id.startswith('chunk_'):
                    # Replace with text_chunk_ prefix
                    hash_part = original_id[6:]  # Remove 'chunk_' prefix
                    new_id = f"text_chunk_{hash_part}"
                else:
                    # Generate new hash if needed
                    content = chunk.get('content', '')
                    header = chunk.get('header', '')
                    hash_part = hashlib.md5(f"{header}_{content[:100]}".encode()).hexdigest()
                    new_id = f"text_chunk_{hash_part}"
                
                chunk['id'] = new_id
                
                # Ensure metadata exists and has proper source_type
                if 'metadata' not in chunk:
                    chunk['metadata'] = {}
                
                metadata = chunk['metadata']
                metadata['source_type'] = 'text'
                metadata['chunk_type'] = 'text'
                
                # Add created_at if not present
                if 'created_at' not in metadata:
                    metadata['created_at'] = datetime.now().isoformat()
                
                # Ensure category is set
                if 'category' not in metadata:
                    metadata['category'] = 'text'
                
                fixed_chunks.append(chunk)
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing line {line_num}: {e}")
            except Exception as e:
                logger.error(f"Error processing line {line_num}: {e}")
    
    # Write fixed chunks
    logger.info(f"Writing {len(fixed_chunks)} fixed chunks to {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for chunk in fixed_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
    
    logger.info(f"Fixed {len(fixed_chunks)} text chunks")
    
    # Replace original file
    if output_path.exists():
        logger.info(f"Replacing {input_path} with fixed version")
        output_path.replace(input_path)
    
    return len(fixed_chunks)


if __name__ == "__main__":
    count = fix_text_chunks()
    print(f"\nFixed {count} text chunks")
    
    # Verify the fix
    print("\nVerifying fix...")
    with open("chunks/text_chunks.jsonl", 'r') as f:
        first_chunk = json.loads(f.readline())
        print(f"Sample ID: {first_chunk['id']}")
        print(f"Source type: {first_chunk['metadata'].get('source_type', 'None')}")
        print(f"Category: {first_chunk['metadata'].get('category', 'None')}")