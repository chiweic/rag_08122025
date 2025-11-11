#!/usr/bin/env python3
"""
Podcast Generation Comparison Tool

This script compares two podcast generation approaches:
1. Structured Q&A-based approach (llm_podcast_generate.py)
2. Simple direct PDF approach (llm_podcast_generate_simple.py)

It generates podcasts using both methods and provides comparison metrics.

Usage:
    # Compare using Q&A JSON
    python compare_podcast_approaches.py --qa chunks/qa/05.01.pdf.qa.json

    # Compare using raw PDF (requires PDF path for approach 2)
    python compare_podcast_approaches.py --qa chunks/qa/05.01.pdf.qa.json --pdf books/05.01.pdf

Author: DDM RAG Team
Created: 2025-11-10
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def count_dialogue_turns(podcast_json: Dict[str, Any]) -> Dict[str, int]:
    """Count dialogue turns in podcast JSON."""
    opening_turns = len(podcast_json.get('opening', []))
    closing_turns = len(podcast_json.get('closing', []))

    segment_turns = 0
    for segment in podcast_json.get('segments', []):
        segment_turns += len(segment.get('dialogue', []))

    total_turns = opening_turns + segment_turns + closing_turns

    return {
        'opening': opening_turns,
        'segments': segment_turns,
        'closing': closing_turns,
        'total': total_turns
    }


def count_characters(podcast_json: Dict[str, Any]) -> Dict[str, int]:
    """Count characters in dialogue content."""
    total_chars = 0
    speaker_chars = {'anchor': 0, 'guest': 0}

    # Count opening
    for turn in podcast_json.get('opening', []):
        content = turn.get('content', '')
        total_chars += len(content)
        speaker = turn.get('speaker', 'unknown')
        if speaker in speaker_chars:
            speaker_chars[speaker] += len(content)

    # Count segments
    for segment in podcast_json.get('segments', []):
        for turn in segment.get('dialogue', []):
            content = turn.get('content', '')
            total_chars += len(content)
            speaker = turn.get('speaker', 'unknown')
            if speaker in speaker_chars:
                speaker_chars[speaker] += len(content)

    # Count closing
    for turn in podcast_json.get('closing', []):
        content = turn.get('content', '')
        total_chars += len(content)
        speaker = turn.get('speaker', 'unknown')
        if speaker in speaker_chars:
            speaker_chars[speaker] += len(content)

    return {
        'total': total_chars,
        'anchor': speaker_chars['anchor'],
        'guest': speaker_chars['guest']
    }


def extract_content_samples(podcast_json: Dict[str, Any], max_samples: int = 3) -> List[str]:
    """Extract sample dialogue turns."""
    samples = []

    # Get opening sample
    if podcast_json.get('opening'):
        for turn in podcast_json['opening'][:2]:
            speaker_name = turn.get('speaker_name', turn.get('speaker', ''))
            content = turn.get('content', '')
            samples.append(f"{speaker_name}: {content[:100]}...")

    # Get segment samples
    if podcast_json.get('segments'):
        first_segment = podcast_json['segments'][0]
        for turn in first_segment.get('dialogue', [])[:max_samples]:
            speaker_name = turn.get('speaker_name', turn.get('speaker', ''))
            content = turn.get('content', '')
            samples.append(f"{speaker_name}: {content[:100]}...")

    return samples[:max_samples]


def generate_approach1_podcast(qa_json_path: str, output_dir: str) -> str:
    """Generate podcast using Approach 1 (structured Q&A)."""
    logger.info("\n" + "="*60)
    logger.info("Approach 1: Structured Q&A-based Generation")
    logger.info("="*60)

    script_path = os.path.join(
        os.path.dirname(__file__),
        "llm_podcast_generate.py"
    )

    cmd = [
        sys.executable,
        script_path,
        "--qa", qa_json_path,
        "--output_dir", output_dir,
        "--num_qas", "3"
    ]

    logger.info(f"運行命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"❌ Approach 1 生成失敗:\n{result.stderr}")
        return None

    # Find generated JSON
    qa_basename = Path(qa_json_path).stem
    expected_json = os.path.join(output_dir, f"{qa_basename}.podcast.json")

    if os.path.exists(expected_json):
        logger.info(f"✅ Approach 1 生成成功: {expected_json}")
        return expected_json
    else:
        logger.error(f"❌ 未找到生成的播客文件: {expected_json}")
        return None


def generate_approach2_podcast(pdf_path: str, output_dir: str, max_chars: int = 800) -> str:
    """Generate podcast using Approach 2 (simple prompt)."""
    logger.info("\n" + "="*60)
    logger.info("Approach 2: Simple Direct PDF Generation")
    logger.info("="*60)

    if not pdf_path or not os.path.exists(pdf_path):
        logger.warning("⚠️  PDF 路徑未提供或不存在，跳過 Approach 2")
        return None

    script_path = os.path.join(
        os.path.dirname(__file__),
        "llm_podcast_generate_simple.py"
    )

    cmd = [
        sys.executable,
        script_path,
        "--pdf", pdf_path,
        "--output_dir", output_dir,
        "--max_chars", str(max_chars),
        "--max_pages", "5"  # Limit to first 5 pages for comparison
    ]

    logger.info(f"運行命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"❌ Approach 2 生成失敗:\n{result.stderr}")
        return None

    # Find generated JSON
    pdf_basename = Path(pdf_path).stem
    expected_json = os.path.join(output_dir, f"{pdf_basename}.podcast_simple.json")

    if os.path.exists(expected_json):
        logger.info(f"✅ Approach 2 生成成功: {expected_json}")
        return expected_json
    else:
        logger.error(f"❌ 未找到生成的播客文件: {expected_json}")
        return None


def compare_podcasts(approach1_json: str, approach2_json: str):
    """Compare two podcast JSON files and print analysis."""
    logger.info("\n" + "="*60)
    logger.info("播客生成對比分析")
    logger.info("="*60)

    # Load JSON files
    with open(approach1_json, 'r', encoding='utf-8') as f:
        podcast1 = json.load(f)

    with open(approach2_json, 'r', encoding='utf-8') as f:
        podcast2 = json.load(f)

    # Count metrics
    turns1 = count_dialogue_turns(podcast1)
    turns2 = count_dialogue_turns(podcast2)

    chars1 = count_characters(podcast1)
    chars2 = count_characters(podcast2)

    samples1 = extract_content_samples(podcast1)
    samples2 = extract_content_samples(podcast2)

    # Print comparison table
    print("\n" + "="*80)
    print(f"{'指標':<20} {'Approach 1 (Q&A)':<30} {'Approach 2 (Simple)':<30}")
    print("="*80)

    print(f"{'生成方法':<20} {'結構化問答 + 詳細提示':<30} {'直接 PDF + 簡單提示':<30}")
    print(f"{'集數標題':<20} {podcast1.get('episode_title', 'N/A')[:28]:<30} {podcast2.get('episode_title', 'N/A')[:28]:<30}")

    print("-"*80)
    print("對話輪數統計:")
    print(f"{'  - 開場白':<20} {turns1['opening']:<30} {turns2['opening']:<30}")
    print(f"{'  - 主要段落':<20} {turns1['segments']:<30} {turns2['segments']:<30}")
    print(f"{'  - 結尾':<20} {turns1['closing']:<30} {turns2['closing']:<30}")
    print(f"{'  - 總計':<20} {turns1['total']:<30} {turns2['total']:<30}")

    print("-"*80)
    print("字數統計:")
    print(f"{'  - 總字數':<20} {chars1['total']:<30} {chars2['total']:<30}")
    print(f"{'  - 主持人':<20} {chars1['anchor']:<30} {chars2['anchor']:<30}")
    print(f"{'  - 來賓':<20} {chars1['guest']:<30} {chars2['guest']:<30}")
    print(f"{'  - 平均每輪':<20} {chars1['total']//turns1['total'] if turns1['total'] > 0 else 0:<30} {chars2['total']//turns2['total'] if turns2['total'] > 0 else 0:<30}")

    print("-"*80)
    print("內容結構:")
    print(f"{'  - 段落數':<20} {len(podcast1.get('segments', [])):<30} {len(podcast2.get('segments', [])):<30}")
    print(f"{'  - 預估時長':<20} {podcast1.get('total_duration_estimate', 'N/A'):<30} {podcast2.get('total_duration_estimate', 'N/A'):<30}")

    print("="*80)

    # Print content samples
    print("\n" + "="*80)
    print("對話內容樣本對比")
    print("="*80)

    print("\n【Approach 1 - 結構化問答方法】")
    print("-"*80)
    for i, sample in enumerate(samples1, 1):
        print(f"{i}. {sample}")

    print("\n【Approach 2 - 簡單提示方法】")
    print("-"*80)
    for i, sample in enumerate(samples2, 1):
        print(f"{i}. {sample}")

    print("="*80)

    # Print observations
    print("\n" + "="*80)
    print("觀察與建議")
    print("="*80)

    observations = []

    # Complexity comparison
    if turns1['total'] > turns2['total'] * 1.5:
        observations.append("✓ Approach 1 生成了更詳細、更多輪次的對話")
    elif turns2['total'] > turns1['total'] * 1.5:
        observations.append("✓ Approach 2 生成了更簡潔的對話")
    else:
        observations.append("✓ 兩種方法的對話輪次相近")

    # Content depth
    avg_chars_per_turn_1 = chars1['total'] // turns1['total'] if turns1['total'] > 0 else 0
    avg_chars_per_turn_2 = chars2['total'] // turns2['total'] if turns2['total'] > 0 else 0

    if avg_chars_per_turn_1 > avg_chars_per_turn_2 * 1.3:
        observations.append("✓ Approach 1 每輪對話更深入詳細")
    elif avg_chars_per_turn_2 > avg_chars_per_turn_1 * 1.3:
        observations.append("✓ Approach 2 每輪對話更深入詳細")

    # Structure
    if podcast1.get('opening') and podcast1.get('closing'):
        observations.append("✓ Approach 1 有完整的開場和結尾結構")
    if not podcast2.get('opening') or not podcast2.get('closing'):
        observations.append("✓ Approach 2 缺少獨立的開場/結尾結構")

    # Print observations
    for obs in observations:
        print(f"  {obs}")

    print("\n推薦使用場景:")
    print("  • Approach 1: 需要深度講解、結構化內容、長播客（15-30分鐘）")
    print("  • Approach 2: 需要快速生成、簡短摘要、短播客（1-3分鐘）")

    print("="*80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="播客生成方法對比工具"
    )
    parser.add_argument(
        "--qa",
        type=str,
        required=True,
        help="Q&A JSON 文件路徑 (用於 Approach 1)"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=None,
        help="PDF 文件路徑 (用於 Approach 2，可選)"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="podcasts_comparison",
        help="輸出目錄 (預設：podcasts_comparison)"
    )
    parser.add_argument(
        "--max_chars_simple",
        type=int,
        default=800,
        help="Approach 2 的最大字數 (預設：800)"
    )

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    logger.info("="*80)
    logger.info("播客生成對比工具")
    logger.info("="*80)
    logger.info(f"Q&A 文件: {args.qa}")
    logger.info(f"PDF 文件: {args.pdf if args.pdf else '(未提供，僅測試 Approach 1)'}")
    logger.info(f"輸出目錄: {args.output_dir}")

    # Generate using Approach 1
    approach1_json = generate_approach1_podcast(args.qa, args.output_dir)

    # Generate using Approach 2 (if PDF provided)
    approach2_json = None
    if args.pdf:
        approach2_json = generate_approach2_podcast(
            args.pdf,
            args.output_dir,
            max_chars=args.max_chars_simple
        )

    # Compare if both generated successfully
    if approach1_json and approach2_json:
        compare_podcasts(approach1_json, approach2_json)
    elif approach1_json:
        logger.info("\n✅ Approach 1 生成完成")
        logger.info(f"   文件: {approach1_json}")
        logger.warning("⚠️  未提供 PDF，無法對比 Approach 2")
    else:
        logger.error("❌ 兩種方法都生成失敗")


if __name__ == "__main__":
    main()
