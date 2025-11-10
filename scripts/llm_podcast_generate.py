#!/usr/bin/env python3
"""
Podcast Script Generation Tool - Stage 1

This script generates natural conversation podcast scripts from Q&A pairs.
It creates engaging dialogues between an anchor (主持人) and invited speakers (來賓)
to bring Buddhist learning content to life through natural conversation.

Key Features:
- Multi-provider LLM support (DeepSeek, OpenAI, Gemini, DashScope, local vLLM)
- Natural conversation flow with multiple speakers
- Structured dialogue with speaker labels
- Automatic script generation from Q&A pairs
- Progress logging to file and console
- Support for Traditional and Simplified Chinese output

Usage:
    # Using default provider
    python llm_podcast_generate.py --qa_file qa_pairs/gemini/01.01.pdf.qa.json

    # Using specific provider
    python llm_podcast_generate.py --qa_file "qa_pairs/gemini/*.json" --provider openai

    # With custom output directory
    python llm_podcast_generate.py --qa_file qa_pairs/gemini/01.01.pdf.qa.json --out_dir podcasts

    # Generate simplified Chinese output
    python llm_podcast_generate.py --qa_file qa_pairs/gemini/01.01.pdf.qa.json --output_lang simplified

Author: DDM RAG Team
Last Updated: 2025-11-09
"""

import os
import sys
import logging
import json
import glob
import argparse
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from openai import OpenAI
from dotenv import load_dotenv
from opencc import OpenCC

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_config import config_manager

load_dotenv()

# ================================
# Logging Configuration
# ================================
log_file = time.strftime('logs/podcast_generation_%Y%m%d_%H%M%S.log')
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# ================================
# Pydantic Data Models
# ================================
from enum import Enum

class SpeakerRole(str, Enum):
    """Speaker roles in podcast conversation."""
    ANCHOR = "anchor"           # 主持人 - Main host
    GUEST = "guest"             # 來賓 - Invited guest/expert

class DialogueTurn(BaseModel):
    """A single turn in the podcast dialogue."""
    speaker: SpeakerRole = Field(description="Speaker role: anchor or guest")
    speaker_name: str = Field(description="Speaker's name in Traditional Chinese")
    content: str = Field(description="Dialogue content in Traditional Chinese")

    @field_validator('speaker', mode='before')
    @classmethod
    def validate_speaker(cls, v):
        """Validate speaker and fall back to default if invalid."""
        if isinstance(v, str):
            v_lower = v.lower()
            valid_values = {role.value for role in SpeakerRole}
            if v_lower in valid_values:
                return v_lower
            else:
                logger.warning(f"Invalid speaker role '{v}' - using default 'anchor'")
                return "anchor"
        return v

class PodcastSegment(BaseModel):
    """A podcast segment based on one Q&A pair."""
    question_reference: str = Field(description="The original question being discussed")
    segment_title: str = Field(description="Short title for this segment in Traditional Chinese")
    dialogue: List[DialogueTurn] = Field(description="List of dialogue turns in natural conversation")
    duration_estimate: str = Field(description="Estimated duration (e.g., '3-5分鐘')")

class PodcastEpisode(BaseModel):
    """Complete podcast episode script."""
    episode_title: str = Field(description="Episode title in Traditional Chinese")
    episode_summary: str = Field(description="Brief episode summary")
    speakers: Dict[str, str] = Field(description="Speaker roles and names (e.g., {'anchor': '王老師', 'guest': '林法師'})")
    opening: List[DialogueTurn] = Field(description="Opening dialogue/introduction")
    segments: List[PodcastSegment] = Field(description="Main content segments")
    closing: List[DialogueTurn] = Field(description="Closing dialogue/wrap-up")
    total_duration_estimate: str = Field(description="Estimated total duration")

# ================================
# Q&A Data Loading
# ================================
def load_qa_file(qa_file_path: str) -> Dict[str, Any]:
    """
    Load Q&A data from JSON file.

    Args:
        qa_file_path: Path to Q&A JSON file

    Returns:
        Dict containing Q&A data with structure:
        {
            "filename": str,
            "document_title": str,
            "topics": List[{
                "topic_title": str,
                "topic_summary": str,
                "page_range": [int, int],
                "qas": List[{
                    "question": str,
                    "question_type": str,
                    "learning_purpose": str,
                    "answer": str,
                    "evidence": List[Dict]
                }]
            }]
        }

    Raises:
        Exception: If file cannot be loaded or parsed
    """
    try:
        with open(qa_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"載入 Q&A 文件：{qa_file_path}")
        logger.info(f"  文件標題：{data.get('document_title', 'Unknown')}")
        logger.info(f"  主題數量：{len(data.get('topics', []))}")
        return data
    except Exception as e:
        logger.error(f"載入 Q&A 文件失敗 {qa_file_path}: {e}")
        raise

def select_qas_for_podcast(qa_data: Dict[str, Any], max_qas: int = 5) -> List[Dict[str, Any]]:
    """
    Select representative Q&As for podcast episode.

    Strategy:
    - Prioritize diversity in question_type and learning_purpose
    - Select from different topics if possible
    - Prefer questions with rich answers and evidence

    Args:
        qa_data: Loaded Q&A data
        max_qas: Maximum number of Q&As to select

    Returns:
        List of selected Q&A dicts with added context:
        [{
            "question": str,
            "answer": str,
            "topic_title": str,
            "topic_summary": str,
            "question_type": str,
            "learning_purpose": str,
            "evidence": List
        }]
    """
    selected = []
    topics = qa_data.get('topics', [])

    # Strategy: Round-robin through topics, select diverse Q&As
    topic_idx = 0
    question_types_used = set()
    learning_purposes_used = set()

    while len(selected) < max_qas and topic_idx < len(topics) * 3:  # Max 3 passes
        topic = topics[topic_idx % len(topics)]
        qas = topic.get('qas', [])

        # Find a Q&A that adds diversity
        for qa in qas:
            q_type = qa.get('question_type', '')
            l_purpose = qa.get('learning_purpose', '')

            # Prefer Q&As with unused types/purposes for diversity
            if len(selected) < max_qas and (
                q_type not in question_types_used or
                l_purpose not in learning_purposes_used or
                len(selected) < 2  # Always take first 2
            ):
                selected.append({
                    "question": qa.get('question', ''),
                    "answer": qa.get('answer', ''),
                    "topic_title": topic.get('topic_title', ''),
                    "topic_summary": topic.get('topic_summary', ''),
                    "question_type": q_type,
                    "learning_purpose": l_purpose,
                    "evidence": qa.get('evidence', [])
                })
                question_types_used.add(q_type)
                learning_purposes_used.add(l_purpose)
                break

        topic_idx += 1

    logger.info(f"選擇了 {len(selected)} 個問答對用於播客生成")
    return selected[:max_qas]

# ================================
# Chinese Character Conversion
# ================================
def convert_podcast_to_simplified(podcast: PodcastEpisode) -> PodcastEpisode:
    """
    Convert Traditional Chinese podcast script to Simplified Chinese.

    Args:
        podcast: PodcastEpisode object with Traditional Chinese content

    Returns:
        PodcastEpisode: Converted to Simplified Chinese
    """
    try:
        # Initialize OpenCC converter (Traditional to Simplified)
        converter = OpenCC('t2s')

        # Convert episode title
        podcast.episode_title = converter.convert(podcast.episode_title)

        # Convert episode summary
        podcast.episode_summary = converter.convert(podcast.episode_summary)

        # Convert speaker names
        podcast.speakers = {role: converter.convert(name) for role, name in podcast.speakers.items()}

        # Convert opening dialogue
        for turn in podcast.opening:
            turn.speaker_name = converter.convert(turn.speaker_name)
            turn.content = converter.convert(turn.content)

        # Convert segments
        for segment in podcast.segments:
            segment.segment_title = converter.convert(segment.segment_title)
            segment.question_reference = converter.convert(segment.question_reference)
            for turn in segment.dialogue:
                turn.speaker_name = converter.convert(turn.speaker_name)
                turn.content = converter.convert(turn.content)

        # Convert closing dialogue
        for turn in podcast.closing:
            turn.speaker_name = converter.convert(turn.speaker_name)
            turn.content = converter.convert(turn.content)

        # Convert duration estimates (they contain Chinese characters)
        podcast.total_duration_estimate = converter.convert(podcast.total_duration_estimate)
        for segment in podcast.segments:
            segment.duration_estimate = converter.convert(segment.duration_estimate)

        logger.info("✅ 已將播客腳本轉換為簡體中文")
        return podcast

    except Exception as e:
        logger.error(f"❌ 中文轉換失敗: {e}")
        return podcast

# ================================
# Podcast Script Generation
# ================================
def generate_podcast_script(
    client: OpenAI,
    document_title: str,
    selected_qas: List[Dict[str, Any]],
    model_name: str,
    temperature: float,
    max_tokens: int,
    output_lang: str = "traditional"
) -> Optional[PodcastEpisode]:
    """
    Generate podcast script from selected Q&As using LLM.

    Supports multiple LLM providers:
    - GPT models (OpenAI): Uses beta.chat.completions.parse()
    - DeepSeek/Qwen3 models: Uses chat.completions with JSON mode
    - vLLM local models (cpatonn/Qwen3-*): Uses beta.chat.completions.parse()
    - Gemini models: Uses beta.chat.completions.parse()

    Args:
        client: OpenAI-compatible client instance
        document_title: Title of source document
        selected_qas: List of selected Q&A pairs
        model_name: Model identifier
        temperature: LLM temperature (0.7-1.0 recommended for creative dialogue)
        max_tokens: Maximum output tokens

    Returns:
        PodcastEpisode: Complete podcast script, or None if generation fails
    """
    # Build system instruction
    lang_instruction = (
        "【重要：必須使用繁體中文】\n"
        "所有輸出必須使用繁體中文（Traditional Chinese）。\n\n"
    ) if output_lang == "traditional" else (
        "【重要：必須使用簡體中文】\n"
        "所有輸出必須使用簡體中文（Simplified Chinese）。\n\n"
    )

    system_instruction = (
        "你是一位專業的播客腳本編劇。你的任務是將佛學問答內容轉化為自然、生動的對話腳本。\n\n"
        f"{lang_instruction}"

        "【播客風格】\n"
        "- 雙人對談：主持人（anchor）+ 專家來賓（guest）\n"
        "- 對話應自然流暢，像真實的朋友對話\n"
        "- 主持人（anchor）：負責引導話題、提出問題（包括核心問題和追問）、把控節奏、從學習者角度請教\n"
        "- 來賓（guest）：佛學專家，深入講解佛法概念、引經據典、提供修行指導\n"
        "- 可以加入適當的互動：如「是的」「沒錯」「有趣」「原來如此」等回應詞\n"
        "- 避免生硬的背誦，要有啟發性和思考性\n"
        "- 主持人應該扮演好奇的學習者角色，通過提問引導來賓深入講解\n\n"

        "【內容深度與比例】\n"
        "- **佛法核心教義**（60-70%）：詳細講解原始問答中的佛學概念、經典依據、修行方法\n"
        "  * 引用經典：適當引述佛經原文或祖師大德的開示\n"
        "  * 概念解析：對專有名詞（如「四聖諦」「八正道」「般若」等）進行深入解釋\n"
        "  * 修行指導：提供具體的實踐方法和步驟\n"
        "- **個人經驗與案例**（20-30%）：來賓分享個人修行體驗或教學案例來闡釋概念\n"
        "  * 個人經驗應該是**輔助說明**，不應喧賓奪主\n"
        "  * 示例開場語：「這讓我想起...」「在我的修行經驗中...」「有位學生曾經...」\n"
        "  * 經驗分享後，應**回歸到佛法理論**的總結\n"
        "- **生活化比喻**（10%）：用現代生活例子幫助理解抽象概念\n\n"

        "【對話結構】\n"
        "1. opening（開場白）：\n"
        "   - 主持人介紹本集主題\n"
        "   - **重要**：主持人詳細介紹來賓背景（例：修行經歷、專長領域、教學經驗等）\n"
        "   - 來賓問候並簡短分享學佛因緣或修行心得\n"
        "   - 主持人表達對主題的興趣或提出引導性問題\n"
        "   - 營造輕鬆友好氛圍\n"
        "   - 3-5輪對話（確保來賓介紹完整）\n\n"

        "2. segments（主要段落）：\n"
        "   - 每個問答轉化為一個段落\n"
        "   - 主持人提出核心問題（改寫原問題，更口語化）\n"
        "   - 來賓深入講解佛法概念（基於原答案，但更有深度）\n"
        "     * **必須**：詳細解釋專有名詞、引用經典、提供修行指導\n"
        "     * **可選**：穿插少量個人經驗作為輔助說明（不超過2-3句）\n"
        "     * **必須**：經驗分享後立即回歸佛法理論總結\n"
        "   - 主持人從學習者角度追問、請求澄清、請求舉例\n"
        "     * 例：「法師，您剛才提到的『般若』，能否再詳細解釋一下？」\n"
        "     * 例：「這個修行方法具體要怎麼做呢？」\n"
        "     * 例：「這對我們日常生活有什麼啟發呢？」\n"
        "   - 來賓回應追問，進一步闡述\n"
        "   - 每段 6-10 輪對話（深度討論，來回互動）\n\n"

        "3. closing（結尾）：\n"
        "   - 主持人總結本集重點佛法概念\n"
        "   - 來賓給聽眾留下修行建議或思考方向\n"
        "   - 主持人分享聽後感悟或感謝來賓\n"
        "   - 預告下集或感謝收聽\n"
        "   - 2-4輪對話\n\n"

        "【對話要求】\n"
        "- speaker: 只能是 'anchor' 或 'guest'（僅兩個角色）\n"
        "- speaker_name: 角色名字（主持人如「小雯」，來賓如「慧心居士」）\n"
        "- content: 該角色的對話內容，自然口語化\n"
        "- 單次發言長度：主持人 1-3句話，來賓 2-5句話（來賓可稍長以深入講解）\n"
        "- 適時使用問句、驚嘆、停頓等口語特徵\n"
        "- 主持人多用疑問句、感嘆句來活躍氣氛\n"
        "- 來賓多用陳述句講解，偶爾用反問句引發思考\n\n"

        "【內容忠實性】\n"
        "- 對話內容必須基於提供的問答材料\n"
        "- 可以用更生活化的語言表達，但不可曲解原意\n"
        "- 專有名詞（如「四聖諦」「般若」）應保持準確\n"
        "- 可以適當補充說明，但核心內容來自原始問答\n\n"

        "【深度要求】\n"
        "- 對於重要概念，來賓應該提供**多層次解釋**：\n"
        "  1. 字面意義（名詞解釋）\n"
        "  2. 佛法脈絡（在整體教義中的位置）\n"
        "  3. 實踐應用（如何在修行中運用）\n"
        "- 引用經典時，應簡要說明出處和上下文\n"
        "- 修行方法應提供**具體步驟**，不只是概念性描述\n"
        "- 主持人應扮演「橋樑」角色，通過提問將艱深概念轉化為易懂的討論\n\n"

        "【JSON 格式要求】\n"
        "1. 輸出必須是完整且有效的 JSON 格式\n"
        "2. 所有字符串必須用雙引號包圍\n"
        "3. 確保所有括號正確閉合\n"
        "4. 不要包含 JSON 之外的任何文字\n\n"

        "【輸出結構】\n"
        '{\n'
        '  "episode_title": "本集標題（簡潔吸引人）",\n'
        '  "episode_summary": "本集簡介（2-3句話）",\n'
        '  "speakers": {"anchor": "主持人名字", "guest": "來賓名字"},\n'
        '  "opening": [\n'
        '    {"speaker": "anchor", "speaker_name": "小雯", "content": "各位聽眾朋友大家好..."},\n'
        '    {"speaker": "guest", "speaker_name": "慧心居士", "content": "主持人好，聽眾朋友們好..."}\n'
        '  ],\n'
        '  "segments": [\n'
        '    {\n'
        '      "question_reference": "原始問題",\n'
        '      "segment_title": "段落小標",\n'
        '      "dialogue": [\n'
        '        {"speaker": "anchor", "speaker_name": "小雯", "content": "...（提問）"},\n'
        '        {"speaker": "guest", "speaker_name": "慧心居士", "content": "...（深入講解佛法）"},\n'
        '        {"speaker": "anchor", "speaker_name": "小雯", "content": "...（追問細節）"},\n'
        '        {"speaker": "guest", "speaker_name": "慧心居士", "content": "...（進一步闡述）"}\n'
        '      ],\n'
        '      "duration_estimate": "4-6分鐘"\n'
        '    }\n'
        '  ],\n'
        '  "closing": [...],\n'
        '  "total_duration_estimate": "20-30分鐘"\n'
        '}\n'
    )

    # Build user prompt with Q&A content
    qa_content = ""
    for i, qa in enumerate(selected_qas, 1):
        qa_content += f"\n【問答 {i}】\n"
        qa_content += f"主題：{qa.get('topic_title', 'Unknown')}\n"
        qa_content += f"問題：{qa.get('question', '')}\n"
        qa_content += f"答案：{qa.get('answer', '')}\n"
        if qa.get('evidence'):
            qa_content += f"依據：{qa['evidence'][0].get('quote', '')[:100]}...\n"

    prompt = (
        f"【文件標題】{document_title}\n\n"
        f"【問答素材】（共 {len(selected_qas)} 個問答）\n"
        f"{qa_content}\n\n"
        f"【任務】\n"
        f"請基於以上問答素材，創作一集精彩的佛學播客對話腳本。\n"
        f"- 主持人和來賓通過自然對話來探討這些問題\n"
        f"- 對話要生動、有啟發性、易於理解\n"
        f"- 嚴格遵循 JSON 格式輸出\n"
        f"- 預估時長：20-30分鐘\n\n"
        f"請直接輸出 JSON 格式，不要包含任何其他文字。"
    )

    try:
        # Route to appropriate API based on model name
        if model_name.startswith("gpt-"):
            # OpenAI GPT models
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                response_format=PodcastEpisode
            )
            podcast = response.choices[0].message.parsed

        elif model_name.startswith("deepseek-") or model_name.startswith("qwen3-"):
            # DeepSeek/Qwen3 models with JSON mode
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if not content:
                logger.error("LLM response content is empty")
                return None
            json_data = json.loads(content)
            podcast = PodcastEpisode(**json_data)

        elif model_name.startswith("cpatonn/Qwen3-"):
            # vLLM local models
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=PodcastEpisode
            )
            podcast = response.choices[0].message.parsed

        elif model_name.startswith("gemini-"):
            # Gemini models
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=PodcastEpisode
            )
            podcast = response.choices[0].message.parsed

        else:
            raise ValueError(f"未知的模型名稱格式: {model_name}")

        if not podcast:
            logger.error("Podcast generation returned None")
            return None

        logger.info(f"✅ 成功生成播客腳本：{podcast.episode_title}")
        logger.info(f"   段落數：{len(podcast.segments)}")
        logger.info(f"   預估時長：{podcast.total_duration_estimate}")

        return podcast

    except Exception as e:
        logger.error(f"❌ LLM 處理失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# ================================
# Main Processing Function
# ================================
def process_qa_file(
    qa_file_path: str,
    client: OpenAI,
    model_name: str,
    temperature: float,
    max_tokens: int,
    output_dir: str,
    max_qas: int = 5,
    output_lang: str = "traditional"
) -> bool:
    """
    Process a single Q&A file to generate podcast script.

    Args:
        qa_file_path: Path to Q&A JSON file
        client: OpenAI-compatible client instance
        model_name: Model identifier
        temperature: LLM temperature
        max_tokens: Maximum output tokens
        output_dir: Output directory for podcast scripts
        max_qas: Maximum Q&As to include in podcast

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load Q&A data
        qa_data = load_qa_file(qa_file_path)
        document_title = qa_data.get('document_title', 'Unknown')

        # Select Q&As for podcast
        selected_qas = select_qas_for_podcast(qa_data, max_qas=max_qas)

        if not selected_qas:
            logger.warning(f"⚠️  沒有可用的問答對，跳過此文件")
            return False

        # Generate podcast script
        podcast = generate_podcast_script(
            client=client,
            document_title=document_title,
            selected_qas=selected_qas,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            output_lang=output_lang
        )

        if not podcast:
            return False

        # Convert to simplified Chinese if requested
        if output_lang == "simplified":
            podcast = convert_podcast_to_simplified(podcast)

        # Prepare output file
        output_filename = os.path.basename(qa_file_path).replace('.qa.json', '.podcast.json')
        output_path = os.path.join(output_dir, output_filename)

        # Save podcast script
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(podcast.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 已保存播客腳本：{output_path}")
        return True

    except Exception as e:
        logger.error(f"❌ 處理 Q&A 文件失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# ================================
# Main Entry Point
# ================================
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="播客腳本生成工具（從問答對生成自然對話腳本）"
    )
    parser.add_argument(
        "--qa_file",
        type=str,
        required=True,
        help="Q&A JSON 檔案路徑或通配符模式（例如 qa_pairs/gemini/*.json）"
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="podcasts",
        help="輸出目錄 (預設：podcasts)"
    )
    parser.add_argument(
        "--max_qas",
        type=int,
        default=5,
        help="每集播客包含的最大問答數 (預設：5)"
    )
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日誌級別"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=config_manager.get_available_providers(),
        help="LLM 供應商選擇"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="如果指定，將覆蓋已存在的輸出文件"
    )
    parser.add_argument(
        "--output_lang",
        type=str,
        default="traditional",
        choices=["traditional", "simplified"],
        help="輸出語言：traditional（繁體中文）或 simplified（簡體中文）(預設：traditional)"
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create output directory
    os.makedirs(args.out_dir, exist_ok=True)

    # Get provider config
    provider = args.provider or config_manager.default_provider
    logger.info(f"使用 LLM 供應商：{provider}")

    provider_config = config_manager.get_provider_config(provider)

    if not config_manager.validate_config(provider):
        logger.error(f"{provider} 配置不完整，請檢查 .env 文件")
        return

    # Create OpenAI client
    client = OpenAI(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url
    )

    # Use higher temperature for creative dialogue (0.7-0.9)
    temperature = 0.8

    # Find Q&A files
    qa_files = glob.glob(args.qa_file)
    if not qa_files:
        logger.error(f"找不到符合模式的 Q&A 文件：{args.qa_file}")
        return

    logger.info(f"找到 {len(qa_files)} 個 Q&A 文件")

    # Process each Q&A file
    successful_count = 0
    for qa_file in qa_files:
        output_filename = os.path.basename(qa_file).replace('.qa.json', '.podcast.json')
        output_path = os.path.join(args.out_dir, output_filename)

        # Skip if output exists and not overwrite
        if os.path.exists(output_path) and not args.overwrite:
            logger.info(f"⏭️  跳過已存在的文件：{output_path}")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"處理文件：{qa_file}")
        logger.info(f"{'='*60}")

        success = process_qa_file(
            qa_file_path=qa_file,
            client=client,
            model_name=provider_config.model_name,
            temperature=temperature,
            max_tokens=provider_config.max_tokens,
            output_dir=args.out_dir,
            max_qas=args.max_qas,
            output_lang=args.output_lang
        )

        if success:
            successful_count += 1

        # Pause between requests to avoid rate limits
        if len(qa_files) > 1:
            time.sleep(2)

    logger.info(f"\n{'='*60}")
    logger.info(f"處理完成！成功: {successful_count}/{len(qa_files)} 個文件")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    main()
